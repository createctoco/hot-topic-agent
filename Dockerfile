# ============================================
# 热搜自动发文系统 - Docker 镜像
# 基于 Node.js + Playwright 官方镜像，内置浏览器
# ============================================
FROM node:20-bookworm-slim

# 安装 Python 3 + 系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    curl \
    git \
    fonts-wqy-zenhei \
    fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 先复制依赖文件，利用 Docker 缓存层
COPY package.json package-lock.json* ./
RUN npm install --production 2>/dev/null || npm install

# 安装 Playwright 浏览器 + 系统依赖
RUN npx playwright install --with-deps chromium

# 复制 Python 依赖并安装
COPY requirements.txt ./
RUN pip3 install --break-system-packages -r requirements.txt

# 复制项目文件
COPY . .

# 创建数据目录
RUN mkdir -p data/logs data/cache data/articles

# 设置环境变量
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app
ENV NON_INTERACTIVE=1

# 默认：执行一次发文
# 可通过 docker-compose 或 docker run 覆盖
CMD ["python3", "main.py", "--once"]
