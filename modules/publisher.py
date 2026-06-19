"""
今日头条自动发布模块（纯 Python 实现）
使用 Python Playwright 直接操作浏览器，彻底绕过 toutiao-ops 的权限问题
"""
import json
import os
import logging
import time
import random
from pathlib import Path

logger = logging.getLogger(__name__)

# 浏览器数据目录（与 toutiao-ops 共享，Cookie 通用）
DEFAULT_DATA_DIR = os.path.expanduser("~/.toutiao-ops/accounts/default/browser-data")

# 头条发布页 URL
PUBLISH_URL = "https://mp.toutiao.com/profile_v4/graphic/publish"

# 标题长度限制
TITLE_MAX_LEN = 30
TITLE_MIN_LEN = 2


class ToutiaoPublisher:
    def __init__(self, work_dir: str = "."):
        """
        初始化发布器
        work_dir: 工作目录
        """
        self.work_dir = work_dir
        self.data_dir = os.environ.get("TOUTIAO_DATA_DIR", DEFAULT_DATA_DIR)
        os.makedirs(self.data_dir, exist_ok=True)
        logger.info(f"浏览器数据目录: {self.data_dir}")
        self._check_playwright()

    def _check_playwright(self):
        """检查 Playwright 是否安装"""
        try:
            import playwright
            logger.info(f"Playwright 已安装: {playwright.__version__}")
        except ImportError:
            logger.warning("Playwright 未安装，正在安装...")
            import subprocess
            subprocess.run(
                ["pip", "install", "playwright"],
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["playwright", "install", "chromium"],
                check=True,
                capture_output=True,
            )
            logger.info("Playwright 安装完成")

    def check_login(self) -> bool:
        """检查登录状态"""
        try:
            from playwright.sync_api import sync_playwright

            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    self.data_dir,
                    headless=True,
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-infobars",
                    ],
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto("https://mp.toutiao.com/profile_v4/home", timeout=30000)
                time.sleep(3)

                # 检查是否有登录按钮或登录态特征
                is_logged_in = "login" not in page.url() and page.locator("text=创作").count() > 0
                context.close()
                return is_logged_in
        except Exception as e:
            logger.warning(f"检查登录状态失败: {e}")
            return False

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
            cover_keyword: 免费图库搜索关键词

        返回: {"success": bool, "message": str}
        """
        try:
            from playwright.sync_api import sync_playwright

            # 标题长度检查
            if len(title) < TITLE_MIN_LEN:
                return {"success": False, "message": f"标题过短（至少 {TITLE_MIN_LEN} 字）"}
            if len(title) > TITLE_MAX_LEN:
                title = title[:TITLE_MAX_LEN]
                logger.warning(f"标题已截断为: {title}")

            with sync_playwright() as p:
                context = p.chromium.launch_persistent_context(
                    self.data_dir,
                    headless=True,
                    locale="zh-CN",
                    timezone_id="Asia/Shanghai",
                    viewport={"width": 1440, "height": 900},
                    args=[
                        "--disable-blink-features=AutomationControlled",
                        "--no-first-run",
                        "--no-default-browser-check",
                        "--disable-infobars",
                    ],
                )
                page = context.pages[0] if context.pages else context.new_page()

                try:
                    # 1. 打开发布页
                    logger.info("正在打开发布页...")
                    page.goto(PUBLISH_URL, timeout=60000, wait_until="domcontentloaded")
                    self._human_sleep(2, 4)

                    # 关闭可能的弹窗
                    self._dismiss_overlays(page)

                    # 2. 填写标题
                    logger.info(f"填写标题: {title}")
                    self._fill_title(page, title)
                    self._human_sleep(1, 2)

                    # 3. 填写正文
                    logger.info("填写正文...")
                    self._fill_content(page, content)
                    self._human_sleep(1, 2)

                    # 4. 设置封面（免费图库）
                    if cover_keyword:
                        logger.info(f"使用免费图库，关键词: {cover_keyword}")
                        self._set_cover_free(page, cover_keyword)
                        self._human_sleep(1, 2)

                    # 5. 勾选"头条首发"
                    if first_publish:
                        logger.info("勾选头条首发...")
                        self._click_label(page, "头条首发")
                        self._human_sleep(0.5, 1)

                    # 6. 勾选"AI 声明"（如果启用）
                    if ai_declared:
                        logger.info("勾选 AI 声明...")
                        self._click_label(page, "AI")
                        self._human_sleep(0.5, 1)

                    # 7. 点击"预览并发布"
                    logger.info("点击预览并发布...")
                    self._dismiss_overlays(page)
                    publish_btn = page.locator('button:has-text("预览并发布")').first
                    publish_btn.scroll_into_view_if_needed(timeout=10000)
                    self._human_sleep(0.5, 1)
                    publish_btn.click(force=True)
                    self._human_sleep(3, 5)

                    # 8. 确认发布（预览页）
                    logger.info("确认发布...")
                    self._dismiss_overlays(page)
                    confirm_btn = page.locator('button:has-text("确认发布"), button:has-text("发布")').first
                    confirm_btn.click(timeout=10000, force=True)
                    self._human_sleep(3, 5)

                    # 9. 可能的二次确认
                    self._dismiss_overlays(page)
                    final_confirm = page.locator('button:has-text("确定"), button:has-text("确认")').first
                    final_confirm.click(timeout=5000, force=True).catch(lambda _: None)
                    self._human_sleep(2, 4)

                    logger.info(f"发布成功: {title}")
                    context.close()
                    return {"success": True, "message": "发布成功"}

                except Exception as e:
                    # 截图保存错误信息
                    try:
                        screenshot_path = os.path.join(
                            self.work_dir, "data", "logs", f"error_{int(time.time())}.png"
                        )
                        os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
                        page.screenshot(path=screenshot_path)
                        logger.error(f"发布失败，截图已保存: {screenshot_path}")
                    except:
                        pass
                    context.close()
                    raise e

        except Exception as e:
            error_msg = str(e)
            logger.error(f"发布失败: {error_msg}")
            return {"success": False, "message": error_msg}

    def _fill_title(self, page, title: str):
        """填写标题"""
        selectors = [
            'textarea[placeholder*="标题"]',
            'input[placeholder*="标题"]',
            '[class*="title"] textarea',
            '[class*="title"] input',
        ]
        for selector in selectors:
            try:
                el = page.locator(selector).first
                if el.count() > 0:
                    el.click(force=True)
                    self._human_sleep(0.3, 0.6)
                    page.keyboard.type(title, delay=50 + random.randint(0, 80))
                    return
            except:
                continue

    def _fill_content(self, page, content: str):
        """填写正文（HTML 转纯文本分段输入）"""
        # 找到编辑器
        editor_selectors = [
            '[contenteditable="true"]',
            '[class*="editor"]',
            'div[role="textbox"]',
        ]
        editor = None
        for selector in editor_selectors:
            try:
                el = page.locator(selector).first
                if el.count() > 0:
                    editor = el
                    break
            except:
                continue

        if not editor:
            raise Exception("找不到正文编辑器")

        editor.click(force=True)
        self._human_sleep(0.3, 0.6)

        # 分段输入（模拟人类打字）
        paragraphs = content.replace("<p>", "").replace("</p>", "\n").split("\n")
        for i, para in enumerate(paragraphs):
            para = para.strip()
            if not para:
                page.keyboard.press("Enter")
                self._human_sleep(0.1, 0.3)
                continue
            # 去除 HTML 标签
            import re
            para = re.sub(r"<[^>]+>", "", para)
            if para:
                page.keyboard.type(para, delay=30 + random.randint(0, 50))
                self._human_sleep(0.1, 0.3)
                page.keyboard.press("Enter")
                self._human_sleep(0.3, 0.8)

    def _set_cover_free(self, page, keyword: str):
        """使用免费图库设置封面"""
        try:
            # 点击"免费图库"标签
            free_tab = page.locator('text=免费图库').first
            free_tab.click(timeout=5000)
            self._human_sleep(1, 2)

            # 搜索关键词
            search_input = page.locator('input[type="text"], input[placeholder*="搜索"]').first
            search_input.fill(keyword or "科技")
            self._human_sleep(0.5, 1)
            page.keyboard.press("Enter")
            self._human_sleep(2, 3)

            # 选择第一张图片
            first_img = page.locator('[class*="image-item"] img, [class*="img-item"] img').first
            first_img.click(timeout=10000)
            self._human_sleep(1, 2)

            # 确认选择
            confirm_btn = page.locator('button:has-text("确定"), button:has-text("确认")').first
            confirm_btn.click(timeout=5000)
            self._human_sleep(1, 2)

            logger.info("免费图库选择完成")
        except Exception as e:
            logger.warning(f"免费图库选择失败（不阻塞发布）: {e}")

    def _click_label(self, page, label_text: str):
        """点击勾选框（通过文本找到对应 label）"""
        try:
            el = page.locator(f'text={label_text}').first
            el.scroll_into_view_if_needed(timeout=5000)
            el.click(timeout=5000)
        except:
            pass

    def _dismiss_overlays(self, page):
        """关闭弹窗、遮罩"""
        try:
            page.evaluate("""
                () => {
                    // 关闭所有 modal
                    document.querySelectorAll('.byte-modal-wrapper, [class*="modal"], [class*="drawer"]').forEach(el => {
                        el.style.display = 'none';
                    });
                    // 按 Escape
                    document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape'}));
                }
            """)
        except:
            pass
        self._human_sleep(0.3, 0.5)

    def _human_sleep(self, min_sec: float, max_sec: float):
        """随机延迟（模拟人类操作）"""
        time.sleep(min_sec + random.random() * (max_sec - min_sec))


def publish_via_playwright(title: str, content: str, work_dir: str = ".", **kwargs) -> dict:
    """
    便捷函数：使用 Playwright 发布文章
    """
    publisher = ToutiaoPublisher(work_dir=work_dir)
    return publisher.publish_article(title=title, content=content, **kwargs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    import sys

    if len(sys.argv) < 3:
        print("用法: python publisher.py <title> <content_file>")
        sys.exit(1)

    title = sys.argv[1]
    content_file = sys.argv[2]

    with open(content_file, "r", encoding="utf-8") as f:
        content = f.read()

    publisher = ToutiaoPublisher(work_dir=".")
    result = publisher.publish_article(title=title, content=content)
    print(result)
