"""
今日头条自动发布模块
使用 node 直接运行 toutiao-ops/index.js，彻底绕过 npx 权限问题
自适应 toutiao-ops 不同版本的参数差异
"""
import json
import os
import subprocess
import logging
import base64
import re
from pathlib import Path

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 1x1 像素 JPEG 的 base64 数据（用于满足 --cover 必填参数）
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
        self._supported_opts = None  # 缓存 --help 解析结果
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
                ["npm", "install", "@openclaw-cn/toutiao-ops@1.1.4"],
                cwd=self.work_dir,
                check=True,
            )
            logger.info("toutiao-ops 安装完成")

    def _get_index_js(self) -> Path:
        return self.work_dir / "node_modules" / "@openclaw-cn" / "toutiao-ops" / "index.js"

    def _run_toutiao_cmd(self, args: list, timeout: int = 120) -> dict:
        """运行 toutiao-ops 命令（用 node 直接运行 index.js，绕过 npx 权限问题）"""
        index_js = self._get_index_js()
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

    def _get_supported_options(self) -> set:
        """
        查询 publish article --help，返回当前版本支持的所有选项名称。
        自适应不同版本的 toutiao-ops，不再硬编码参数。
        """
        if self._supported_opts is not None:
            return self._supported_opts

        result = self._run_toutiao_cmd(["publish", "article", "--help"], timeout=30)
        output = result.get("message", "") + result.get("output", "")

        # 匹配 --option 格式
        opts = set(re.findall(r'--([a-zA-Z][\w-]*)', output))
        logger.info(f"toutiao-ops publish article 支持的参数: {sorted(opts)}")

        self._supported_opts = opts
        return opts

    def _has_opt(self, name: str) -> bool:
        """检查当前版本是否支持某个参数"""
        return name in self._get_supported_options()

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
        发布文章到今日头条
        自适应 toutiao-ops 版本，根据 --help 动态选择可用参数
        """
        # 1. 保存正文到临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".html", delete=False) as f:
            content_file = f.name
            f.write(content)
        logger.info(f"正文已保存到: {content_file}")

        # 2. 生成占位图片
        placeholder_path = _ensure_placeholder_image()

        # 3. 查询当前版本支持的参数
        opts = self._get_supported_options()

        # 4. 构建命令参数 —— 只传支持的参数
        args = ["publish", "article"]
        args += ["--title", title]
        args += ["--content-file", content_file]

        # 封面：始终传 --cover 占位图（满足必填）
        if "cover" in opts:
            args += ["--cover", placeholder_path]
            logger.info(f"传 --cover 占位图: {placeholder_path}")

        # 免费图库：根据版本选可用方式
        if "cover-free" in opts:
            # 旧版本/本地版本：--cover-free 是 flag
            args.append("--cover-free")
            logger.info("使用 --cover-free flag（免费图库）")
        elif "cover-mode" in opts:
            # CI 版本：--cover-mode free
            args += ["--cover-mode", "free"]
            logger.info("使用 --cover-mode free（免费图库）")

        # 封面关键词：只有支持时才传
        fallback_keyword = title[:4] if title else "科技"
        keyword = cover_keyword if cover_keyword else fallback_keyword
        if "cover-keyword" in opts:
            args += ["--cover-keyword", keyword]
            logger.info(f"封面关键词: {keyword}")
        else:
            logger.info(f"当前版本不支持 --cover-keyword，跳过（关键词: {keyword}）")

        # 头条首发
        if first_publish and "first-publish" in opts:
            args.append("--first-publish")

        # AI声明
        if ai_declared and "declaration" in opts:
            args += ["--declaration", "引用AI"]
        elif ai_declared and "ai-declared" in opts:
            args.append("--ai-declared")

        # 无头模式
        if os.environ.get("NON_INTERACTIVE") or os.environ.get("CI"):
            if "headless" in opts:
                args.append("--headless")
                logger.info("使用无头模式运行")

        # 5. 执行发布命令
        logger.info(f"发布文章: [{category}] {title}")
        logger.info(f"完整参数: {args}")
        result = self._run_toutiao_cmd(args, timeout=180)

        # 6. 清理临时文件
        try:
            os.unlink(content_file)
        except:
            pass

        return result
