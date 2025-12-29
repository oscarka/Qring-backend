# Qring Backend API Server

Qring 健康数据后端 API 服务器，接收来自 iOS App 的数据，并提供 REST API 接口供前端调用。

## 📋 功能特性

- ✅ 接收 iOS App 上传的健康数据（心率、HRV、压力、血氧、活动、睡眠等）
- ✅ 提供 REST API 接口供前端调用
- ✅ 数据持久化（JSON 文件存储）
- ✅ 数据去重和验证
- ✅ CORS 跨域支持
- ✅ 健康检查端点
- ✅ 详细的日志记录
- ✅ 客户端来源识别（区分 Web 前端和手机 App）

## 🚀 快速开始

### 环境要求

- Python 3.8+
- pip

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

复制 `env.example.backend` 为 `.env` 并修改配置：

```bash
cp env.example.backend .env
```

编辑 `.env` 文件：

```bash
# Flask 环境配置
FLASK_ENV=development
FLASK_DEBUG=True

# 服务器配置
HOST=0.0.0.0
PORT=5002

# CORS 配置（生产环境应限制来源）
CORS_ORIGINS=*
```

### 运行服务器

```bash
python qring_api_server.py
```

服务器将在 `http://localhost:5002` 启动。

## 📡 API 接口

### 数据上传接口（iOS App 使用）

- `POST /api/qring/upload` - 上传 Qring 数据

### 前端 API 接口

- `GET /api/health` - 健康检查
- `GET /api/stats` - 获取数据统计
- `GET /api/heartrate?hours=24` - 获取心率数据
- `GET /api/hrv?days=7` - 获取 HRV 数据
- `GET /api/stress?days=7` - 获取压力数据
- `GET /api/blood-oxygen?days=7` - 获取血氧数据
- `GET /api/daily-activity?days=30` - 获取活动数据
- `GET /api/sleep?days=30` - 获取睡眠数据
- `GET /api/exercise?days=30` - 获取运动记录
- `GET /api/sport-plus?days=30` - 获取运动+数据
- `GET /api/sedentary?days=30` - 获取久坐提醒数据
- `GET /api/manual-measurements?hours=24&type=realtime` - 获取主动测量数据
- `GET /api/user-info` - 获取用户信息
- `GET /api/target-info` - 获取目标设置

详细 API 文档请参考：[前端需求文档-第二部分-API接口规范.md](./前端需求文档-第二部分-API接口规范.md)

## 📁 项目结构

```
.
├── qring_api_server.py      # 主应用文件
├── requirements.txt          # Python 依赖
├── railway.toml              # Railway 配置文件（推荐）
├── Procfile                  # Railway 部署配置（备用）
├── Dockerfile                # Docker 部署配置
├── env.example.backend       # 环境变量示例
├── .env                      # 环境变量配置（不提交到 Git）
├── qring_data.json          # 数据存储文件（自动生成）
└── README.md                 # 本文件
```

## 🚢 部署

### Railway 部署（推荐）

1. 在 Railway 创建新项目
2. 连接 GitHub 仓库（`oscarka/Qring-backend`）
3. Railway 会自动检测 `railway.toml` 配置文件
4. 在 Railway Dashboard 配置环境变量：
   ```
   FLASK_ENV=production
   FLASK_DEBUG=False
   CORS_ORIGINS=https://your-frontend-domain.com
   ```
5. 配置 Volume 持久化存储（可选但推荐）

**详细部署指南请参考：**
- [Railway部署配置说明.md](./Railway部署配置说明.md)
- [后端部署指南.md](./后端部署指南.md)

### Google Cloud Run 部署

```bash
# 构建镜像
gcloud builds submit --tag gcr.io/$PROJECT_ID/qring-api

# 部署到 Cloud Run（选择亚洲区域以优化中国大陆访问）
gcloud run deploy qring-api \
  --image gcr.io/$PROJECT_ID/qring-api \
  --region asia-east1 \
  --platform managed \
  --allow-unauthenticated
```

### Docker 部署

```bash
# 构建镜像
docker build -t qring-api .

# 运行容器
docker run -p 5002:5002 --env-file .env qring-api
```

## 🔧 配置说明

### 环境变量

| 变量名 | 说明 | 默认值 | 必需 |
|--------|------|--------|------|
| `FLASK_ENV` | Flask 环境 | `development` | 否 |
| `FLASK_DEBUG` | 调试模式 | `False` | 否 |
| `HOST` | 监听地址 | `0.0.0.0` | 否 |
| `PORT` | 监听端口 | `5002` | 否 |
| `CORS_ORIGINS` | 允许的 CORS 来源 | `*` | 否 |

### 生产环境配置

```bash
FLASK_ENV=production
FLASK_DEBUG=False
HOST=0.0.0.0
PORT=5002
CORS_ORIGINS=https://your-frontend-domain.com
```

## 📊 数据存储

当前使用 JSON 文件存储（`qring_data.json`），适合小规模使用。

**注意**：
- Railway/Cloud Run 使用临时存储，数据会在重启后丢失
- 建议配置 Volume 持久化或迁移到数据库

## 🔒 安全性

- 生产环境必须使用 HTTPS
- 限制 CORS 来源，不要使用 `*`
- 考虑添加 API 密钥验证（可选）

## 📝 日志

服务器会输出详细的日志，包括：
- 数据接收日志
- API 请求日志
- 客户端来源识别
- 数据统计信息

## 🐛 故障排查

### 问题1：端口被占用

```bash
# 检查端口占用
lsof -i :5002

# 修改 PORT 环境变量或代码中的端口号
```

### 问题2：CORS 错误

- 检查 `CORS_ORIGINS` 环境变量
- 确保前端域名在允许列表中

### 问题3：数据丢失

- Railway/Cloud Run 使用临时存储
- 需要配置持久化存储或迁移到数据库

## 📚 相关文档

- [后端部署指南.md](./后端部署指南.md)
- [后端部署就绪检查报告.md](./后端部署就绪检查报告.md)
- [后端平台对比分析-中国大陆用户.md](./后端平台对比分析-中国大陆用户.md)
- [前端需求文档-第二部分-API接口规范.md](./前端需求文档-第二部分-API接口规范.md)

## 📄 许可证

MIT License

## 👥 贡献

欢迎提交 Issue 和 Pull Request！
