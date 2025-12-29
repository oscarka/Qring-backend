# Railway + Cloudflare 部署完整指南

## 📋 部署架构

```
iOS App → Cloudflare Worker → Railway Backend
Web Frontend (Cloudflare Pages) → Cloudflare Worker → Railway Backend
```

**优势**：
- ✅ 利用 Cloudflare 全球 CDN 加速中国大陆访问
- ✅ 隐藏后端真实地址
- ✅ 免费使用（小规模）
- ✅ 简单配置

---

## 🚀 第一步：部署后端到 Railway

### 1.1 创建 Railway 项目

1. 访问 [Railway](https://railway.app)
2. 登录账号
3. 点击 "New Project"
4. 选择 "Deploy from GitHub repo"
5. 选择 `oscarka/Qring-backend` 仓库

### 1.2 配置环境变量

在 Railway Dashboard → Variables 中添加：

```
FLASK_ENV=production
FLASK_DEBUG=False
CORS_ORIGINS=https://your-frontend.pages.dev,https://your-worker.workers.dev
```

**重要**：
- `CORS_ORIGINS` 应该包含前端域名和 Cloudflare Worker 域名
- 多个域名用逗号分隔
- `PORT` 由 Railway 自动设置，不需要配置

### 1.3 配置数据持久化（推荐）

1. 在 Railway Dashboard → Volumes
2. 点击 "Create Volume"
3. 设置挂载路径：`/app/data`
4. 创建 Volume

Railway 会自动设置环境变量 `RAILWAY_VOLUME_MOUNT_PATH=/app/data`，代码会自动使用此路径。

### 1.4 等待部署完成

Railway 会自动：
- 检测 `railway.toml` 配置
- 安装依赖
- 启动服务
- 运行健康检查

### 1.5 获取部署 URL

部署完成后，Railway 会提供一个 URL，例如：
```
https://qring-backend-production.up.railway.app
```

**保存这个 URL，后续配置 Cloudflare Worker 会用到。**

---

## 🌐 第二步：配置 Cloudflare Worker（代理）

### 2.1 创建 Cloudflare Worker

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com)
2. 进入 "Workers & Pages"
3. 点击 "Create application"
4. 选择 "Create Worker"
5. 输入名称：`qring-api-proxy`

### 2.2 编写 Worker 代码

在 Worker 编辑器中，替换默认代码为：

```javascript
// Cloudflare Worker - Qring API 反向代理
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  // Railway 后端地址（从环境变量读取）
  const BACKEND_URL = env.BACKEND_URL || 'https://qring-backend-production.up.railway.app'
  
  // 获取请求URL
  const url = new URL(request.url)
  
  // 构建后端URL
  const backendUrl = new URL(BACKEND_URL)
  backendUrl.pathname = url.pathname
  backendUrl.search = url.search
  
  // 创建新请求
  const newRequest = new Request(backendUrl.toString(), {
    method: request.method,
    headers: request.headers,
    body: request.body,
  })
  
  // 转发请求到后端
  try {
    const response = await fetch(newRequest)
    
    // 创建新响应，添加CORS头
    const newResponse = new Response(response.body, {
      status: response.status,
      statusText: response.statusText,
      headers: {
        ...response.headers,
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
      },
    })
    
    return newResponse
  } catch (error) {
    return new Response(JSON.stringify({ 
      error: 'Proxy error', 
      message: error.message 
    }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}
```

### 2.3 配置环境变量

在 Worker 设置 → Variables 中添加：

- **变量名**：`BACKEND_URL`
- **变量值**：你的 Railway URL（例如：`https://qring-backend-production.up.railway.app`）

### 2.4 部署 Worker

1. 点击 "Save and Deploy"
2. Worker 会获得一个 URL，例如：`https://qring-api-proxy.your-subdomain.workers.dev`

**保存这个 URL，后续配置前端和 iOS App 会用到。**

### 2.5 配置自定义域名（可选）

1. 在 Worker 设置 → Triggers → Custom Domains
2. 添加自定义域名，例如：`api.yourdomain.com`
3. 配置 DNS 记录指向 Cloudflare

---

## 🎨 第三步：部署前端到 Cloudflare Pages

### 3.1 创建 Cloudflare Pages 项目

1. 在 Cloudflare Dashboard → Workers & Pages
2. 点击 "Create application" → "Pages"
3. 选择 "Connect to Git"
4. 选择 `oscarka/Qring-frontend` 仓库

