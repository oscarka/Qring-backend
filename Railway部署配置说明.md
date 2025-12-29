# Railway 部署配置说明

## 📋 Railway.toml 配置

已创建 `railway.toml` 配置文件，Railway 会自动识别并使用此配置。

### 配置说明

- **builder**: 使用 NIXPACKS（Railway 自动检测 Python 项目）
- **buildCommand**: 安装 Python 依赖
- **startCommand**: 启动 Flask 应用
- **restartPolicy**: 失败时自动重启（最多 10 次）
- **healthcheck**: 健康检查配置（每 30 秒检查一次 `/api/health`）

## 🔧 环境变量配置

### 必需的环境变量

在 Railway Dashboard 中配置以下环境变量：

```
FLASK_ENV=production
FLASK_DEBUG=False
CORS_ORIGINS=https://your-frontend-domain.com
```

**重要**：
- `PORT` 由 Railway 自动设置，不需要手动配置
- `CORS_ORIGINS` 应该设置为你的前端域名（Cloudflare Pages 域名）
- 多个域名用逗号分隔：`https://domain1.com,https://domain2.com`

### 可选的环境变量

```
HOST=0.0.0.0  # 默认值，通常不需要修改
```

## 💾 数据持久化配置

### 问题

Railway 使用临时存储，服务重启后 `qring_data.json` 会丢失。

### 解决方案

#### 方案1：使用 Railway Volume（推荐）

1. 在 Railway Dashboard 中：
   - 进入项目设置
   - 点击 "Volumes"
   - 创建新 Volume
   - 挂载到 `/app/data` 目录

2. 修改代码使用 Volume 路径：

```python
# 在 qring_api_server.py 中
import os

# 数据文件路径
DATA_DIR = os.getenv('DATA_DIR', '/app/data')
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR, exist_ok=True)

DATA_FILE = os.path.join(DATA_DIR, "qring_data.json")
```

3. 在 `railway.toml` 中添加 Volume 配置：

```toml
[volume]
mountPath = "/app/data"
```

#### 方案2：使用环境变量指定数据目录

```python
# 使用 Railway 提供的持久化目录
DATA_DIR = os.getenv('RAILWAY_VOLUME_MOUNT_PATH', './')
DATA_FILE = os.path.join(DATA_DIR, "qring_data.json")
```

#### 方案3：迁移到数据库（长期方案）

如果数据量大，建议迁移到 PostgreSQL：

- Railway 提供 PostgreSQL 插件
- 修改代码使用 SQLAlchemy 或直接使用 PostgreSQL

## 🚀 部署步骤

### 1. 在 Railway 创建项目

1. 访问 [Railway](https://railway.app)
2. 点击 "New Project"
3. 选择 "Deploy from GitHub repo"
4. 选择 `oscarka/Qring-backend` 仓库

### 2. 配置环境变量

在 Railway Dashboard → Variables 中添加：

```
FLASK_ENV=production
FLASK_DEBUG=False
CORS_ORIGINS=https://your-frontend.pages.dev
```

### 3. 配置 Volume（数据持久化）

1. 在 Railway Dashboard → Volumes
2. 创建新 Volume
3. 挂载到 `/app/data`

### 4. 部署

Railway 会自动：
- 检测 `railway.toml` 配置
- 安装依赖
- 启动服务
- 运行健康检查

### 5. 获取部署 URL

部署完成后，Railway 会提供一个 URL，例如：
```
https://qring-backend-production.up.railway.app
```

## 🔗 与 Cloudflare 集成

### 1. 创建 Cloudflare Worker（代理）

参考 `Cloudflare Workers代理配置.md`

### 2. 配置前端

在 Cloudflare Pages 环境变量中设置：

```
VITE_API_BASE=https://your-worker.workers.dev/api
```

或直接使用 Railway URL：

```
VITE_API_BASE=https://qring-backend-production.up.railway.app/api
```

### 3. 配置 iOS App

在 iOS App 中使用 Cloudflare Worker URL 或 Railway URL：

```objective-c
NSString *serverURL = @"https://your-worker.workers.dev";
// 或
NSString *serverURL = @"https://qring-backend-production.up.railway.app";
```

## 📊 监控和日志

### Railway Dashboard

- **Metrics**: CPU、内存使用情况
- **Logs**: 实时日志查看
- **Deployments**: 部署历史

### 健康检查

Railway 会自动检查 `/api/health` 端点：
- 每 30 秒检查一次
- 超时时间 10 秒
- 如果失败，会自动重启服务

## ⚠️ 注意事项

### 1. 数据备份

- 定期备份 `qring_data.json`
- 考虑设置自动备份脚本

### 2. 成本控制

- Railway $5/月套餐包含：
  - 512MB RAM
  - 1GB 存储
  - 100GB 流量
- 监控使用量，避免超出配额

### 3. 性能优化

- 如果数据量大，考虑迁移到数据库
- 添加缓存机制（Redis）
- 优化 API 响应时间

### 4. 安全性

- 生产环境必须使用 HTTPS（Railway 自动提供）
- 限制 CORS 来源
- 考虑添加 API 密钥验证

## 🐛 故障排查

### 问题1：服务无法启动

- 检查 `railway.toml` 配置
- 检查环境变量
- 查看 Railway 日志

### 问题2：数据丢失

- 检查 Volume 是否正确挂载
- 检查数据文件路径
- 确认 Volume 已创建

### 问题3：CORS 错误

- 检查 `CORS_ORIGINS` 环境变量
- 确保前端域名在允许列表中

### 问题4：健康检查失败

- 检查 `/api/health` 端点是否正常
- 检查服务是否正在运行
- 查看日志错误信息

## 📚 相关文档

- [Railway 官方文档](https://docs.railway.app)
- [Railway.toml 配置参考](https://docs.railway.app/develop/variables#railwaytoml)
- [后端部署指南.md](./后端部署指南.md)
- [Cloudflare Workers代理配置.md](./Cloudflare%20Workers代理配置.md)

