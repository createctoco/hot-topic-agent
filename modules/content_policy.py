"""Hard content boundaries and deterministic article quality checks."""

from __future__ import annotations

import re
from html import unescape


ALLOWED_CATEGORIES = {"科技", "AI", "外贸", "跨境电商"}

BLOCKED_TERMS = {
    "政治": [
        "政治", "政党", "选举", "总统", "总理", "主席", "政府", "外交", "制裁",
        "贸易战", "关税战", "政治人物",
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

EMPTY_CONTENT_MARKERS = [
    "众所周知", "不难发现", "值得注意的是", "未来可期", "让我们拭目以待",
    "在这个快速发展的时代", "总而言之", "综上所述",
]


class ContentPolicyError(ValueError):
    pass


def find_boundary_violations(text: str) -> list[str]:
    violations: list[str] = []
    compact = re.sub(r"\s+", "", text or "")
    for boundary, terms in BLOCKED_TERMS.items():
        matches = sorted({term for term in terms if term in compact})
        if matches:
            violations.append(f"{boundary}: {', '.join(matches)}")
    return violations


def validate_topic(title: str, category: str) -> None:
    if category not in ALLOWED_CATEGORIES:
        raise ContentPolicyError(f"unsupported category: {category}")
    violations = find_boundary_violations(title)
    if violations:
        raise ContentPolicyError("blocked topic: " + "; ".join(violations))


def plain_text(html_or_text: str) -> str:
    text = re.sub(r"<[^>]+>", "\n", html_or_text or "")
    return unescape(text).strip()


def validate_article(title: str, content: str, category: str) -> None:
    validate_topic(title, category)
    text = plain_text(content)
    violations = find_boundary_violations(text)
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

    if any(marker in compact for marker in ("作为一个AI", "作为AI", "我无法", "语言模型")):
        raise ContentPolicyError("article contains model meta-commentary")
