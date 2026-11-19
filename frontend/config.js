/*
 * VISIONLAB 前端部署配置
 *
 * 留空 "" ：前端与后端同源（本地 scripts\启动网站.bat 或后端一并托管前端）。
 * 跨域部署（例如前端放 Vercel / Cloudflare Pages，后端放阿里云）时，
 * 必须填写后端公网地址，例如：
 *   window.VISIONLAB_API = "https://api.your-domain.com";
 *
 * 注意：后端地址不要带结尾斜杠。后端已开启 CORS（允许所有来源）。
 */
window.VISIONLAB_API = "";
