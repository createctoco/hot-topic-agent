"""
AI文章生成模块
使用 DeepSeek API 生成头条文章
"""
import json
import time
import logging
from typing import Dict, Optional
from openai import OpenAI

from modules.content_policy import (
    ContentPolicyError,
    validate_article,
    validate_generated_title,
    validate_topic,
)

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
    def __init__(self, api_key: str, base_url: str = "https://api.deepseek.com", model: str = "deepseek-chat"):
        """
        初始化 DeepSeek API 客户端
        api_key: DeepSeek API密钥
        base_url: API地址（默认 https://api.deepseek.com）
        model: 模型名称（默认 deepseek-chat）
        """
        self.client = OpenAI(api_key=api_key, base_url=base_url)
        self.model = model
        logger.info(f"AI Writer 初始化完成 (DeepSeek, model={model})")

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
                status_code = getattr(e, "status_code", None)
                message = str(e).lower()
                if status_code in (401, 403) or "authentication" in message or "api key" in message:
                    logger.error("AI API authentication failed; retries will not help.")
                    raise
                if attempt < max_retries - 1:
                    time.sleep(5 * (attempt + 1))  # 指数退避
                else:
                    raise

    def generate_title(self, hot_title: str, category: str) -> str:
        """
        根据热搜关键词生成文章标题
        """
        validate_topic(hot_title, category)
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
6. 只讨论科技、AI、外贸或跨境电商业务，不涉及政治、军事、政治人物或国家评价
7. 不使用攻击、贬损、煽动或未经证实的指控

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
        try:
            validate_generated_title(title, category, hot_title)
        except ContentPolicyError:
            title = hot_title[:30].strip("，。！？!?：: ")
            validate_generated_title(title, category, hot_title)
            logger.warning("生成标题未通过边界检查，已改用保守标题: %s", title)
        logger.info(f"生成标题: {title}")
        return title

    def generate_article(
        self,
        hot_title: str,
        category: str,
        platform: str = "",
        source_url: str = "",
    ) -> Dict:
        """
        根据热搜关键词生成完整文章
        返回: {"title": str, "content": str, "category": str}
        """
        validate_topic(hot_title, category)
        style = CATEGORY_STYLES.get(category, CATEGORY_STYLES["科技"])

        # 先生成标题
        title = self.generate_title(hot_title, category)

        # 生成正文
        content_prompt = f"""你是今日头条的{style['perspective']}，请围绕以下热搜话题，写一篇深度文章。

热搜话题：{hot_title}（来源：{platform}）
来源链接：{source_url or '未提供'}
领域：{category}
写作风格：{style['tone']}
重点关注：{style['focus']}

文章要求：
1. 字数2000-3000字
2. 结构清晰，使用小标题分段
3. 开头要吸引人，用一段话引出话题
4. 提供具体、可执行的信息；不得编造数据、案例、引语、认证或调查结论
5. 结尾要有观点总结和展望
6. 语言要通俗易懂，避免过于学术
7. 不要写"编者按""导语"等元信息
8. 直接写正文内容
9. 内容只限科技、AI、外贸、跨境电商，不讨论政治、军事、政治人物或国际冲突
10. 不贬损中国或任何国家、地区和群体，不使用煽动性、对立性表达
11. 遇到无法从题目和来源确认的事实，删除该事实，不猜测、不补造
12. 每段表达一个明确观点，给出原因、影响或操作建议，避免套话和空泛结论
13. 关于具体公司、人物或产品，只能复述热搜标题明确表达的事实；不得推断其动机、内部措施、技术路线、供应链安排或未来计划
14. 除热搜标题明确包含的信息外，正文改写为不依赖具体公司的行业通用原理、检查清单和操作方法

文章内容："""

        messages = [
            {"role": "system", "content": f"你是一个专业的今日头条{category}领域创作者，擅长写有深度、有观点的文章。你的文章风格{style['tone']}。"},
            {"role": "user", "content": content_prompt},
        ]

        logger.info(f"正在生成文章: [{category}] {title}")
        content = self._call_api(messages, max_tokens=4096, temperature=0.65)
        content = self._review_and_rewrite(
            title=title,
            content=content,
            hot_title=hot_title,
            category=category,
        )
        content = self._enforce_policy_with_rewrite(
            title=title,
            content=content,
            hot_title=hot_title,
            category=category,
        )

        # 将正文转为适合头条发布的HTML格式
        html_content = self._format_to_html(title, content, category)

        result = {
            "title": title,
            "content": html_content,
            "raw_content": content,
            "category": category,
            "source_topic": hot_title,
            "source_url": source_url,
            "image_keywords": self._generate_image_keywords(hot_title, category),
        }

        logger.info(f"文章生成完成: {title} ({len(content)}字)")
        return result

    def _review_and_rewrite(self, title: str, content: str, hot_title: str, category: str) -> str:
        """Run a low-temperature editorial pass before deterministic validation."""
        prompt = f"""你是严格的中文科技商业编辑。请审校并重写下面的文章，直接输出修订后的正文。

标题：{title}
原始话题：{hot_title}
领域：{category}

硬性要求：
1. 只保留科技、AI、外贸或跨境电商相关内容。
2. 删除政治、军事、政治人物、国际冲突、国家对立和贬损中国或其他国家群体的内容。
3. 修复病句、歧义、搭配错误、指代不清、前后矛盾和不完整句子。
4. 删除空洞套话、重复段落和模糊观点；每段必须提供明确事实边界、原因、影响或可执行建议。
5. 输入材料只有话题标题，不足以支持新闻事实。不得添加年份、比例、人数、报告、爆料、调查、引语或真实企业已经实施某项行为的断言。
6. 不得把推测写成事实。只能写概念解释、通用机制、风险识别方法和不依赖特定企业的实用建议。
7. 保持约1800至3000个中文字符，使用清晰的小标题和自然段。
8. 标题和正文不得使用“惊现、暗藏玄机、震惊、内幕、伦理拷问、细思极恐”等标题党或文学化表达。
9. 不输出审校说明、评分、Markdown代码围栏或“作为AI”等元信息。
10. 具体公司或人物只允许在开头复述原始话题一次；后文不得推断其动机、内部措施、供应链安排、技术路线或未来计划。

待审文章：
{content}
"""
        messages = [
            {
                "role": "system",
                "content": "你负责中文商业科技内容的事实边界、语法、逻辑和信息密度审校。",
            },
            {"role": "user", "content": prompt},
        ]
        reviewed = self._call_api(messages, max_tokens=4096, temperature=0.2).strip()
        if reviewed.startswith("```"):
            reviewed = reviewed.strip("`")
            reviewed = reviewed.removeprefix("markdown").strip()
        logger.info("文章二次审校完成: %s (%s字)", title, len(reviewed))
        return reviewed

    def _enforce_policy_with_rewrite(
        self,
        title: str,
        content: str,
        hot_title: str,
        category: str,
    ) -> str:
        """Automatically repair one policy failure before rejecting a topic."""
        try:
            validate_article(title, content, category)
            return content
        except ContentPolicyError as error:
            logger.warning("初次质量检查未通过，启动自动安全重写: %s", error)
            rewritten = self._safe_rewrite(
                title=title,
                content=content,
                hot_title=hot_title,
                category=category,
                rejection_reason=str(error),
            )
            validate_article(title, rewritten, category)
            logger.info("自动安全重写通过质量检查: %s (%s字)", title, len(rewritten))
            return rewritten

    def _safe_rewrite(
        self,
        title: str,
        content: str,
        hot_title: str,
        category: str,
        rejection_reason: str,
    ) -> str:
        """Rewrite rejected copy into evergreen, source-bounded business content."""
        prompt = f"""你是中文科技商业稿件的终审编辑。下面文章未通过自动检查，请重写整篇正文。

标题：{title}
原始话题：{hot_title}
领域：{category}
自动检查拒绝原因：{rejection_reason}

必须执行：
1. 删除所有政治、政府、政党、选举、外交、制裁、军事、战争、战场、武器、政治人物、国际冲突和国家对立内容；比喻用法也要删除。
2. 删除无法由输入标题直接支持的年份、比例、人数、金额、报告、统计、调查、爆料、引语、内部消息和企业已实施行为。
3. 不补造新闻细节。改写为技术原理、行业通用机制、风险识别步骤和可执行建议。
4. 只聚焦科技、AI、外贸或跨境电商，不评价中国或任何国家、地区和群体。
5. 修复病句、歧义、指代不清、前后矛盾和不完整句子；删除套话、重复和模糊观点。
6. 保留8个以上自然段或小标题、18个以上完整句子，总长度约1800至3000个中文字符。
7. 不输出说明、评分、引用列表、代码围栏或“作为AI”等元信息，只输出修订后的正文。
8. 具体公司或人物只允许在开头复述原始话题一次；后文统一使用“科技企业”“跨境卖家”等通用主体，不推断其内部措施或动机。

待重写正文：
{content}
"""
        messages = [
            {
                "role": "system",
                "content": "你只做保守、可验证、无敏感议题的中文科技商业稿件终审。",
            },
            {"role": "user", "content": prompt},
        ]
        rewritten = self._call_api(messages, max_tokens=4096, temperature=0.1).strip()
        if rewritten.startswith("```"):
            rewritten = rewritten.strip("`")
            rewritten = rewritten.removeprefix("markdown").strip()
        return rewritten

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
