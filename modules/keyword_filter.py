"""
关键词过滤模块
按领域过滤热搜：跨境电商、外贸、AI、科技
"""
import re
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

# 四大领域关键词库（已扩充，覆盖更多热搜场景）
CATEGORY_KEYWORDS = {
    "跨境电商": [
        "跨境电商", "亚马逊", "独立站", "Shopify", "速卖通", "虾皮", "shopee",
        "Lazada", "TikTok Shop", "TEMU", "SHEIN", "海外仓", "跨境",
        "跨境支付", "国际物流", "eBay", "Wish", "Ozon", "美客多",
        "跨境卖家", "跨境贸易", "出海", "DTC", "dropshipping",
        "电商", "天猫", "京东", "拼多多", "618", "双11", "双12",
        "快递", "顺丰", "菜鸟", "供应链", "仓储", "物流",
    ],
    "外贸": [
        "外贸", "出口", "进口", "报关", "关税", "海关", "贸易战",
        "国际贸易", "FOB", "CIF", "信用证", "提单", "外贸订单",
        "外贸B2B", "阿里巴巴国际站", "中国制造网", "广交会",
        "贸易摩擦", "反倾销", "贸易壁垒", "人民币汇率", "外贸人",
        "进出口", "贸易顺差", "贸易逆差", "一带一路", "RCEP",
        "美联储", "人民币", "汇率", "外汇", "GDP", "经济数据",
        "出口退税", "关税壁垒", "贸易协定", "自贸区",
    ],
    "AI": [
        "AI", "人工智能", "大模型", "ChatGPT", "GPT", "Claude",
        "DeepSeek", "通义千问", "文心一言", "机器学习", "深度学习",
        "AIGC", "AI绘画", "AI写作", "AGI", "LLM", "Stable Diffusion",
        "Midjourney", "Sora", "AI芯片", "算力", "智能体", "Agent",
        "AI应用", "AI工具", "生成式AI", "神经网络", "Transformer",
        "OpenAI", "Anthropic", "智谱", "月之暗面", "Kimi",
        "豆包", "文心", "质谱", "AI支付", "智能驾驶", "聊天机器人",
        "数字人", "AI医疗", "AI教育", "AI生成", "AI助手", "AI搜索",
        "大语言模型", "多模态", "AI创业", "AI商业化",
    ],
    "科技": [
        "科技", "芯片", "半导体", "光刻机", "5G", "6G", "量子计算",
        "区块链", "元宇宙", "新能源", "电动车", "自动驾驶", "智能手机",
        "电脑", "操作系统", "华为", "小米", "苹果", "谷歌", "微软",
        "英伟达", "台积电", "中芯国际", "电池", "光伏", "储能",
        "火箭", "航天", "卫星", "机器人", "无人机", "物联网",
        "云计算", "大数据", "网络安全", "国产替代", "科技股",
        "比亚迪", "蔚来", "理想汽车", "小鹏", "特斯拉", "增程", "纯电",
        "玻璃基板", "基板", "创新药", "医药", "新车", "充电桩",
        "新势力", "新能源车", "发布会", "科技企业", "科技公司",
        "科技部", "高新区", "专精特新", "独角兽",
    ],
}

# 排除关键词（避免发无关内容）
EXCLUDE_KEYWORDS = [
    "娱乐", "明星", "综艺", "选秀", "八卦", "绯闻",
    "游戏", "电竞", "直播带货", "网红", "饭圈",
    "女主", "男主", "男主", "主演", "剧情", "番外",
    "电视剧", "电影", "追剧", "热播", "大结局",
    "cos", "Cos", "COS", "cosplay", "角色扮演",
]


def match_category(title: str) -> str:
    """
    判断标题属于哪个领域
    返回领域名称，不匹配返回 None
    """
    title_lower = title.lower()

    # 先检查排除关键词
    for kw in EXCLUDE_KEYWORDS:
        if kw in title:
            return None

    # 检查领域关键词
    matched_categories = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in title_lower:
                matched_categories.append(category)
                break

    if matched_categories:
        # 如果匹配多个领域，优先级：跨境电商 > 外贸 > AI > 科技
        priority = ["跨境电商", "外贸", "AI", "科技"]
        for cat in priority:
            if cat in matched_categories:
                return cat

    return None


def filter_items(items: List[Dict]) -> Dict[str, List[Dict]]:
    """
    过滤热搜列表，按领域分组
    返回: {"跨境电商": [...], "外贸": [...], "AI": [...], "科技": [...]}
    """
    result = {
        "跨境电商": [],
        "外贸": [],
        "AI": [],
        "科技": [],
    }

    seen_titles = set()  # 去重

    for item in items:
        title = item.get("title", "").strip()
        if not title or title in seen_titles:
            continue

        category = match_category(title)
        if category:
            seen_titles.add(title)
            item["category"] = category
            result[category].append(item)

    # 统计
    for cat, items_list in result.items():
        logger.info(f"  {cat}: {len(items_list)} 条")

    return result


def select_topics(filtered: Dict[str, List[Dict]], count: int = 10) -> List[Dict]:
    """
    从过滤后的热搜中选取要发布的选题
    策略：四个领域均衡分配
    """
    selected = []
    per_category = count // 4
    remainder = count % 4

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
        {"title": "ChatGPT-5发布", "platform": "百度热搜"},
        {"title": "亚马逊Prime Day大促", "platform": "微博热搜"},
        {"title": "某明星出轨", "platform": "微博热搜"},
        {"title": "华为Mate70发布", "platform": "头条热榜"},
        {"title": "TEMU席卷全球", "platform": "百度热搜"},
        {"title": "广交会开幕", "platform": "知乎热榜"},
        {"title": "DeepSeek开源新模型", "platform": "百度热搜"},
        {"title": "英伟达股价创新高", "platform": "头条热榜"},
    ]
    filtered = filter_items(test_items)
    import json
    print(json.dumps({k: [i["title"] for i in v] for k, v in filtered.items()},
                     ensure_ascii=False, indent=2))
    selected = select_topics(filtered, 10)
    print(f"\n选中 {len(selected)} 个:")
    for s in selected:
        print(f"  [{s['category']}] {s['title']}")
