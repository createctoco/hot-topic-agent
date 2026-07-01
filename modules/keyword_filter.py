"""
关键词过滤模块
按领域过滤热搜：跨境电商、外贸、AI、科技
"""
import re
import logging
from typing import List, Dict

from modules.content_policy import ContentPolicyError, validate_topic

logger = logging.getLogger(__name__)

# 四大领域关键词库（大幅扩充，提高匹配率）
CATEGORY_KEYWORDS = {
    "跨境电商": [
        # 平台
        "跨境电商", "跨境", "亚马逊", "Amazon", "独立站", "Shopify", "速卖通", "AliExpress",
        "虾皮", "Shopee", "Lazada", "TikTok Shop", "TikTok", "TEMU", "SHEIN", "希音",
        "海外仓", "跨境支付", "国际物流", "eBay", "Wish", "Ozon", "美客多", "MercadoLibre",
        "跨境卖家", "跨境贸易", "出海", "DTC", "dropshipping", "外贸电商",
        # 电商通用
        "电商", "天猫", "京东", "拼多多", "618", "双11", "双12", "双十一", "黑五", "黑五",
        "快递", "顺丰", "菜鸟", "供应链", "仓储", "物流", "发货", "配送",
        "直播带货", "直播电商", "内容电商", "社交电商",
        # 出海相关
        "出海", "全球化", "海外市场", "海外业务", "国际化", "跨境出海",
    ],
    "外贸": [
        # 核心词汇
        "外贸", "出口", "进口", "报关", "关税", "海关", "贸易战", "贸易摩擦",
        "国际贸易", "FOB", "CIF", "信用证", "提单", "外贸订单",
        "外贸B2B", "阿里巴巴国际站", "中国制造网", "广交会", "进出口",
        "出口退税", "关税壁垒", "贸易协定", "自贸区", "自由贸易",
        # 经济金融
        "美联储", "人民币", "汇率", "外汇", "GDP", "经济数据", "经济增长",
        "贸易顺差", "贸易逆差", "一带一路", "RCEP", "东盟", "欧盟",
        "进出口额", "外贸进出口", "外贸企业", "外贸人", "外贸业务",
        # 政策相关
        "加征关税", "关税加征", "贸易制裁", "反倾销", "反补贴",
        "人民币汇率", "美元", "欧元", "日元", "汇率波动",
        "外贸政策", "进出口政策", "外贸新规",
    ],
    "AI": [
        # 通用AI词汇
        "AI", "人工智能", "智能", "大模型", "LLM", "大语言模型",
        "ChatGPT", "GPT", "Claude", "DeepSeek", "通义千问", "文心一言",
        "机器学习", "深度学习", "AIGC", "AI绘画", "AI写作", "AGI",
        "Stable Diffusion", "Midjourney", "Sora", "AI芯片", "算力",
        "智能体", "Agent", "AI应用", "AI工具", "生成式AI", "神经网络",
        "Transformer", "OpenAI", "Anthropic", "智谱", "月之暗面", "Kimi",
        "豆包", "文心", "质谱", "AI助手", "AI搜索", "AI创业", "AI商业化",
        # AI应用场景
        "AI医疗", "AI教育", "AI生成", "AI绘画", "AI视频", "AI音乐",
        "数字人", "虚拟人", "智能驾驶", "自动驾驶", "聊天机器人", "智能客服",
        "多模态", "GPT-4", "GPT-5", "Gemini", "文生图", "文生视频",
        "Copilot", "智能编程", "AI代码", "AI辅助",
        # 国内AI
        "百度AI", "阿里AI", "腾讯AI", "华为AI", "字节AI", "商汤", "旷视", "云从",
        "讯飞", "科大讯飞", "AI大会", "人工智能大会",
    ],
    "科技": [
        # 硬件/芯片
        "科技", "芯片", "半导体", "光刻机", "5G", "6G", "量子计算",
        "区块链", "元宇宙", "新能源", "电动车", "电动汽车", "自动驾驶", "智能手机",
        "电脑", "笔记本", "平板", "智能手表", "wearable",
        "操作系统", "华为", "小米", "苹果", "谷歌", "微软", "三星",
        "英伟达", "NVIDIA", "台积电", "中芯国际", "TSMC", "芯片制造",
        # 汽车/新能源
        "电池", "光伏", "储能", "火箭", "航天", "卫星", "无人机",
        "比亚迪", "蔚来", "理想", "小鹏", "特斯拉", "增程", "纯电",
        "新能源车", "新能源汽车", "电动汽车", "智能汽车", "车联网",
        "充电桩", "充电设施", "锂电池", "固态电池",
        # 互联网/软件
        "物联网", "云计算", "大数据", "网络安全", "国产替代", "科技股",
        "玻璃基板", "基板", "创新药", "医药", "新车", "发布会",
        "科技企业", "科技公司", "科技部", "高新区", "专精特新", "独角兽",
        "IPO", "科技上市", "科技融资", "科技巨头", "科技突破",
        # 手机/消费电子
        "iPhone", "手机", "新品发布", "旗舰机", "折叠屏", "全面屏",
        "华为手机", "小米手机", "苹果手机", "三星手机", "OPPO", "vivo",
        "荣耀", "realme", "一加", "努比亚",
        # 国内科技
        "国产芯片", "国产操作系统", "国产软件", "信创", "国产替代",
        "科技战", "技术封锁", "科技制裁", "科技自立",
        # 新增：热搜常见具体词
        "苹果", "华为", "小米", "OPPO", "vivo", "荣耀", "三星", "iPhone", "iPad", "Mac",
        "特斯拉", "比亚迪", "蔚来", "理想", "小鹏", "问界", "智界", "享界",
        "英伟达", "英伟达", "AMD", "英特尔", "高通", "联发科",
        "台积电", "三星电子", "中芯国际", "华虹", "长江存储",
        "京东方", "TCL", "海信", "创维", "长虹",
        "火山引擎", "字节", "阿里", "腾讯", "百度", "美团", "京东", "拼多多",
        "快手", "B站", "B站", "知乎", "小红书", "抖音",
        "SpaceX", "马斯克", "特斯拉", "星链",
        "发布", "上市", "融资", "IPO", "市值", "股价",
        "突破", "自研", "国产", "制裁", "禁令",
    ],
}

# 排除关键词（避免发无关内容）
EXCLUDE_KEYWORDS = [
    "娱乐", "明星", "综艺", "选秀", "八卦", "绯闻",
    "游戏", "电竞", "直播带货", "网红", "饭圈",
    "女主", "男主", "男主", "主演", "剧情", "番外",
    "电视剧", "电影", "追剧", "热播", "大结局",
    "cos", "Cos", "COS", "cosplay", "角色扮演",
    "婚礼", "结婚", "恋情", "离婚", "演唱会", "歌手", "演员", "红毯", "穿搭", "粉丝",
    "叶文洁", "惊现", "暗藏玄机", "伦理拷问", "细思极恐",
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
                try:
                    validate_topic(title, cat)
                except ContentPolicyError:
                    return None
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
