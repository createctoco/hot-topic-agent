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
    sanitize_article_content,
)

logger = logging.getLogger(__name__)

# 领域写作风格
GENERIC_FALLBACK_TITLES = {
    "跨境电商": "跨境运营中的通用方法与风险控制",
    "外贸": "外贸流程中的通用方法与沟通要点",
    "AI": "AI应用中的通用方法与实施要点",
}

CATEGORY_STYLES = {
    "跨境电商": {
        "perspective": "跨境电商从业者/行业观察者",
        "tone": "专业、实用、有洞察",
        "focus": "行业趋势、通用运营方法、选品思路、内容客服、物流与支付流程",
    },
    "外贸": {
        "perspective": "资深外贸人/国际贸易分析师",
        "tone": "务实、经验丰富、接地气",
        "focus": "国际贸易流程、市场变化、沟通谈判、单证结算、风险管理",
    },
    "AI": {
        "perspective": "AI行业观察者/AI应用从业者",
        "tone": "前沿、清晰、通俗易懂",
        "focus": "技术原理、通用应用场景、行业影响、实施方法、未来趋势",
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

    def generate_title(self, hot_title: str, category: str, source_text: str = "") -> str:
        """
        根据热搜关键词生成文章标题
        """
        validate_topic(hot_title, category)
        style = CATEGORY_STYLES.get(category, CATEGORY_STYLES["AI"])

        prompt = f"""你是今日头条的{style['perspective']}，请根据以下热搜关键词，生成一个吸引人的文章标题。

热搜关键词：{hot_title}
来源正文摘录：{source_text[:3000] or '未能读取来源正文'}
领域：{category}

要求：
1. 标题15-30字，不要太长
2. 要有信息量，让人想点开看
3. 不要标题党，不要夸张
4. 不要用感叹号
5. 只返回标题本身，不要引号、不要序号、不要其他内容
6. 只写积极、建设性、可操作的内容，不写负面、争议、投诉、处罚、诉讼、事故或资本/市值话题
7. 全文不得出现任何具体企业、品牌、平台、工具、模型、产品、型号或人物名称；如热搜或来源包含这些名称，必须改成“某类工具”“相关平台”“行业通用方法”等类别词
8. 不做产品评测、推荐、比价或指名评价
9. 标题中的数字和具体事实必须能在热搜标题或来源正文中逐字找到

生成标题："""

        messages = [
            {"role": "system", "content": f"你只写积极、通用、无企业名、无品牌、无产品型号的今日头条{category}领域标题。"},
            {"role": "user", "content": prompt},
        ]

        title = self._call_api(messages, max_tokens=100, temperature=0.9)
        # 清理标题
        title = title.strip().strip('"').strip("'").strip("《》").strip("【】")
        # 去掉可能的前缀序号
        title = title.lstrip("1234567890.、) ")
        try:
            validate_generated_title(title, category, hot_title + "\n" + source_text)
        except ContentPolicyError:
            title = GENERIC_FALLBACK_TITLES.get(category, "行业通用方法与实施要点")
            validate_generated_title(title, category, title)
            logger.warning("生成标题未通过边界检查，已改用通用标题: %s", title)
        logger.info(f"生成标题: {title}")
        return title

    def generate_article(
        self,
        hot_title: str,
        category: str,
        platform: str = "",
        source_url: str = "",
        source_text: str = "",
    ) -> Dict:
        """
        根据热搜关键词生成完整文章
        返回: {"title": str, "content": str, "category": str}
        """
        validate_topic(hot_title, category)
        style = CATEGORY_STYLES.get(category, CATEGORY_STYLES["AI"])

        # 先生成标题
        title = self.generate_title(hot_title, category, source_text)

        source_material = source_text[:8000].strip() or "未能读取来源正文，只能使用热搜标题。"

        # 生成正文
        content_prompt = f"""你是今日头条的{style['perspective']}，请围绕以下热搜话题，写一篇深度文章。

热搜话题：{hot_title}（来源：{platform}）
来源链接：{source_url or '未提供'}
来源正文材料（只可使用这里明确出现的事实）：
---
{source_material}
---
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
9. 内容只限AI、外贸、跨境电商的通用知识和方法，不讨论泛科技新品、汽车、消费电子、政治、军事、政治人物或国际冲突
10. 只写积极、建设性、可操作的内容；不写负面、争议、投诉、处罚、诉讼、事故、裁员、破产、市值、股价或产品评测
11. 全文不得出现任何具体企业、品牌、平台、工具、模型、产品、型号或人物名称
12. 如热搜或来源材料出现具体名称，必须完全删除，改用类别词，例如“某类工具”“相关平台”“行业通用方法”
13. 遇到无法从热搜标题或来源材料确认的事实，删除该事实，不猜测、不补造
14. 每段表达一个明确观点，给出原因、影响或操作建议，避免套话和空泛结论

文章内容："""

        messages = [
            {"role": "system", "content": f"你只写积极、建设性、无企业名、无品牌、无平台名、无产品型号的{category}领域通用文章。"},
            {"role": "user", "content": content_prompt},
        ]

        logger.info(f"正在生成文章: [{category}] {title}")
        content = self._call_api(messages, max_tokens=4096, temperature=0.65)
        content = self._review_and_rewrite(
            title=title,
            content=content,
            hot_title=hot_title,
            category=category,
            source_text=source_text,
        )
        content = self._enforce_policy_with_rewrite(
            title=title,
            content=content,
            hot_title=hot_title,
            category=category,
            source_text=source_text,
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
            "source_text": source_text[:8000],
            "source_text_length": len(source_text),
            "image_keywords": self._generate_image_keywords(hot_title, category),
        }

        logger.info(f"文章生成完成: {title} ({len(content)}字)")
        return result

    def _review_and_rewrite(
        self,
        title: str,
        content: str,
        hot_title: str,
        category: str,
        source_text: str = "",
    ) -> str:
        """Run a low-temperature editorial pass before deterministic validation."""
        prompt = f"""你是严格的中文AI与外贸商业编辑。请审校并重写下面的文章，直接输出修订后的正文。

标题：{title}
原始话题：{hot_title}
领域：{category}
可用来源正文：
---
{source_text[:8000] or '无来源正文'}
---

硬性要求：
1. 只保留AI、外贸、跨境电商的通用知识和方法；删除汽车、消费电子、新品发布、公司新闻和所有具名事件。
2. 删除政治、军事、政治人物、国际冲突、国家对立和贬损中国或其他国家群体的内容。
3. 全文不得出现任何具体企业、品牌、平台、工具、模型、产品、型号或人物名称；如有，改成“某类工具”“相关平台”“行业通用方法”等类别词。
4. 只写积极、建设性、可操作内容，删除负面、争议、投诉、处罚、诉讼、事故、裁员、破产、市值、股价、产品评测等内容。
5. 修复病句、歧义、搭配错误、指代不清、前后矛盾和不完整句子。
6. 删除空洞套话、重复段落和模糊观点；每段必须提供明确事实边界、原因、影响或可执行建议。
7. 年份、比例、人数、报告、调查、引语和企业行为等具体事实，必须能在可用来源正文或原始话题中逐字找到；找不到就删除。
8. 不得把推测写成事实。只能写概念解释、通用机制、风险识别方法和不依赖特定企业的实用建议。
9. 保持约1800至3000个中文字符，使用清晰的小标题和自然段。
10. 不输出审校说明、评分、Markdown代码围栏或“作为AI”等元信息。

待审文章：
{content}
"""
        messages = [
            {
                "role": "system",
                "content": "你负责中文AI与外贸商业内容的事实边界、语法、逻辑和信息密度审校。",
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
        source_text: str = "",
    ) -> str:
        """Automatically repair one policy failure before rejecting a topic."""
        try:
            validate_article(title, content, category, hot_title + "\n" + source_text)
            return content
        except ContentPolicyError as error:
            logger.warning("初次质量检查未通过，启动自动安全重写: %s", error)
            rewritten = self._safe_rewrite(
                title=title,
                content=content,
                hot_title=hot_title,
                category=category,
                rejection_reason=str(error),
                source_text=source_text,
            )
            evidence = hot_title + "\n" + source_text
            try:
                validate_article(title, rewritten, category, evidence)
                logger.info("自动安全重写通过质量检查: %s (%s字)", title, len(rewritten))
                return rewritten
            except ContentPolicyError:
                sanitized = sanitize_article_content(rewritten, evidence)
                validate_article(title, sanitized, category, evidence)
                logger.info("确定性安全清洗通过质量检查: %s (%s字)", title, len(sanitized))
                return sanitized

    def _safe_rewrite(
        self,
        title: str,
        content: str,
        hot_title: str,
        category: str,
        rejection_reason: str,
        source_text: str = "",
    ) -> str:
        """Rewrite rejected copy into evergreen, source-bounded business content."""
        prompt = f"""你是中文AI与外贸商业稿件的终审编辑。下面文章未通过自动检查，请重写整篇正文。

标题：{title}
原始话题：{hot_title}
领域：{category}
自动检查拒绝原因：{rejection_reason}
允许引用的来源正文：
---
{source_text[:8000] or '无来源正文'}
---

必须执行：
1. 删除所有政治、政府、政党、选举、外交、制裁、军事、战争、战场、武器、政治人物、国际冲突和国家对立内容；比喻用法也要删除。
2. 删除无法由输入标题或允许引用的来源正文支持的年份、比例、人数、金额、报告、统计、调查、爆料、引语和内部消息。
3. 不补造新闻细节。改写为技术原理、行业通用机制、操作步骤和可执行建议。
4. 只聚焦AI、外贸或跨境电商的通用方法，删除汽车、消费电子、新品发布、公司新闻和具名事件。
5. 只写积极、建设性内容，删除负面、争议、投诉、处罚、诉讼、事故、裁员、破产、市值和股价话题。
6. 全文不得出现任何具体企业、品牌、平台、工具、模型、产品、型号或人物名称；只使用通用类别词。
7. 保留8个以上自然段或小标题、18个以上完整句子，总长度约1800至3000个中文字符。
8. 不输出说明、评分、引用列表、代码围栏或“作为AI”等元信息，只输出修订后的正文。

待重写正文：
{content}
"""
        messages = [
            {
                "role": "system",
                "content": "你只做保守、可验证、无敏感议题的中文AI与外贸商业稿件终审。",
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
5. 不得出现企业、品牌、平台、工具、产品、型号或人物名称
6. 只使用积极、通用、行业场景词
7. 只返回3行关键词，不要其他内容

热搜话题：{hot_title}
领域：{category}

示例（通用业务方法）：
人工智能
知识库
客服流程

只返回3行关键词："""

        try:
            messages = [
                {"role": "system", "content": "你是一个图片关键词生成助手，擅长将话题转化为简洁的中文图片搜索关键词。"},
                {"role": "user", "content": prompt},
            ]
            keywords_text = self._call_api(messages, max_tokens=100, temperature=0.7)
            raw_keywords = [kw.strip() for kw in keywords_text.strip().split("\n") if kw.strip()][:8]
            safe_keywords: list[str] = []
            for keyword in raw_keywords:
                keyword = keyword.lstrip("1234567890.、）) ").strip()
                if not keyword or keyword in safe_keywords:
                    continue
                try:
                    validate_topic(keyword, category)
                except ContentPolicyError:
                    continue
                safe_keywords.append(keyword)
                if len(safe_keywords) >= 3:
                    break

            defaults = {
                "跨境电商": ["电商", "外贸", "全球贸易"],
                "外贸": ["外贸", "出口", "贸易"],
                "AI": ["人工智能", "大模型", "AI应用"],
            }
            for fallback in defaults.get(category, ["人工智能", "外贸", "跨境电商"]):
                if len(safe_keywords) >= 3:
                    break
                if fallback not in safe_keywords:
                    safe_keywords.append(fallback)
            logger.info(f"配图关键词: {safe_keywords[:3]}")
            return safe_keywords[:3]
        except Exception as e:
            logger.warning(f"生成配图关键词失败: {e}")
            # 返回默认中文关键词
            defaults = {
                "跨境电商": ["电商", "外贸", "全球贸易"],
                "外贸": ["外贸", "出口", "贸易"],
                "AI": ["人工智能", "大模型", "AI应用"],
            }
            return defaults.get(category, ["人工智能", "外贸", "跨境电商"])[:3]

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
        result = writer.generate_article("大语言模型如何改善外贸客服", "AI")
        print(f"\n标题: {result['title']}")
        print(f"内容前500字: {result['raw_content'][:500]}")
