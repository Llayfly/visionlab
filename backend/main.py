from pathlib import Path
import io
import os
import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "backend" / "models"
YOLO_WEIGHTS = Path(os.getenv("VISIONLAB_YOLO_WEIGHTS", str(MODEL_DIR / "best.pt")))
REALESRGAN_WEIGHTS = Path(os.getenv("VISIONLAB_ESRGAN_WEIGHTS", str(MODEL_DIR / "RealESRGAN_x4plus.pth")))

app = FastAPI(title="VISIONLAB API", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_yolo = None
_realesrgan = None

def open_image(raw: bytes) -> Image.Image:
    try:
        image = Image.open(io.BytesIO(raw)).convert("RGB")
        if image.width * image.height > 40_000_000:
            raise HTTPException(status_code=413, detail="图像尺寸过大，请使用小于 4000 万像素的图片")
        return image
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail="无法读取图像文件") from exc

def get_yolo():
    global _yolo
    if _yolo is not None:
        return _yolo
    if not YOLO_WEIGHTS.exists():
        raise HTTPException(
            status_code=503,
            detail=f"找不到工地安全帽检测权重文件：{YOLO_WEIGHTS.name}。请将模型权重放入 backend/models/，或设置 VISIONLAB_YOLO_WEIGHTS。",
        )
    try:
        from ultralytics import YOLO
        _yolo = YOLO(str(YOLO_WEIGHTS))
        return _yolo
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"YOLOv8 加载失败：{exc}") from exc

def get_realesrgan():
    global _realesrgan
    if _realesrgan is not None:
        return _realesrgan
    if not REALESRGAN_WEIGHTS.exists():
        raise HTTPException(
            status_code=503,
            detail=f"找不到 Real-ESRGAN 权重文件：{REALESRGAN_WEIGHTS.name}。请将模型权重放入 backend/models/。",
        )
    try:
        import torch
        from realesrgan import RealESRGANer
        from basicsr.archs.rrdbnet_arch import RRDBNet
        model = RRDBNet(
            num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23,
            num_grow_ch=32, scale=4
        )
        _realesrgan = RealESRGANer(
            scale=4, model_path=str(REALESRGAN_WEIGHTS), model=model,
            tile=0, tile_pad=10, pre_pad=0,
            half=torch.cuda.is_available()
        )
        return _realesrgan
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Real-ESRGAN 加载失败：{exc}") from exc

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "yolo_weights_found": YOLO_WEIGHTS.exists(),
        "esrgan_weights_found": REALESRGAN_WEIGHTS.exists(),
        "message": "VISIONLAB API 已启动；目标检测模型为工地安全帽/头盔检测（best.pt）。",
    }

@app.post("/api/detect")
async def detect(file: UploadFile = File(...), confidence: float = Form(0.5)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图像文件")
    confidence = max(0.01, min(0.99, confidence))
    raw = await file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="图像文件不能超过 25 MB")
    image = open_image(raw)
    model = get_yolo()
    start = time.perf_counter()
    try:
        results = model.predict(source=image, conf=confidence, verbose=False)
        elapsed = round((time.perf_counter() - start) * 1000, 1)
        result = results[0]
        names = result.names
        detections = []
        if result.boxes is not None:
            for box in result.boxes:
                cls_id = int(box.cls.item())
                detections.append({
                    "label": str(names.get(cls_id, cls_id)),
                    "confidence": round(float(box.conf.item()), 4),
                    "xyxy": [round(float(v), 2) for v in box.xyxy[0].tolist()],
                })
        avg = sum(x["confidence"] for x in detections) / len(detections) if detections else None
        return {"count": len(detections), "average_confidence": avg, "elapsed_ms": elapsed, "detections": detections}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"目标检测执行失败：{exc}") from exc

@app.post("/api/enhance")
async def enhance(file: UploadFile = File(...), scale: int = Form(2)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="请上传图像文件")
    if scale not in (2, 4):
        raise HTTPException(status_code=400, detail="放大倍率只支持 2 或 4")
    raw = await file.read()
    if len(raw) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="图像文件不能超过 25 MB")
    image = open_image(raw)
    enhancer = get_realesrgan()
    try:
        import numpy as np
        import cv2
        output, _ = enhancer.enhance(cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR), outscale=scale)
        output = cv2.cvtColor(output, cv2.COLOR_BGR2RGB)
        buf = io.BytesIO()
        Image.fromarray(output).save(buf, format="PNG")
        return Response(content=buf.getvalue(), media_type="image/png")
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"高清增强执行失败：{exc}") from exc

app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
