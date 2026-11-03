# VISIONLAB · 智能视觉工作站

一个可本地运行的前后端项目，包含图像上传、ESRGAN 高清增强接口、YOLOv8 目标检测接口、视频本地预览、数据统计与历史任务页面。

## 项目结构

```text
VISIONLAB_完整项目/
├─ frontend/
│  └─ index.html             # 网站界面
├─ backend/
│  ├─ __init__.py
│  ├─ main.py                # FastAPI 后端与推理接口
│  └─ models/
│     └─ README.txt          # 模型权重放置说明
├─ scripts/
│  ├─ 启动网站.bat           # Windows 一键启动
│  └─ 检查环境.bat
├─ requirements.txt
└─ README.md
```

## Windows 启动步骤

1. 安装 Python 3.10 或 3.11（安装时勾选 **Add Python to PATH**）。
2. 解压整个项目文件夹，不要只单独运行 `index.html`。
3. 双击 `scripts/启动网站.bat`。首次启动会创建 `.venv` 并安装依赖，可能需要几分钟。
4. 浏览器打开 `http://127.0.0.1:8000`。
5. 可访问 `http://127.0.0.1:8000/api/health` 检查后端状态。

## 模型配置

项目代码已提供真实模型接口，但**权重文件没有打包**：

- YOLOv8：将 `yolov8n.pt` 放入 `backend/models/`。
- Real-ESRGAN：将 `RealESRGAN_x4plus.pth` 放入 `backend/models/`。

对应接口：
- `POST /api/detect`：表单字段 `file`（图像）与 `confidence`（0.01–0.99）。
- `POST /api/enhance`：表单字段 `file`（图像）与 `scale`（2 或 4）。

Real-ESRGAN 的 Python 依赖可能因 Python、PyTorch、CUDA 版本而不同。需要时在虚拟环境中按 Real-ESRGAN 官方项目说明安装 `realesrgan` 及兼容的 PyTorch/BasicSR 依赖。若尚未安装或缺少权重，API 会返回清晰错误，不会伪造成功结果。

## 视频流说明

当前提供本地视频文件预览。要做实时视频目标检测，还需增加逐帧推理与流式传输逻辑；当前版本不把普通视频播放冒充实时 AI 检测。

## 安全与使用

- 默认只监听 `127.0.0.1`，仅本机访问。
- 上传文件大小限制为 25 MB；图像限制为 4000 万像素。
- 当前为开发/本地演示配置，不建议直接暴露到公网。