### 3.2 配置构建设置

- **Framework preset**: Vite
- **Build command**: `npm run build`
- **Build output directory**: `dist`

### 3.3 配置环境变量

在 Pages 设置 → Environment variables 中添加：

```
VITE_API_BASE=https://qring-api-proxy.your-subdomain.workers.dev/api
```

或使用自定义域名：

```
VITE_API_BASE=https://api.yourdomain.com/api
```

### 3.4 部署

Cloudflare Pages 会自动：
- 检测到代码推送
- 运行构建
- 部署到全球 CDN

### 3.5 获取前端 URL

部署完成后，Cloudflare Pages 会提供一个 URL，例如：
```
https://qring-frontend.pages.dev
```

---

## 📱 第四步：配置 iOS App

### 4.1 修改服务器地址

在 `QringDataCollector.m` 中：

```objective-c
// 使用 Cloudflare Worker URL
#define SERVER_URL @"https://qring-api-proxy.your-subdomain.workers.dev/api/qring/upload"

// 或使用自定义域名
#define SERVER_URL @"https://api.yourdomain.com/api/qring/upload"
```

### 4.2 确保使用 HTTPS

代码中应该使用 `https://` 而不是 `http://`。

### 4.3 测试连接

1. 运行 iOS App
2. 测试数据上传
3. 检查后端日志确认数据接收

---

## ✅ 部署验证

### 1. 后端健康检查

```bash
curl https://qring-backend-production.up.railway.app/api/health
```

应该返回：
```json
{
  "status": "ok",
  "timestamp": "2025-01-01T12:00:00",
  "version": "1.0.0"
}
```

### 2. Cloudflare Worker 测试

```bash
curl https://qring-api-proxy.your-subdomain.workers.dev/api/health
```

应该返回相同的结果。

### 3. 前端访问

访问前端 URL，应该能看到数据展示。

### 4. iOS App 测试

在 iOS App 中测试数据上传，检查后端是否收到数据。

---

## 🔧 配置总结

### 环境变量配置清单

#### Railway（后端）
```
FLASK_ENV=production
FLASK_DEBUG=False
CORS_ORIGINS=https://your-frontend.pages.dev,https://your-worker.workers.dev
```

#### Cloudflare Worker
```
BACKEND_URL=https://qring-backend-production.up.railway.app
```

#### Cloudflare Pages（前端）
```
VITE_API_BASE=https://qring-api-proxy.your-subdomain.workers.dev/api
```

#### iOS App
```objective-c
#define SERVER_URL @"https://qring-api-proxy.your-subdomain.workers.dev/api/qring/upload"
```

---

## 💰 成本估算

### Railway
- **$5/月** - Hobby 套餐
- 包含：512MB RAM, 1GB 存储, 100GB 流量
- **10人使用完全够用**

### Cloudflare
- **Worker**: 免费（每天 100,000 请求）
- **Pages**: 免费（无限请求）
- **10人使用完全在免费额度内**

### 总成本
**约 $5/月（仅 Railway）**

---

## 🐛 故障排查

### 问题1：后端无法访问

- 检查 Railway 服务是否运行
- 检查环境变量配置
- 查看 Railway 日志

### 问题2：Worker 代理失败

- 检查 `BACKEND_URL` 环境变量
- 检查 Railway URL 是否正确
- 查看 Worker 日志

### 问题3：前端无法获取数据

- 检查 `VITE_API_BASE` 环境变量
- 检查 CORS 配置
- 检查浏览器控制台错误

### 问题4：iOS App 连接失败

- 检查服务器地址是否正确
- 确保使用 HTTPS
- 检查网络连接

---

## 📚 相关文档

- [Railway部署配置说明.md](./Railway部署配置说明.md)
- [Cloudflare Workers代理配置.md](./Cloudflare%20Workers代理配置.md)
- [后端部署指南.md](./后端部署指南.md)
- [后端平台对比分析-中国大陆用户.md](./后端平台对比分析-中国大陆用户.md)

---

## 🎯 下一步

1. ✅ 部署后端到 Railway
2. ✅ 配置 Cloudflare Worker
3. ✅ 部署前端到 Cloudflare Pages
4. ✅ 配置 iOS App
5. ✅ 测试所有功能
6. ✅ 监控使用情况

部署完成后，你的应用就可以为全球用户（包括中国大陆）提供服务了！🚀

