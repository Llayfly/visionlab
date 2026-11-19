# VISIONLAB 后端镜像（FastAPI + YOLOv8）
#
# 用途：部署到阿里云（ECS 自建 / 容器镜像服务 ACR + 函数计算 FC 自定义容器）
# 构建（在项目根目录执行，注意构建上下文必须包含 backend/models/best.pt）：
#   docker build -t visionlab-api:latest .
#   docker run -d -p 8000:8000 --name visionlab-api visionlab-api:latest
#
# 说明：best.pt 被 .gitignore 排除，克隆仓库后不会自带权重，
# 构建前请确认本地存在 backend\models\best.pt（约 5.1 MB）。

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    VISIONLAB_YOLO_WEIGHTS=/app/backend/models/best.pt

WORKDIR /app

# OpenCV / Pillow 运行所需系统库
RUN apt-get update \
 && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 libsm6 libxext6 libxrender1 \
 && rm -rf /var/lib/apt/lists/*

# 先装 CPU 版 torch，避免 pip 拉取 CUDA 版本（体积可省 1.5 GB 以上）
RUN pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
  CMD python -c "import urllib.request;urllib.request.urlopen('http://127.0.0.1:8000/api/health',timeout=3)"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
