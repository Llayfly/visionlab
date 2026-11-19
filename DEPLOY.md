# VISIONLAB 部署指南（Vercel + 阿里云 + Cloudflare）

## 一、先说结论：三层怎么分工

| 层 | 放在哪 | 跑什么 | 说明 |
|---|---|---|---|
| 静态前端 | Vercel（或 Cloudflare Pages） | `frontend/` 目录的 HTML/CSS/JS | 纯静态，不跑模型 |
| 检测后端 | 阿里云（ECS 或 函数计算 FC 自定义容器） | FastAPI + YOLOv8（`best.pt`） | **必须**有 Python 运行环境，Vercel 跑不了 |
| 域名 / DNS / HTTPS / CDN | Cloudflare | 域名解析、SSL、加速 | 只做流量入口，不跑代码 |

> 关键点：Vercel 的函数上限约 250 MB、单次执行有时限，装不下 `torch + ultralytics`（约 1~2 GB），
> 所以检测接口只能落在阿里云。前端与后端分离后，靠 `frontend/config.js` 指定后端地址。

---

## 二、先发布后端（阿里云）

### 方式 A：ECS + Docker（推荐，最省事）

1. 购买 ECS（Ubuntu 22.04 / 2 核 4 GB 起，无需 GPU；`torch` 用 CPU 版即可）。
2. 安全组放行入方向 `8000`（或直接放行 `80/443` 由 Nginx 反代）。
3. 本机在项目根目录构建并推送镜像（阿里云容器镜像服务 ACR）：

```bash
# 登录 ACR（地址在 ACR 控制台「访问凭证」页）
docker login registry.cn-shenzhen.aliyuncs.com

# 构建（构建上下文必须包含 backend/models/best.pt）
docker build -t visionlab-api:latest .

# 打标签并推送
docker tag visionlab-api:latest registry.cn-shenzhen.aliyuncs.com/<命名空间>/visionlab-api:latest
docker push registry.cn-shenzhen.aliyuncs.com/<命名空间>/visionlab-api:latest
```

4. ECS 上拉取并运行：

```bash
docker login registry.cn-shenzhen.aliyuncs.com
docker pull registry.cn-shenzhen.aliyuncs.com/<命名空间>/visionlab-api:latest
docker run -d --name visionlab-api --restart always -p 8000:8000 \
  registry.cn-shenzhen.aliyuncs.com/<命名空间>/visionlab-api:latest
```

5. 验证：

```bash
curl http://<ECS 公网 IP>:8000/api/health
# 期望：{"status":"ok","yolo_weights_found":true,...}
```

> `yolo_weights_found` 为 `false` 说明镜像里没有 `best.pt`，重新确认构建上下文。

### 方式 B：不想用 Docker，直接在 ECS 上跑

```bash
sudo apt update && sudo apt install -y python3.11 python3.11-venv
git clone https://github.com/Llayfly/visionlab.git
cd visionlab
python3.11 -m venv .venv && source .venv/bin/activate
pip install --index-url https://download.pytorch.org/whl/cpu torch torchvision
pip install -r requirements.txt
# 把 best.pt 传到 backend/models/（git 里没有权重，需 scp 或从本地拖上去）
nohup uvicorn backend.main:app --host 0.0.0.0 --port 8000 > api.log 2>&1 &
```

> 权重文件：`backend/models/best.pt` 被 `.gitignore` 排除（约 5.1 MB），克隆仓库不会带上，需手动上传。

### 方式 C：阿里云函数计算 FC（自定义容器）

- FC 支持"自定义容器"，把上面同一个镜像推到 ACR，在 FC 控制台选镜像部署；
- 监听端口必须 `0.0.0.0:8000`（与本 Dockerfile 一致）；
- 冷启动会重新加载模型（约 5~15 秒），首屏检测可能较慢。

---

## 三、再发布前端（Vercel）

1. 打开 https://vercel.com → **Add New Project** → 导入 `Llayfly/visionlab` 仓库。
2. 关键设置：
   - **Root Directory**：`frontend`
   - **Framework Preset**：`Other`
   - **Build Command**：留空
   - **Output Directory**：留空（`frontend/vercel.json` 已配置）
3. 部署完成后拿到域名，例如 `https://visionlab.vercel.app`。
4. 回到仓库改 `frontend/config.js`，把后端地址填上：

```js
window.VISIONLAB_API = "http://<ECS 公网 IP>:8000";
```

5. 提交后 Vercel 自动重新部署，打开站点即可看到右上角状态变为「已连接」。

> 若后端还没配 HTTPS，浏览器在 https 页面里调用 http 接口会被拦截（混合内容）。
> 解决办法：给后端挂 Cloudflare 域名并开启 HTTPS（见下面第四节），`config.js` 填 `https://api.你的域名`。

---

## 四、Cloudflare（域名 + HTTPS + 加速）

1. 在 Cloudflare 添加站点，把域名的 NS 改到 Cloudflare 提供的两条地址。
2. 加解析：
   - `visionlab`（或 `@`）→ CNAME → `cname.vercel-dns.com`（前端，建议 **DNS only**，Vercel 自己管证书）
   - `api` → A → `<ECS 公网 IP>`（后端，建议 **Proxied** 开着橙云，走 Cloudflare HTTPS 与 CDN）
3. SSL/TLS 模式选 **Full**（ECS 上用 Nginx + Let's Encrypt 证书），或 **Flexible**（仅临时，源站 80 明文）。
4. 后端建议加 Nginx 反代 + 证书：

```nginx
server {
    listen 443 ssl;
    server_name api.你的域名;
    ssl_certificate     /etc/letsencrypt/live/api.你的域名/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.你的域名/privkey.pem;

    client_max_body_size 25m;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
```

`client_max_body_size` 必须不低于 25 MB，否则图片上传会被 413 拦掉。

---

## 五、上线检查清单

- [ ] `curl https://api.你的域名/api/health` 返回 `yolo_weights_found: true`
- [ ] `frontend/config.js` 的 `VISIONLAB_API` 指向 `https://api.你的域名`（无结尾斜杠）
- [ ] 站点打开后右上角状态灯为绿色「已连接」
- [ ] 拖一张佩戴安全帽的工地照片进工作台，四类统计与耗时正常返回
- [ ] 手机端访问同样可用（Vercel 域名自带 HTTPS）

---

## 六、改过的本地行为（不影响双击启动）

- 本地仍然双击 `scripts/启动网站.bat`，访问 http://127.0.0.1:8000；
- `config.js` 留空时前端自动走同源，本地行为与之前完全一致；
- 只有跨域部署场景才需要填 `window.VISIONLAB_API`。
