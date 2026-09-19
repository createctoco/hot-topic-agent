"""Hard content boundaries and deterministic article quality checks."""

from __future__ import annotations

import re
from html import unescape


ALLOWED_CATEGORIES = {"AI", "外贸", "跨境电商"}

BLOCKED_TERMS = {
    "政治": [
        "政治", "政党", "选举", "总统", "总理", "主席", "政府", "外交", "制裁",
        "贸易战", "关税战", "政治人物", "政务", "党委", "共产党", "基层治理",
        "政治协商", "人大代表", "政协委员",
        "特朗普", "拜登", "普京", "泽连斯基", "习近平",
    ],
    "军事": [
        "军事", "军队", "战争", "战场", "武器", "导弹", "核武", "航母", "军演",
        "台海", "南海冲突", "俄乌", "以色列", "加沙",
    ],
    "国家贬损": [
        "中国崩溃", "中国落后", "中国威胁", "中国失败", "唱衰中国", "抹黑中国",
        "国人素质", "中国人不行",
    ],
}

BLOCKED_TERMS.update({
    "企业负面": [
        "投诉", "举报", "警告", "处罚", "罚款", "约谈", "诉讼", "起诉", "被诉",
        "败诉", "判赔", "赔偿", "侵权", "抄袭", "下架", "封禁", "争议", "风波",
        "质疑", "危机", "负面", "舆情", "翻车", "塌房", "爆雷", "暴雷", "破产",
        "倒闭", "裁员", "欠薪", "欠款", "拖欠", "造假", "欺诈", "虚假宣传",
        "数据泄露", "隐私泄露", "安全事故", "事故", "伤亡", "火灾", "爆炸",
        "偷税", "漏税", "逃税", "洗钱", "行贿", "受贿", "违法", "犯罪",
        "逮捕", "拘捕", "刑拘", "判刑", "内幕", "黑幕", "曝光", "爆料",
        "网传", "传闻", "谣言",
    ],
    "资本与汽车": [
        "上市", "IPO", "市值", "估值", "股价", "暴跌", "跌停", "涨停", "融资",
        "财报", "营收", "亏损", "退市", "收购", "并购", "车企", "汽车", "车型",
        "锁车", "远程锁车", "召回", "停产", "销量", "交付量", "智能驾驶", "自动驾驶",
    ],
    "具体品牌": [
        "亚马逊", "Amazon", "阿里巴巴", "Alibaba", "速卖通", "AliExpress",
        "Shopify", "Shopee", "虾皮", "Lazada", "TikTok", "TEMU", "SHEIN",
        "希音", "eBay", "Wish", "Ozon", "美客多", "MercadoLibre", "ChatGPT",
        "GPT", "Claude", "DeepSeek", "OpenAI", "Anthropic", "Kimi", "Gemini",
        "Copilot", "通义千问", "文心一言", "豆包", "智谱", "月之暗面",
        "科大讯飞", "讯飞", "商汤", "旷视", "云从", "百度", "腾讯", "华为",
        "字节", "英伟达", "Nvidia", "微软", "Microsoft", "谷歌", "Google",
        "苹果", "Apple", "Meta", "特斯拉", "Tesla", "比亚迪", "BYD", "小鹏",
        "蔚来", "理想汽车", "小米", "Xiaomi", "奔驰", "Mercedes", "宝马", "BMW",
        "奥迪", "Audi", "丰田", "Toyota", "大众", "Volkswagen", "本田", "Honda",
        "福特", "Ford", "吉利", "长城", "奇瑞", "上汽", "广汽", "东风",
    ],
    "具体产品": [
        "手机", "iPhone", "智能手机", "折叠屏", "电脑", "笔记本", "平板", "相机",
        "耳机", "AirPods", "手表", "电视", "冰箱", "空调", "洗衣机", "芯片",
        "新品", "发布会", "评测", "测评", "工具推荐", "产品推荐", "型号",
    ],
})

EMPTY_CONTENT_MARKERS = [
    "众所周知", "不难发现", "值得注意的是", "未来可期", "让我们拭目以待",
    "在这个快速发展的时代", "总而言之", "综上所述",
]

HYPE_OR_OFF_TOPIC_TERMS = [
    "惊现", "暗藏玄机", "震惊", "内幕", "伦理拷问", "叶文洁", "细思极恐",
    "颠覆认知", "终于瞒不住", "万万没想到",
]

UNSUPPORTED_CLAIM_PATTERNS = [
    r"20\d{2}年",
    r"\d+(?:\.\d+)?\s*(?:至|到|[-—])\s*\d+(?:\.\d+)?\s*(?:年|月|天|小时|分钟|个|家|人|%)",
    r"\d+(?:\.\d+)?%",
    r"(?:超过|高达|达到|多达)\d+",
    r"\d+(?:\.\d+)?万(?:人|家|个|美元|元)",
    r"据[^。；]{0,20}(?:报告|统计|数据|研究|调查)",
    r"(?:员工|内部人士|知情人士)[^。；]{0,20}(?:爆料|透露|表示)",
    r"(?:有消息称|传出|网传|业内人士表示|公开表示|研究表明|调查显示)",
    r"(?:具体措施|具体做法)(?:包括|有)",
]


class ContentPolicyError(ValueError):
    pass


