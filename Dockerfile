# 使用官方 Python 运行时作为基础镜像
FROM python:3.11-slim

# 设置工作目录
WORKDIR /app

# 复制依赖文件
COPY requirements.txt .

# 安装依赖
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY qring_api_server.py .
# 复制环境变量示例文件
COPY env.example.backend ./

# 创建数据目录（用于持久化数据文件）
RUN mkdir -p /app/data

# 暴露端口（Railway/Cloud Run 会自动映射）
EXPOSE 5002

# 设置环境变量
ENV FLASK_ENV=production
ENV FLASK_DEBUG=False
ENV PORT=5002
ENV HOST=0.0.0.0

# 运行应用
CMD ["python", "qring_api_server.py"]

