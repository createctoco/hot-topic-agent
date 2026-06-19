"""
AI文章生成模块
使用 DeepSeek API 生成头条文章
"""
import json
import time
import logging
from typing import Dict, Optional
from openai import OpenAI

logger = logging.getLogger(__name__)

# 领域写作风格
CATEGORY_STYLES = {
    "跨境电商": {
        "perspective": "跨境电商从业者/行业观察者",
        "tone": "专业、实用、有洞察",
        "focus": "行业趋势、平台政策、选品策略、运营技巧、出海机会",
    },
    "外贸": {
        "perspective": "资深外贸人/国际贸易分析师",
        "tone": "务实、经验丰富、接地气",
        "focus": "贸易政策影响、市场变化、接单技巧、风险规避、实战经验",
    },
    "AI": {
        "perspective": "科技博主/AI应用达人",
        "tone": "前沿、清晰、通俗易懂",
        "focus": "技术解读、应用场景、行业影响、工具推荐、未来趋势",
    },
    "科技": {
        "perspective": "科技媒体分析师",
        "tone": "客观、深度、有观点",
        "focus": "技术突破、产业影响、竞争格局、市场前景、国产化进程",
    },
}


class AIWriter:
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com"):
        """
        初始化 DeepSeek API 客户端
        api_key: DeepSeek API密钥
        base_url: API地址（默认 https://api.deepseek.com）
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = "deepseek-chat"
        logger.info("AI Writer 初始化完成 (DeepSeek)")

    def _call_api(self, messages: list, max_tokens: int = 4096, temperature: float = 0.8) -> str:
        """调用 DeepSeek API"""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False,
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.warning(f"API调用失败 (第{attempt+1}次): {e}")
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))  # 指数退避
                else:
                    raise

    def generate_title(self, hot_title: str, category: str) -> str:
        """
        根据热搜关键词生成文章标题
        """
        style = CATEGORY_STYLES.get(category, CATEGORY_STYLES["科技"])

        prompt = f"""你是今日头条的{style['perspective']}，请根据以下热搜关键词，生成一个吸引人的文章标题。

热搜关键词：{hot_title}
领域：{category}

要求：
1. 标题15-30字，不要太长
2. 要有信息量，让人想点开看
3. 不要标题党，不要夸张
4. 不要用感叹号
5. 只返回标题本身，不要引号、不要序号、不要其他内容

生成标题："""

        messages = [
            {"role": "system", "content": f"你是一个专业的今日头条{category}领域创作者，擅长写有深度的文章标题。"},
            {"role": "user", "content": prompt},
        ]

        title = self._call_api(messages, max_tokens=100, temperature=0.9)
        # 清理标题
        title = title.strip().strip('"').strip("'").strip("《》").strip("【】")
        # 去掉可能的前缀序号
        title = title.lstrip("1234567890.、) ")
        logger.info(f"生成标题: {title}")
        return title

    def generate_article(self, hot_title: str, category: str, platform: str = "") -> Dict:
        """
        根据热搜关键词生成完整文章
        返回: {"title": str, "content": str, "category": str}
        """
        style = CATEGORY_STYLES.get(category, CATEGORY_STYLES["科技"])

        # 先生成标题
        title = self.generate_title(hot_title, category)

        # 生成正文
        content_prompt = f"""你是今日头条的{style['perspective']}，请围绕以下热搜话题，写一篇深度文章。

热搜话题：{hot_title}（来源：{platform}）
领域：{category}
写作风格：{style['tone']}
重点关注：{style['focus']}

文章要求：
1. 字数2000-3000字
2. 结构清晰，使用小标题分段
3. 开头要吸引人，用一段话引出话题
4. 中间要有数据、案例、分析
5. 结尾要有观点总结和展望
6. 语言要通俗易懂，避免过于学术
7. 不要写"编者按""导语"等元信息
8. 直接写正文内容

