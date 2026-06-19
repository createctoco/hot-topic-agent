"""
今日头条自动发布模块
使用 node 直接运行 toutiao-ops/index.js，彻底绕过 npx 权限问题
"""
import json
import os
import subprocess
import logging
import struct
import zlib
from pathlib import Path

logger = logging.getLogger(__name__)

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

# 默认占位图路径（首次运行时生成）
PLACEHOLDER_COVER = PROJECT_ROOT / "data" / "assets" / "placeholder_cover.png"


def _create_placeholder_cover() -> Path:
    """创建一个1x1像素的红色PNG作为占位封面（不需要Pillow）"""
    PLACEHOLDER_COVER.parent.mkdir(parents=True, exist_ok=True)
    
    if PLACEHOLDER_COVER.exists():
        return PLACEHOLDER_COVER
    
    # 创建一个简单的1x1像素PNG（红色）
    width, height = 100, 100
    
    def make_png():
        # PNG 文件结构
        signature = b'\x89PNG\r\n\x1a\n'
        
        # IHDR chunk
        ihdr_data = struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)
        ihdr_crc = zlib.crc32(b'IHDR' + ihdr_data) & 0xffffffff
        ihdr_chunk = struct.pack('>I', 13) + b'IHDR' + ihdr_data + struct.pack('>I', ihdr_crc)
        
        # IDAT chunk (图像数据)
        raw_data = b''
        for y in range(height):
            raw_data += b'\x00'  # 过滤器字节
            for x in range(width):
                # 红色像素 (R=255, G=100, B=100)
                raw_data += bytes([255, 100, 100])
        
        compressed = zlib.compress(raw_data)
        idat_crc = zlib.crc32(b'IDAT' + compressed) & 0xffffffff
        idat_chunk = struct.pack('>I', len(compressed)) + b'IDAT' + compressed + struct.pack('>I', idat_crc)
        
        # IEND chunk
        iend_crc = zlib.crc32(b'IEND') & 0xffffffff
        iend_chunk = struct.pack('>I', 0) + b'IEND' + struct.pack('>I', iend_crc)
        
        return signature + ihdr_chunk + idat_chunk + iend_chunk
    
    png_data = make_png()
    with open(PLACEHOLDER_COVER, 'wb') as f:
        f.write(png_data)
    
    logger.info(f"已生成占位封面图: {PLACEHOLDER_COVER}")
    return PLACEHOLDER_COVER


class ToutiaoPublisher:
    def __init__(self, work_dir: str = "."):
        """
        初始化发布器
        work_dir: 工作目录（toutiao-ops 的安装目录）
        """
        self.work_dir = Path(work_dir).resolve()
        self._check_environment()
        # 确保占位封面存在
        _create_placeholder_cover()

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
        result = self._run_toutiao_cmd(["auth", "status"])
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

        参数:
            title: 文章标题
            content: 文章正文（HTML 格式）
            category: 领域分类
            first_publish: 是否声明头条首发
            ai_declared: 是否声明AI生成
            cover_keyword: 免费图库搜索关键词（暂未使用，原版不支持）

        返回: {"success": bool, "message": str}
        """
        # 1. 保存正文到临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", suffix=".html", delete=False) as f:
            content_file = f.name
            f.write(content)
        logger.info(f"正文已保存到: {content_file}")

        # 2. 确保封面图存在（toutiao-ops 必须要有 --cover 参数）
        cover_path = str(PLACEHOLDER_COVER)
        if not os.path.exists(cover_path):
            cover_path = str(_create_placeholder_cover())

        # 3. 构建命令参数
        args = ["publish", "article"]
        args += ["--title", title]
        args += ["--content-file", content_file]
        args += ["--cover", cover_path]  # 必须要有封面图

        if first_publish:
            args.append("--first-publish")

        if ai_declared:
            args.append("--ai-declared")

        # 注意：原版 toutiao-ops 不支持 --cover-free 和 --cover-keyword
        # 如果需要使用免费图库，需要在发布后手动在头条后台更换封面

        # 4. 执行发布命令
        logger.info(f"发布文章: [{category}] {title}")
        result = self._run_toutiao_cmd(args, timeout=180)

        # 5. 清理临时文件
        try:
            os.unlink(content_file)
        except:
            pass

        return result
