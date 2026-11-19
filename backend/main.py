from pathlib import Path
import io
import os
import time

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "backend" / "models"
YOLO_WEIGHTS = Path(os.getenv("VISIONLAB_YOLO_WEIGHTS", str(MODEL_DIR / "best.pt")))

app = FastAPI(title="VISIONLAB API", version="2.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

_yolo = None

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

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "yolo_weights_found": YOLO_WEIGHTS.exists(),
        "message": "VISIONLAB API 已启动；本系统仅提供工地安全帽/头盔与反光衣检测（best.pt）。",
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

app.mount("/", StaticFiles(directory=ROOT / "frontend", html=True), name="frontend")
