"""
热搜采集模块
支持多平台热搜数据采集：百度、微博、知乎、头条
"""
import requests
import json
import time
import logging
import re
from html import unescape
from urllib.parse import quote
from xml.etree import ElementTree
from typing import List, Dict
from datetime import datetime

logger = logging.getLogger(__name__)

# 通用请求头
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

# 各平台配置
PLATFORMS = {
    "baidu": {
        "name": "百度热搜",
        "url": "https://top.baidu.com/api/board?platform=wise&tab=realtime",
    },
    "weibo": {
        "name": "微博热搜",
        "url": "https://weibo.com/ajax/side/hotSearch",
    },
    "zhihu": {
        "name": "知乎热榜",
        "url": "https://www.zhihu.com/api/v3/feed/topstory/hot-lists/total?limit=50",
    },
    "toutiao": {
        "name": "头条热榜",
        "url": "https://www.toutiao.com/hot-event/hot-board/?origin=toutiao_pc",
    },
}


# General hot lists rarely contain enough vertical business news. These queries
# supplement them without bringing generic consumer-technology news back in.
VERTICAL_NEWS_QUERIES = {
    "跨境电商": "跨境电商 OR 跨境卖家 OR 海外仓 OR Amazon卖家 OR TEMU OR TikTok Shop when:3d",
    "外贸": "外贸 OR 出口订单 OR 海关 OR 进出口 OR 国际贸易 OR 广交会 when:3d",
    "AI": "人工智能 OR 大模型 OR AI智能体 OR DeepSeek OR ChatGPT when:2d",
}


def _plain_text(value: str) -> str:
    """Turn the small HTML snippets used by RSS feeds into plain text."""
    value = re.sub(r"<[^>]+>", " ", value or "")
    return re.sub(r"\s+", " ", unescape(value)).strip()


def _parse_rss(content: bytes, platform: str, category: str, limit: int = 20) -> List[Dict]:
    """Parse RSS 2.0 items into the same shape as regular hot-list data."""
    root = ElementTree.fromstring(content)
    items = []
    for node in root.findall("./channel/item")[:limit]:
        title = _plain_text(node.findtext("title", ""))
        link = (node.findtext("link", "") or "").strip()
        source = _plain_text(node.findtext("source", ""))
        if source and title.endswith(f" - {source}"):
            title = title[: -(len(source) + 3)].strip()
        if not title or not link:
            continue
        items.append({
            "platform": platform,
            "title": title,
            "hot": "",
            "url": link,
            "raw_query": title,
            "summary": _plain_text(node.findtext("description", "")),
            "published_at": (node.findtext("pubDate", "") or "").strip(),
            "source_name": source,
            "hint_category": category,
        })
    return items


def fetch_vertical_news() -> List[Dict]:
    """Fetch category-specific news, using Bing only when Google RSS fails."""
    items = []
    for category, query in VERTICAL_NEWS_QUERIES.items():
        google_url = (
            "https://news.google.com/rss/search?q="
            f"{quote(query)}&hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
        )
        try:
            resp = requests.get(google_url, headers=HEADERS, timeout=15)
            resp.raise_for_status()
            category_items = _parse_rss(resp.content, "Google新闻", category)
        except Exception as exc:
            logger.warning("Google新闻RSS获取失败 [%s]: %s", category, exc)
            category_items = []

        if not category_items:
            bing_url = (
                "https://www.bing.com/news/search?q="
                f"{quote(query.replace(' when:3d', '').replace(' when:2d', ''))}"
                "&format=rss&setlang=zh-cn"
            )
            try:
                resp = requests.get(bing_url, headers=HEADERS, timeout=15)
                resp.raise_for_status()
                category_items = _parse_rss(resp.content, "Bing新闻", category)
            except Exception as exc:
                logger.warning("Bing新闻RSS获取失败 [%s]: %s", category, exc)

        logger.info("垂直新闻 [%s]: 获取到 %s 条", category, len(category_items))
        items.extend(category_items)
        time.sleep(0.3)
    return items


