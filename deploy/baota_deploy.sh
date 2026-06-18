#!/bin/bash
# ============================================
# 宝塔面板部署脚本 - 热搜自动发文系统
# 在宝塔面板终端中运行：bash baota_deploy.sh
# ============================================
set -e

echo "========================================"
echo "  热搜自动发文系统 - 宝塔面板部署"
echo "========================================"

# 项目目录（脚本所在目录的上级）
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"
echo "项目目录: $PROJECT_DIR"

# ====== 1. 检查并安装 Python 3 ======
echo ""
echo ">>> [1/6] 检查 Python 3..."
if command -v python3 &>/dev/null; then
    PYTHON_VERSION=$(python3 --version 2>&1)
    echo "    Python 已安装: $PYTHON_VERSION"
else
    echo "    安装 Python 3..."
    yum install -y python3 python3-pip || apt-get install -y python3 python3-pip
fi

# ====== 2. 检查并安装 Node.js ======
echo ""
echo ">>> [2/6] 检查 Node.js..."
if command -v node &>/dev/null; then
    NODE_VERSION=$(node --version 2>&1)
    echo "    Node.js 已安装: $NODE_VERSION"
else
    echo "    安装 Node.js 20..."
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - || \
    curl -fsSL https://rpm.nodesource.com/setup_20.x | bash -
    apt-get install -y nodejs || yum install -y nodejs
fi

# ====== 3. 安装 Python 依赖 ======
echo ""
echo ">>> [3/6] 安装 Python 依赖..."
python3 -m pip install -r requirements.txt -q
echo "    Python 依赖安装完成"

# ====== 4. 安装 Node.js 依赖 + Playwright ======
echo ""
echo ">>> [4/6] 安装 Node.js 依赖和 Playwright..."
npm install --production 2>/dev/null || npm install
npx playwright install --with-deps chromium
echo "    Playwright 浏览器安装完成"

# ====== 5. 配置环境变量 ======
echo ""
echo ">>> [5/6] 配置环境变量..."

# 读取 DeepSeek API Key
if [ -f .env ]; then
    echo "    .env 文件已存在，跳过"
else
    echo "    请输入 DeepSeek API Key (从 https://platform.deepseek.com/ 获取):"
    read -r API_KEY
    cat > .env << EOF
DEEPSEEK_API_KEY=$API_KEY
NON_INTERACTIVE=1
TZ=Asia/Shanghai
EOF
    echo "    .env 已创建"
fi

# 创建数据目录
mkdir -p data/logs data/cache data/articles

# ====== 6. 安装 PM2 进程管理器 ======
echo ""
echo ">>> [6/6] 配置 PM2 进程管理..."
if command -v pm2 &>/dev/null; then
    echo "    PM2 已安装"
else
    npm install -g pm2
fi

# 创建 PM2 配置文件
cat > ecosystem.config.cjs << 'EOF'
module.exports = {
  apps: [{
    name: "hot-topic-agent",
    script: "main.py",
    interpreter: "python3",
    cwd: __dirname,
    env: {
      NON_INTERACTIVE: "1",
      TZ: "Asia/Shanghai",
    },
    env_file: ".env",
    max_restarts: 10,
    restart_delay: 5000,
    error_file: "./data/logs/pm2-error.log",
    out_file: "./data/logs/pm2-out.log",
    log_date_format: "YYYY-MM-DD HH:mm:ss",
  }]
};
EOF

echo ""
echo "========================================"
echo "  部署完成！"
echo "========================================"
echo ""
echo "后续步骤："
echo ""
echo "1. 首次登录头条（在服务器上执行）："
echo "   source .env && python3 main.py --login"
echo "   （会弹出浏览器扫码，如果没有桌面环境，请在本地登录后复制 data/ 目录到服务器）"
echo ""
echo "2. 启动定时调度："
echo "   pm2 start ecosystem.config.cjs"
echo ""
echo "3. 查看运行状态："
echo "   pm2 status"
echo "   pm2 logs hot-topic-agent"
echo ""
echo "4. 设置开机自启："
echo "   pm2 save"
echo "   pm2 startup"
echo ""
echo "5. 手动执行一次（测试）："
echo "   source .env && python3 main.py --once --count 1"
echo ""
