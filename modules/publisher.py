"""
今日头条自动发布模块
通过 toutiao-ops (Node.js + Playwright) 自动发布文章
"""
import subprocess
import json
import os
import logging
import time
from typing import Dict, Optional

logger = logging.getLogger(__name__)

# Node.js 和 npx 路径
NODE_PATH = os.environ.get("NODE_PATH", "node")
NPX_PATH = os.environ.get("NPX_PATH", "npx")

# toutiao-ops 命令前缀
TOUTIAO_CMD = "npx @openclaw-cn/toutiao-ops"


class ToutiaoPublisher:
    def __init__(self, work_dir: str = "."):
        """
        初始化发布器
        work_dir: 工作目录（toutiao-ops 的安装目录）
        """
        self.work_dir = work_dir
        self._check_environment()

    def _check_environment(self):
        """检查 Node.js 和 toutiao-ops 环境"""
        try:
            result = subprocess.run(
                [NODE_PATH, "--version"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                logger.info(f"Node.js: {result.stdout.strip()}")
            else:
                logger.warning("Node.js 未安装或不可用")
        except Exception as e:
            logger.warning(f"检查 Node.js 失败: {e}")

    def _run_cmd(self, args: list, timeout: int = 120) -> Dict:
        """运行 toutiao-ops 命令"""
        cmd = [NPX_PATH] + ["@openclaw-cn/toutiao-ops"] + args
        logger.info(f"执行命令: {' '.join(cmd)}")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.work_dir,
                capture_output=True,
                text=True,
                timeout=timeout,
                shell=False,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode,
            }
        except subprocess.TimeoutExpired:
            logger.error("命令超时")
            return {"success": False, "error": "timeout"}
        except Exception as e:
            logger.error(f"命令执行失败: {e}")
            return {"success": False, "error": str(e)}

    def login(self) -> bool:
        """
        登录今日头条（首次需要扫码）
        运行后会弹出浏览器，用手机扫码登录
        """
        logger.info("正在启动登录流程，请用手机扫码...")
        result = self._run_cmd(["auth", "login"], timeout=300)

        if result.get("success"):
            logger.info("登录成功！")
            return True
        else:
            logger.error(f"登录失败: {result.get('stderr', result.get('error', 'unknown'))}")
            return False

    def check_login(self) -> bool:
        """检查登录状态"""
        result = self._run_cmd(["auth", "status"], timeout=30)
        return result.get("success", False)

    def publish_article(
        self,
        title: str,
        content: str,
        category: str = "",
        first_publish: bool = True,
        ai_generated: bool = True,
        cover_images: list = None,
    ) -> Dict:
        """
        发布文章到今日头条

        参数:
            title: 文章标题
            content: 文章正文（HTML格式）
            category: 领域分类
            first_publish: 是否声明头条首发
            ai_generated: 是否声明AI生成
            cover_images: 封面图URL列表（最多3张）

        返回: {"success": bool, "message": str}
        """
        # 构建命令参数
        args = [
            "publish", "article",
            "--title", title,
            "--content", content,
        ]

        if first_publish:
            args.append("--first-publish")

        if ai_generated:
            args.append("--ai-declared")

        if cover_images:
            for i, img in enumerate(cover_images[:3]):
                args.extend([f"--cover-{i+1}", img])

        logger.info(f"发布文章: [{category}] {title}")

        # 内容可能很长，用文件传递
        content_file = os.path.join(self.work_dir, "data", "cache", "_article_content.html")
        os.makedirs(os.path.dirname(content_file), exist_ok=True)

        with open(content_file, "w", encoding="utf-8") as f:
            f.write(content)

        # 用文件方式传递内容
        args = [
            "publish", "article",
            "--title", title,
            "--content-file", os.path.abspath(content_file),
        ]

        if first_publish:
            args.append("--first-publish")
        if ai_generated:
            args.append("--ai-declared")

        result = self._run_cmd(args, timeout=180)

        if result.get("success"):
            logger.info(f"发布成功: {title}")
            return {"success": True, "message": "发布成功"}
        else:
            error_msg = result.get("stderr", result.get("error", "未知错误"))
            logger.error(f"发布失败: {error_msg}")
            return {"success": False, "message": error_msg}

    def publish_micro(self, content: str) -> Dict:
        """
        发布微头条
        """
        args = ["publish", "micro", "--content", content]
        result = self._run_cmd(args, timeout=120)

        if result.get("success"):
            return {"success": True, "message": "微头条发布成功"}
        else:
            return {"success": False, "message": result.get("stderr", "发布失败")}


def publish_via_node_script(
    title: str,
    content: str,
    work_dir: str = ".",
    first_publish: bool = True,
    ai_declared: bool = True,
) -> Dict:
    """
    通过自定义 Node.js 脚本发布文章
    更灵活的方式，可以处理复杂的发布逻辑
    """
    script_path = os.path.join(os.path.dirname(__file__), "..", "publish_helper.js")

    # 将文章内容写入临时文件
    content_file = os.path.join(work_dir, "data", "cache", "_publish_content.json")
    os.makedirs(os.path.dirname(content_file), exist_ok=True)

    article_data = {
        "title": title,
        "content": content,
        "first_publish": first_publish,
        "ai_declared": ai_declared,
    }

    with open(content_file, "w", encoding="utf-8") as f:
        json.dump(article_data, f, ensure_ascii=False)

    try:
        result = subprocess.run(
            [NODE_PATH, script_path, os.path.abspath(content_file)],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=180,
        )

        if result.returncode == 0:
            return {"success": True, "message": "发布成功"}
        else:
            return {"success": False, "message": result.stderr or "发布失败"}
    except Exception as e:
        return {"success": False, "message": str(e)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    publisher = ToutiaoPublisher(work_dir=".")

    # 检查登录状态
    if publisher.check_login():
        print("已登录")
    else:
        print("未登录，请运行: publisher.login()")