def fetch_baidu() -> List[Dict]:
    """获取百度热搜"""
    try:
        resp = requests.get(PLATFORMS["baidu"]["url"], headers=HEADERS, timeout=10)
        data = resp.json()
        items = []
        cards = data.get("data", {}).get("cards", [])
        for card in cards:
            for item in card.get("content", []):
                items.append({
                    "platform": "百度热搜",
                    "title": item.get("word", ""),
                    "hot": item.get("hotScore", ""),
                    "url": item.get("url", ""),
                    "raw_query": item.get("query", item.get("word", "")),
                    "summary": item.get("desc", ""),
                })
        logger.info(f"百度热搜: 获取到 {len(items)} 条")
        return items
    except Exception as e:
        logger.warning(f"百度热搜获取失败: {e}")
        return []


def fetch_weibo() -> List[Dict]:
    """获取微博热搜"""
    try:
        headers = {**HEADERS, "Referer": "https://weibo.com"}
        resp = requests.get(PLATFORMS["weibo"]["url"], headers=headers, timeout=10)
        data = resp.json()
        items = []
        # realtime hot search
        for item in data.get("data", {}).get("realtime", []):
            items.append({
                "platform": "微博热搜",
                "title": item.get("note", ""),
                "hot": item.get("num", ""),
                "url": f"https://s.weibo.com/weibo?q=%23{item.get('note', '').replace(' ', '%20')}%23",
                "raw_query": item.get("note", ""),
                "summary": item.get("word_scheme", ""),
            })
        logger.info(f"微博热搜: 获取到 {len(items)} 条")
        return items
    except Exception as e:
        logger.warning(f"微博热搜获取失败: {e}")
        return []


def fetch_zhihu() -> List[Dict]:
    """获取知乎热榜"""
    try:
        headers = {**HEADERS, "Referer": "https://www.zhihu.com"}
        resp = requests.get(PLATFORMS["zhihu"]["url"], headers=headers, timeout=10)
        data = resp.json()
        items = []
        for item in data.get("data", []):
            target = item.get("target", {})
            title = target.get("title", "")
            if title:
                items.append({
                    "platform": "知乎热榜",
                    "title": title,
                    "hot": item.get("detail_text", ""),
                    "url": target.get("url", ""),
                    "raw_query": title,
                    "summary": target.get("excerpt", ""),
                })
        logger.info(f"知乎热榜: 获取到 {len(items)} 条")
        return items
    except Exception as e:
        logger.warning(f"知乎热榜获取失败: {e}")
        return []


def fetch_toutiao() -> List[Dict]:
    """获取头条热榜"""
    try:
        resp = requests.get(PLATFORMS["toutiao"]["url"], headers=HEADERS, timeout=10)
        data = resp.json()
        items = []
        for item in data.get("data", []):
            title = item.get("Title", "")
            if title:
                items.append({
                    "platform": "头条热榜",
                    "title": title,
                    "hot": item.get("HotValue", ""),
                    "url": item.get("Url", ""),
                    "raw_query": title,
                    "summary": item.get("LabelDesc", ""),
                })
        logger.info(f"头条热榜: 获取到 {len(items)} 条")
        return items
    except Exception as e:
        logger.warning(f"头条热榜获取失败: {e}")
        return []


def fetch_all() -> List[Dict]:
    """
    采集所有平台热搜数据
    返回格式: [{platform, title, hot, url, raw_query, collected_at}, ...]
    """
    all_items = []
    now = datetime.now().isoformat()

    # 逐个平台采集，失败不影响其他平台
    for fetcher in [fetch_baidu, fetch_weibo, fetch_zhihu, fetch_toutiao, fetch_vertical_news]:
        try:
            items = fetcher()
            for item in items:
                item["collected_at"] = now
            all_items.extend(items)
        except Exception as e:
            logger.error(f"采集失败: {e}")
        time.sleep(0.5)  # 请求间隔，避免太快

    logger.info(f"总计采集到 {len(all_items)} 条热搜")
    return all_items


if __name__ == "__main__":
    # 测试
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    items = fetch_all()
    print(f"\n总计 {len(items)} 条热搜:")
    for item in items[:20]:
        print(f"  [{item['platform']}] {item['title']}")
