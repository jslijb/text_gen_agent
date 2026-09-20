# backend/Dockerfile（spec v1.4.0：全量 Docker 化）
# FastAPI 后端 + Celery Worker 共用此镜像
FROM python:3.11-slim

# spec v1.4.0：使用国内镜像源加速（Debian + pip）
RUN sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || true && \
    sed -i 's|deb.debian.org|mirrors.aliyun.com|g' /etc/apt/sources.list 2>/dev/null || true

# 系统依赖（psycopg2、playwright 等）
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 先装依赖（利用 Docker 层缓存，使用清华镜像加速）
COPY requirements.txt .
# spec v1.4.0：先装 CPU-only torch，避免拉取 2GB+ CUDA 依赖（bge 嵌入模型 CPU 推理足够）
# torch 主体走 PyTorch CPU 索引；间接依赖（fsspec 等）回退到清华镜像
RUN pip install --no-cache-dir torch \
    --index-url https://download.pytorch.org/whl/cpu \
    --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple \
    --timeout 300
RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300

# 安装 playwright 浏览器（发布功能用，超时或失败不阻塞构建——国内 CDN 慢）
RUN timeout 180 playwright install chromium --with-deps || echo "playwright install skipped (timeout or error)"

# 复制后端代码
COPY . .

# 默认启动 FastAPI（worker 容器通过 docker-compose command 覆盖）
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
