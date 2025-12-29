# Cloudflare Workers 后端代理配置

## 📋 用途

通过Cloudflare Workers作为反向代理，加速中国大陆用户访问Railway/Cloud Run后端。

## 🎯 优势

1. **全球CDN加速**：利用Cloudflare的全球网络
2. **隐藏后端地址**：不暴露真实后端URL
3. **免费使用**：Cloudflare Workers免费额度足够
4. **简单配置**：只需创建一个Worker脚本

---

## 📝 配置步骤

### 步骤1：创建Cloudflare Worker

1. 登录 [Cloudflare Dashboard](https://dash.cloudflare.com)
2. 选择你的账户
3. 进入 "Workers & Pages"
4. 点击 "Create application"
5. 选择 "Create Worker"
6. 输入名称，例如：`qring-api-proxy`

### 步骤2：编写Worker代码

在Worker编辑器中，替换默认代码为：

```javascript
// Cloudflare Worker - Qring API 反向代理
addEventListener('fetch', event => {
  event.respondWith(handleRequest(event.request))
})

async function handleRequest(request) {
  // 后端真实地址（Railway或Cloud Run）
  const BACKEND_URL = 'https://your-backend.railway.app' // 或 Cloud Run URL
  
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
    return new Response(JSON.stringify({ error: 'Proxy error', message: error.message }), {
      status: 500,
      headers: { 'Content-Type': 'application/json' },
    })
  }
}
```

### 步骤3：配置环境变量（可选）

如果需要动态配置后端地址：

1. 在Worker设置中添加环境变量：
   - 变量名：`BACKEND_URL`
   - 变量值：`https://your-backend.railway.app`

2. 修改代码使用环境变量：
```javascript
const BACKEND_URL = env.BACKEND_URL || 'https://your-backend.railway.app'
```

### 步骤4：部署Worker

1. 点击 "Save and Deploy"
2. Worker会获得一个URL，例如：`https://qring-api-proxy.your-subdomain.workers.dev`

### 步骤5：配置自定义域名（可选）

1. 在Worker设置中，添加自定义域名
2. 例如：`api.yourdomain.com`
3. 配置DNS记录指向Cloudflare

---

## 🔧 使用方式

### iOS App配置

修改 `ViewController.m` 中的服务器地址：

```objective-c
// 原来：直接连接Railway
NSString *serverURL = @"https://your-backend.railway.app";

// 改为：通过Cloudflare Worker代理
NSString *serverURL = @"https://qring-api-proxy.your-subdomain.workers.dev";
// 或使用自定义域名
NSString *serverURL = @"https://api.yourdomain.com";
```

### 前端配置

修改 `.env.production`：

```bash
# 原来：直接连接后端
VITE_API_BASE=https://your-backend.railway.app/api

# 改为：通过Cloudflare Worker代理
VITE_API_BASE=https://qring-api-proxy.your-subdomain.workers.dev/api
# 或使用自定义域名
VITE_API_BASE=https://api.yourdomain.com/api
```

---

## 🎯 高级配置

### 1. 添加缓存（可选）

```javascript
async function handleRequest(request) {
  const BACKEND_URL = 'https://your-backend.railway.app'
  const url = new URL(request.url)
  
  // GET请求可以缓存
  if (request.method === 'GET' && url.pathname.startsWith('/api/stats')) {
    const cacheKey = new Request(url.toString(), request)
    const cache = caches.default
    
    // 检查缓存
    let response = await cache.match(cacheKey)
    if (response) {
      return response
    }
    
    // 从后端获取
    response = await fetch(BACKEND_URL + url.pathname + url.search)
    
    // 缓存5分钟
    response = new Response(response.body, response)
    response.headers.set('Cache-Control', 'public, max-age=300')
    event.waitUntil(cache.put(cacheKey, response.clone()))
    
    return response
  }
  
  // 其他请求直接转发
  // ... 原有代码
}
```

### 2. 添加请求日志

```javascript
async function handleRequest(request) {
  console.log(`[${new Date().toISOString()}] ${request.method} ${request.url}`)
  
  // ... 原有代码
}
```

### 3. 添加错误重试

```javascript
async function fetchWithRetry(url, options, retries = 3) {
  for (let i = 0; i < retries; i++) {
    try {
      return await fetch(url, options)
    } catch (error) {
      if (i === retries - 1) throw error
      await new Promise(resolve => setTimeout(resolve, 1000 * (i + 1)))
    }
  }
}
```

---

## 📊 性能优化

### 1. 连接复用

Cloudflare Workers自动处理连接复用，无需额外配置。

### 2. 压缩响应

```javascript
// 在响应头中添加压缩
response.headers.set('Content-Encoding', 'gzip')
```

### 3. 减少延迟

- 使用Cloudflare的全球网络
- 选择离用户最近的边缘节点
- 减少不必要的处理逻辑

---

## ⚠️ 注意事项

### 1. CORS配置

Worker已经添加了CORS头，但后端也应该配置CORS：

```python
# qring_api_server.py
CORS_ORIGINS = os.getenv('CORS_ORIGINS', '*')
```

### 2. 超时设置

- Cloudflare Workers超时：30秒（免费版）
- 确保后端API响应时间<30秒

### 3. 请求大小限制

- Cloudflare Workers：100MB请求体限制
- 对于健康数据上传，完全够用

### 4. 成本

- **免费额度**：每天100,000请求
- **超出后**：$0.50/百万请求
- **10人使用**：完全在免费额度内

---

## 🧪 测试

### 1. 测试Worker

```bash
# 测试健康检查
curl https://qring-api-proxy.your-subdomain.workers.dev/api/health

# 测试API
curl https://qring-api-proxy.your-subdomain.workers.dev/api/stats
```

### 2. 测试速度

- 在中国大陆测试访问速度
- 对比直接访问后端和通过Worker访问
- 应该看到明显的速度提升

---

## ✅ 总结

使用Cloudflare Workers作为反向代理可以：
- ✅ 加速中国大陆用户访问
- ✅ 隐藏后端真实地址
- ✅ 免费使用
- ✅ 简单配置

**推荐**：无论选择哪个后端平台，都建议使用Cloudflare Workers加速。

