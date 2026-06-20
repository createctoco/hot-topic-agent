"""
今日头条自动发布模块
使用 node 直接运行 toutiao-ops/index.js，彻底绕过 npx 权限问题
支持头条免费图库配图
"""
import json
import os
import subprocess
import logging
import base64
from pathlib import Path

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 1x1 像素 JPEG 的 base64 数据（用于满足 --cover 必填参数）
# 实际封面由 --cover-mode free 从头条免费图库选取，此图片不会被使用
PLACEHOLDER_JPEG_B64 = "/9j/4AAQSkZJRgABAQEAYABgAAD/2wBDAP//////////////////////////////////////////////////////////////////////////////////////2wBDAf//////////////////////////////////////////////////////////////////////////////////////wAARCAABAAEDASIAAhEBAxEB/8QAFQABAQAAAAAAAAAAAAAAAAAAAAr/xAAUEAEAAAAAAAAAAAAAAAAAAAAA/8QAFAEBAAAAAAAAAAAAAAAAAAAAAP/EABQRAQAAAAAAAAAAAAAAAAAAAAD/2gAMAwEAAhEDEQA/AL+AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/9k="


def _ensure_placeholder_image() -> str:
    """生成占位图片文件，返回路径"""
    img_path = PROJECT_ROOT / "data" / "placeholder.jpg"
    img_path.parent.mkdir(parents=True, exist_ok=True)
    if not img_path.exists():
        img_data = base64.b64decode(PLACEHOLDER_JPEG_B64)
        img_path.write_bytes(img_data)
    return str(img_path)


class ToutiaoPublisher:
    def __init__(self, work_dir: str = "."):
        """
        初始化发布器
        work_dir: 工作目录（toutiao-ops 的安装目录）
        """
        self.work_dir = Path(work_dir).resolve()
        self._check_environment()

    def _check_environment(self):
        """检查运行环境"""
        # 检查 node 是否可用
        try:
            result = subprocess.run(
                ["node", "--version"],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Node.js: {result.stdout.strip()}")
        except (subprocess.CalledProcessError, FileNotFoundError):
            raise RuntimeError("Node.js 未安装，请先安装 Node.js")

        # 检查 toutiao-ops 是否安装
        toutiao_js = self.work_dir / "node_modules" / "@openclaw-cn" / "toutiao-ops" / "index.js"
        if not toutiao_js.exists():
            logger.warning(f"toutiao-ops 未安装，正在安装...")
            subprocess.run(
                ["npm", "install", "@openclaw-cn/toutiao-ops"],
                cwd=self.work_dir,
                check=True,
            )
            logger.info("toutiao-ops 安装完成")

    def _run_toutiao_cmd(self, args: list, timeout: int = 120) -> dict:
        """
        运行 toutiao-ops 命令（用 node 直接运行 index.js，绕过 npx 权限问题）
        """
        index_js = self.work_dir / "node_modules" / "@openclaw-cn" / "toutiao-ops" / "index.js"

        if not index_js.exists():
            return {"success": False, "message": f"toutiao-ops 未找到: {index_js}"}

        cmd = ["node", str(index_js)] + args
        logger.info(f"执行命令: {' '.join(cmd[:3])} ...")

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.work_dir,
            )
            output = result.stdout + result.stderr

            if result.returncode == 0:
                return {"success": True, "message": "命令执行成功", "output": output}
            else:
                return {"success": False, "message": output}

        except subprocess.TimeoutExpired:
            return {"success": False, "message": f"命令超时（{timeout}秒）"}
        except Exception as e:
            return {"success": False, "message": str(e)}

    def check_login(self) -> bool:
        """检查登录状态"""
        result = self._run_toutiao_cmd(["auth", "check"])
        return result["success"] and "已登录" in result.get("message", "")

    def publish_article(
        self,
        title: str,
        content: str,
        category: str = "",
        first_publish: bool = True,
        ai_declared: bool = True,
        cover_keyword: str = "",
    ) -> dict:
        """
        发布文章到今日头条（使用免费图库配图）

        参数:
            title: 文章标题
            content: 文章正文（HTML 格式）
            category: 领域分类
            first_publish: 是否声明头条首发
            ai_declared: 是否声明AI生成
            cover_keyword: 免费图库搜索关键词（中文，如"关税"、"芯片"）

        返回: {"success": bool, "message": str}
        """
        # 1. 保存正文到临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".html", delete=False) as f:
            content_file = f.name
            f.write(content)
        logger.info(f"正文已保存到: {content_file}")

        # 2. 生成占位图片（满足 --cover 必填，实际由 --cover-mode free 从免费图库选图）
        placeholder_path = _ensure_placeholder_image()

        # 3. 构建命令参数
        args = ["publish", "article"]
        args += ["--title", title]
        args += ["--content-file", content_file]
        args += ["--cover", placeholder_path]        # 占位图片，满足必填
        args += ["--cover-mode", "free"]             # 使用免费图库选图（覆盖占位图）
        fallback_keyword = title[:4] if title else "科技"
        keyword = cover_keyword if cover_keyword else fallback_keyword
        args += ["--cover-keyword", keyword]
        logger.info(f"使用免费图库，封面关键词: {keyword}")

        if first_publish:
            args.append("--first-publish")

        # AI声明：toutiao-ops 用 --declaration 参数
        if ai_declared:
            args += ["--declaration", "引用AI"]

        # CI/服务器环境需要无头模式
        if os.environ.get("NON_INTERACTIVE") or os.environ.get("CI"):
            args.append("--headless")
            logger.info("使用无头模式运行")

        # 4. 执行发布命令
        logger.info(f"发布文章: [{category}] {title}")
        result = self._run_toutiao_cmd(args, timeout=180)

        # 5. 清理临时文件
        try:
            os.unlink(content_file)
        except:
            pass

        return result