文章内容："""

        messages = [
            {"role": "system", "content": f"你是一个专业的今日头条{category}领域创作者，擅长写有深度、有观点的文章。你的文章风格{style['tone']}。"},
            {"role": "user", "content": content_prompt},
        ]

        logger.info(f"正在生成文章: [{category}] {title}")
        content = self._call_api(messages, max_tokens=4096, temperature=0.85)

        # 将正文转为适合头条发布的HTML格式
        html_content = self._format_to_html(title, content, category)

        result = {
            "title": title,
            "content": html_content,
            "raw_content": content,
            "category": category,
            "source_topic": hot_title,
            "image_keywords": self._generate_image_keywords(hot_title, category),
        }

        logger.info(f"文章生成完成: {title} ({len(content)}字)")
        return result

    def _generate_image_keywords(self, hot_title: str, category: str) -> list:
        """让AI生成3个配图关键词（中文，适配头条免费图库）"""
        prompt = f"""请根据以下热搜话题，生成3个适合做文章配图的中文关键词。
要求：
1. 每个关键词2-6个汉字
2. 适合在头条免费图库搜索
3. 与话题相关，不要太泛
4. 每行一个，不要序号
5. 只返回3行关键词，不要其他内容

热搜话题：{hot_title}
领域：{category}

示例（比亚迪唐L停产）：
比亚迪
唐L
电动汽车

只返回3行关键词："""

        try:
            messages = [
                {"role": "system", "content": "你是一个图片关键词生成助手，擅长将话题转化为简洁的中文图片搜索关键词。"},
                {"role": "user", "content": prompt},
            ]
            keywords_text = self._call_api(messages, max_tokens=100, temperature=0.7)
            keywords = [kw.strip() for kw in keywords_text.strip().split("\n") if kw.strip()][:3]
            # 过滤掉可能的前缀
            keywords = [kw.lstrip("1234567890.、）) ").strip() for kw in keywords]
            keywords = [kw for kw in keywords if kw]  # 去掉空字符串
            logger.info(f"配图关键词: {keywords}")
            return keywords
        except Exception as e:
            logger.warning(f"生成配图关键词失败: {e}")
            # 返回默认中文关键词
            defaults = {
                "跨境电商": ["电商", "外贸", "全球贸易"],
                "外贸": ["外贸", "出口", "贸易"],
                "AI": ["人工智能", "科技", "机器人"],
                "科技": ["科技", "创新", "技术"],
            }
            return defaults.get(category, ["科技", "新闻", "资讯"])[:3]

    def _format_to_html(self, title: str, content: str, category: str) -> str:
        """
        将纯文本内容格式化为HTML
        适配今日头条的文章格式
        """
        lines = content.strip().split("\n")
        html_parts = []

        for line in lines:
            line = line.strip()
            if not line:
                continue

            # 判断是否是小标题（短行、可能有序号或#号）
            is_heading = (
                (len(line) < 40 and not line.endswith("。"))
                or line.startswith("#")
                or (line[0:1] in "一二三四五六七八九十" and ("、" in line or "：" in line or ":" in line))
                or (line[0].isdigit() and ("." in line[:3] or "、" in line[:3] or "：" in line[:3]))
            )

            if is_heading:
                clean = line.lstrip("#").strip()
                html_parts.append(f"<h2>{clean}</h2>")
            else:
                html_parts.append(f"<p>{line}</p>")

        return "\n".join(html_parts)


if __name__ == "__main__":
    import os
    # 测试
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    api_key = os.getenv("DEEPSEEK_API_KEY", "sk-your-key-here")
    if api_key == "sk-your-key-here":
        print("请设置 DEEPSEEK_API_KEY 环境变量")
    else:
        writer = AIWriter(api_key)
        result = writer.generate_article("DeepSeek开源新模型", "AI")
        print(f"\n标题: {result['title']}")
        print(f"内容前500字: {result['raw_content'][:500]}")
