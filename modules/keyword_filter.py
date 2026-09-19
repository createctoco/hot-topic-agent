"""
关键词过滤模块
按领域过滤热搜：跨境电商、外贸、AI
"""
import re
import logging
from typing import List, Dict

from modules.content_policy import ContentPolicyError, validate_topic

logger = logging.getLogger(__name__)

# 只保留具有明确业务语义的关键词，避免泛科技、体育和娱乐热点误入。
CATEGORY_KEYWORDS = {
    "跨境电商": [
        "跨境电商", "跨境", "独立站", "海外仓", "跨境支付", "国际物流",
        "跨境卖家", "跨境贸易", "出海", "DTC", "dropshipping", "外贸电商",
        "跨境出海", "海外电商", "海外市场", "海外业务", "全球开店", "国际站",
        "跨境运营", "海外客服", "跨境物流",
    ],
    "外贸": [
        "外贸", "出口", "进口", "报关", "关税", "海关",
        "国际贸易", "FOB", "CIF", "信用证", "提单", "外贸订单",
        "外贸B2B", "进出口", "出口退税", "关税壁垒", "贸易协定",
        "自贸区", "自由贸易", "贸易顺差", "贸易逆差", "RCEP",
        "进出口额", "外贸进出口", "外贸企业", "外贸人", "外贸业务",
        "国际结算", "出口订单", "海外订单", "反倾销", "反补贴",
        "人民币汇率", "汇率波动", "外贸政策", "进出口政策", "外贸新规",
    ],
    "AI": [
        "AI", "人工智能", "大模型", "LLM", "大语言模型",
        "机器学习", "深度学习", "AIGC", "AI绘画", "AI写作", "AGI",
        "算力", "智能体", "AI应用", "AI工具", "生成式AI", "神经网络",
        "多模态", "文生图", "文生视频", "智能编程", "AI代码", "AI辅助",
        "模型训练", "模型推理", "AI治理", "内容审核", "知识库",
    ],
}

CURRENCY_TERMS = ["美元", "欧元", "日元", "人民币", "汇率", "外汇"]
TRADE_CONTEXT_TERMS = [
    "外贸", "出口", "进口", "跨境", "贸易", "海关", "关税", "国际结算",
    "海外订单", "外贸订单", "采购", "报价", "收款",
]

# 排除关键词（避免发无关内容）
EXCLUDE_KEYWORDS = [
    "娱乐", "明星", "综艺", "选秀", "八卦", "绯闻",
    "游戏", "电竞", "直播带货", "网红", "饭圈",
    "女主", "男主", "男主", "主演", "剧情", "番外",
    "电视剧", "电影", "追剧", "热播", "大结局",
    "cos", "Cos", "COS", "cosplay", "角色扮演",
    "婚礼", "结婚", "恋情", "离婚", "演唱会", "歌手", "演员", "红毯", "穿搭", "粉丝",
    "足球", "球队", "球员", "赛事", "比赛", "世界杯", "冠军", "奖金", "进球",
    "查获", "藏匿", "毒品", "冰毒", "走私", "非法", "拘捕", "缉私", "活体",
    "政务", "党委", "共产党", "基层治理", "政治协商", "人大代表", "政协委员",
    "漫剧", "短剧", "配音", "真人剧", "影视", "追番", "动画作品",
    "曝", "曝光", "内情", "爆料", "网传", "传闻",
    "叶文洁", "惊现", "暗藏玄机", "伦理拷问", "细思极恐",
]


def _keyword_matches(title: str, keyword: str) -> bool:
    """Match ASCII terms as tokens so AI does not match words like AirPods."""
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 .+_-]*", keyword):
        pattern = rf"(?<![A-Za-z0-9]){re.escape(keyword)}(?![A-Za-z0-9])"
        return re.search(pattern, title, flags=re.IGNORECASE) is not None
    return keyword.lower() in title.lower()


