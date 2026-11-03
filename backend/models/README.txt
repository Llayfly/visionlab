将模型权重文件放在此目录：

1. YOLOv8：默认文件名 yolov8n.pt
   也可设置环境变量 VISIONLAB_YOLO_WEIGHTS 指向其他 YOLOv8 权重。

2. Real-ESRGAN：默认文件名 RealESRGAN_x4plus.pth
   也可设置环境变量 VISIONLAB_ESRGAN_WEIGHTS 指向权重文件。

注意：模型权重不包含在项目压缩包内，需要用户自行从模型官方/可信来源获取。
没有权重时，网站界面和 API 健康检查仍可启动；对应推理接口会明确提示缺少模型文件。
