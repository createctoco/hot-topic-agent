#!/bin/bash
# ============================================
# 本地登录头条 + 导出会话脚本
# 在本地电脑运行，登录后将 data/ 目录传到服务器
# ============================================

echo "========================================"
echo "  头条登录 - 本地执行"
echo "========================================"
echo ""
echo "此脚本在你的本地电脑上运行，打开浏览器扫码登录头条。"
echo "登录成功后，将 data/ 目录打包传到服务器即可。"
echo ""

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
cd "$PROJECT_DIR"

# 检查环境
if ! command -v python3 &>/dev/null && ! command -v python &>/dev/null; then
    echo "[错误] 未找到 Python，请先安装 Python 3"
    exit 1
fi

PYTHON=$(command -v python3 || command -v python)

# 检查依赖
echo ">>> 检查依赖..."
$PYTHON -c "import yaml, requests, openai" 2>/dev/null || {
    echo ">>> 安装 Python 依赖..."
    $PYTHON -m pip install -r requirements.txt
}

echo ">>> 检查 Node.js 依赖..."
if ! command -v npx &>/dev/null; then
    echo "[错误] 未找到 Node.js/npx，请先安装 Node.js 18+"
    exit 1
fi

npm install --production 2>/dev/null || npm install
npx playwright install chromium

echo ""
echo ">>> 启动登录流程..."
echo "    浏览器即将打开，请用手机头条 App 扫码登录"
echo ""

# 加载环境变量
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

$PYTHON main.py --login

echo ""
echo "========================================"
if [ $? -eq 0 ]; then
    echo "  登录成功！"
    echo "========================================"
    echo ""
    echo "会话数据保存在: $PROJECT_DIR/data/"
    echo ""
    echo "下一步：将会话数据传到服务器"
    echo ""
    echo "方法一（scp 直接传）："
    echo "  scp -r data/ root@你的服务器IP:$PROJECT_DIR/"
    echo ""
    echo "方法二（打包后传）："
    echo "  tar czf session.tar.gz data/"
    echo "  scp session.tar.gz root@你的服务器IP:/root/hot-topic-agent/"
    echo "  ssh root@你的服务器IP 'cd /root/hot-topic-agent && tar xzf session.tar.gz'"
    echo ""
    echo "方法三（宝塔面板上传）："
    echo "  1. 在宝塔面板文件管理中进入项目目录"
    echo "  2. 上传 data/ 目录覆盖"
    echo ""
else
    echo "  登录失败，请重试"
    echo "========================================"
fi