def match_category(title: str) -> str:
    """
    判断标题属于哪个领域
    返回领域名称，不匹配返回 None
    """
    # 先检查排除关键词
    for kw in EXCLUDE_KEYWORDS:
        if kw in title:
            return None

    # Currency names alone do not make a topic foreign-trade news.
    if any(term in title for term in CURRENCY_TERMS) and not any(
        term in title for term in TRADE_CONTEXT_TERMS
    ):
        currency_only = True
    else:
        currency_only = False

    # 检查领域关键词
    matched_categories = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if _keyword_matches(title, kw):
                if category == "外贸" and currency_only and kw in CURRENCY_TERMS:
                    continue
                matched_categories.append(category)
                break

    if matched_categories:
        priority = ["跨境电商", "外贸", "AI"]
        for cat in priority:
            if cat in matched_categories:
                try:
                    validate_topic(title, cat)
                except ContentPolicyError:
                    return None
                return cat

    return None


def _hinted_category(title: str, hint: str) -> str:
    """Accept a trusted vertical-feed hint while retaining every safety gate."""
    if hint not in CATEGORY_KEYWORDS:
        return None
    if any(keyword in title for keyword in EXCLUDE_KEYWORDS):
        return None
    if not any(_keyword_matches(title, keyword) for keyword in CATEGORY_KEYWORDS[hint]):
        return None
    try:
        validate_topic(title, hint)
    except ContentPolicyError:
        return None
    return hint


def filter_items(items: List[Dict]) -> Dict[str, List[Dict]]:
    """
    过滤热搜列表，按领域分组
    返回: {"跨境电商": [...], "外贸": [...], "AI": [...]}
    """
    result = {
        "跨境电商": [],
        "外贸": [],
        "AI": [],
    }

    seen_titles = set()  # 去重

    for item in items:
        title = item.get("title", "").strip()
        if not title or title in seen_titles:
            continue

        category = _hinted_category(title, item.get("hint_category")) or match_category(title)
        if category:
            seen_titles.add(title)
            item["category"] = category
            result[category].append(item)

    # 统计
    for cat, items_list in result.items():
        logger.info(f"  {cat}: {len(items_list)} 条")

    return result


def exclude_published_topics(
    filtered: Dict[str, List[Dict]], published_titles: set[str]
) -> Dict[str, List[Dict]]:
    """Remove previously published source topics before quota selection."""
    return {
        category: [item for item in items if item.get("title") not in published_titles]
        for category, items in filtered.items()
    }


def select_topics(filtered: Dict[str, List[Dict]], count: int = 10) -> List[Dict]:
    """
    从过滤后的热搜中选取要发布的选题
    策略：三个领域均衡分配
    """
    selected = []
    category_count = max(len(filtered), 1)
    per_category = count // category_count
    remainder = count % category_count

    categories = list(filtered.keys())
    for i, cat in enumerate(categories):
        # 前 remainder 个领域多分一个
        target = per_category + (1 if i < remainder else 0)
        items = filtered.get(cat, [])
        for item in items[:target]:
            selected.append(item)

    # 如果某个领域不够，从其他领域补充
    if len(selected) < count:
        all_remaining = []
        for cat, items in filtered.items():
            already_selected = {s["title"] for s in selected}
            for item in items:
                if item["title"] not in already_selected:
                    all_remaining.append(item)
        for item in all_remaining:
            if len(selected) >= count:
                break
            selected.append(item)

    logger.info(f"选出 {len(selected)} 个选题:")
    for s in selected:
        logger.info(f"  [{s['category']}] {s['title']} (来源: {s['platform']})")

    return selected


if __name__ == "__main__":
    # 测试
    test_items = [
        {"title": "人工智能如何改善外贸客服", "platform": "安全示例"},
        {"title": "跨境卖家如何优化海外仓流程", "platform": "安全示例"},
        {"title": "人民币汇率波动影响外贸报价", "platform": "安全示例"},
        {"title": "某明星婚礼引发关注", "platform": "应被排除"},
        {"title": "某车企远程锁车引发投诉", "platform": "应被排除"},
        {"title": "某品牌新品发布会", "platform": "应被排除"},
    ]
    filtered = filter_items(test_items)
    import json
    print(json.dumps({k: [i["title"] for i in v] for k, v in filtered.items()},
                     ensure_ascii=False, indent=2))
    selected = select_topics(filtered, 10)
    print(f"\n选中 {len(selected)} 个:")
    for s in selected:
        print(f"  [{s['category']}] {s['title']}")