def find_boundary_violations(text: str) -> list[str]:
    violations: list[str] = []
    compact = re.sub(r"\s+", "", text or "")
    casefolded = (text or "").casefold()
    for boundary, terms in BLOCKED_TERMS.items():
        matches: list[str] = []
        for term in terms:
            if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .+_-]*", term):
                pattern = rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])"
                if re.search(pattern, text or "", flags=re.IGNORECASE):
                    matches.append(term)
            elif term.casefold() in casefolded or term.replace(" ", "").casefold() in compact.casefold():
                matches.append(term)
        if matches:
            violations.append(f"{boundary}: {', '.join(sorted(set(matches)))}")
    return violations


def find_named_entity_violations(text: str) -> list[str]:
    matches: set[str] = set()
    patterns = (
        (r"[\u4e00-\u9fff]{2,16}(?:有限公司|股份有限公司|集团有限公司|控股集团|科技集团|实业集团|株式会社)", re.IGNORECASE),
        (r"\b[A-Z][A-Za-z0-9&.'-]{1,30}\s+(?:Inc|Corp|Corporation|Ltd|Limited|LLC|Group|Holdings|Technologies|Technology)\b", re.IGNORECASE),
        (r"\b[A-Za-z]{2,12}[- ]?\d{1,4}[A-Za-z0-9-]*\b", re.IGNORECASE),
        (r"[\u4e00-\u9fff](?:Pro|Max|Plus|Ultra|L|S|X|Y)\d{0,4}", 0),
        (r"[®™]", 0),
    )
    for pattern, flags in patterns:
        matches.update(
            match.group(0)
            for match in re.finditer(pattern, text or "", flags=flags)
        )
    if not matches:
        return []
    return ["具体企业/品牌/产品: " + ", ".join(sorted(matches))]


def _all_policy_violations(text: str) -> list[str]:
    return find_boundary_violations(text) + find_named_entity_violations(text)


def validate_topic(title: str, category: str) -> None:
    if category not in ALLOWED_CATEGORIES:
        raise ContentPolicyError(f"unsupported category: {category}")
    violations = _all_policy_violations(title)
    if violations:
        raise ContentPolicyError("blocked topic: " + "; ".join(violations))
    hype = [term for term in HYPE_OR_OFF_TOPIC_TERMS if term in title]
    if hype:
        raise ContentPolicyError("hype or off-topic title: " + ", ".join(hype))


def validate_generated_title(title: str, category: str, source_evidence: str) -> None:
    """Reject factual claims introduced by the generated title itself."""
    validate_topic(title, category)
    introduced_claims: list[str] = []
    for pattern in UNSUPPORTED_CLAIM_PATTERNS:
        for match in re.finditer(pattern, title):
            claim = match.group(0)
            if claim not in re.sub(r"\s+", "", source_evidence or ""):
                introduced_claims.append(claim)
    if introduced_claims:
        raise ContentPolicyError(
            "generated title introduced unsupported claims: "
            + ", ".join(sorted(set(introduced_claims)))
        )


def plain_text(html_or_text: str) -> str:
    text = re.sub(r"<[^>]+>", "\n", html_or_text or "")
    return unescape(text).strip()


def find_unsupported_claims(text: str, source_evidence: str = "") -> list[str]:
    compact = re.sub(r"\s+", "", text or "")
    evidence = re.sub(r"\s+", "", source_evidence or "")
    unsupported: list[str] = []
    for pattern in UNSUPPORTED_CLAIM_PATTERNS:
        for match in re.finditer(pattern, compact):
            if not evidence or match.group(0) not in evidence:
                unsupported.append(pattern)
                break
    return unsupported


def sanitize_article_content(content: str, source_evidence: str = "") -> str:
    """Drop complete passages that violate hard boundaries or source rules."""
    kept: list[str] = []
    for passage in re.split(r"\n+", content or ""):
        passage = passage.strip()
        if not passage:
            continue
        compact = re.sub(r"\s+", "", passage)
        if _all_policy_violations(passage):
            continue
        if any(marker in compact for marker in ("作为一个AI", "作为AI", "作为人工智能", "我无法")):
            continue
        if find_unsupported_claims(passage, source_evidence):
            continue
        kept.append(passage)
    return "\n".join(kept)


def validate_article(title: str, content: str, category: str, source_evidence: str = "") -> None:
    validate_topic(title, category)
    text = plain_text(content)
    violations = _all_policy_violations(text)
    if violations:
        raise ContentPolicyError("blocked article: " + "; ".join(violations))

    compact = re.sub(r"\s+", "", text)
    if len(compact) < 1200:
        raise ContentPolicyError(f"article is too short: {len(compact)} characters")
    if len(compact) > 5000:
        raise ContentPolicyError(f"article is too long: {len(compact)} characters")

    paragraphs = [part.strip() for part in re.split(r"\n+", text) if part.strip()]
    if len(paragraphs) < 8:
        raise ContentPolicyError("article needs at least 8 meaningful sections or paragraphs")

    sentences = [part.strip() for part in re.split(r"[。！？!?]", text) if len(part.strip()) >= 8]
    if len(sentences) < 18:
        raise ContentPolicyError("article has too few complete sentences")
    normalized = [re.sub(r"\s+", "", sentence) for sentence in sentences]
    if len(set(normalized)) / len(normalized) < 0.8:
        raise ContentPolicyError("article contains excessive repetition")

    marker_hits = sum(compact.count(marker) for marker in EMPTY_CONTENT_MARKERS)
    if marker_hits > 4:
        raise ContentPolicyError("article contains too many vague filler phrases")

    if any(marker in compact for marker in ("作为一个AI", "作为AI", "作为人工智能", "我无法")):
        raise ContentPolicyError("article contains model meta-commentary")

    unsupported = find_unsupported_claims(compact, source_evidence)
    if unsupported:
        raise ContentPolicyError("article contains unsupported factual claims")
