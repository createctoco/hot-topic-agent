"""
热搜自动发文系统 - 主程序
串联：热搜采集 → 关键词过滤 → AI生成文章 → 自动发布头条
"""
import os
import sys
import json
import time
import logging
import yaml
from datetime import datetime
from pathlib import Path

# 添加项目根目录到 path
PROJECT_ROOT = Path(__file__).parent
sys.path.insert(0, str(PROJECT_ROOT))

from modules.hot_search import fetch_all
from modules.keyword_filter import filter_items, select_topics
from modules.ai_writer import AIWriter
from modules.publisher import ToutiaoPublisher

# 日志配置
log_dir = PROJECT_ROOT / "data" / "logs"
log_dir.mkdir(parents=True, exist_ok=True)
log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("main")


def load_config() -> dict:
    """加载配置文件"""
    config_path = PROJECT_ROOT / "config.yaml"
    if not config_path.exists():
        logger.error("config.yaml 不存在，请复制 config.yaml.example 为 config.yaml 并填写配置")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # 环境变量覆盖（优先使用环境变量中的 API Key）
    if os.getenv("DEEPSEEK_API_KEY"):
        config["deepseek"]["api_key"] = os.getenv("DEEPSEEK_API_KEY")

    return config


def load_published_history() -> list:
    """加载已发布文章记录"""
    history_file = PROJECT_ROOT / "data" / "published.json"
    if history_file.exists():
        with open(history_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []


def save_published_history(history: list):
    """保存已发布文章记录"""
    history_file = PROJECT_ROOT / "data" / "published.json"
    with open(history_file, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def run_once(config: dict, articles_count: int = None) -> dict:
    """
    执行一次完整的流程：采集 → 过滤 → 生成 → 发布
    返回执行结果统计
    """
    stats = {
        "start_time": datetime.now().isoformat(),
        "collected": 0,
        "filtered": {},
        "generated": 0,
        "published": 0,
        "failed": 0,
        "articles": [],
    }

    count = articles_count or config.get("daily_count", 10)

    # ============ 1. 采集热搜 ============
    logger.info("=" * 50)
    logger.info("第1步：采集热搜关键词")
    logger.info("=" * 50)
    items = fetch_all()
    stats["collected"] = len(items)

    if not items:
        logger.warning("未采集到任何热搜，跳过本轮")
        stats["end_time"] = datetime.now().isoformat()
        return stats

    # ============ 2. 关键词过滤 ============
    logger.info("=" * 50)
    logger.info("第2步：按领域过滤热搜")
    logger.info("=" * 50)
    filtered = filter_items(items)
    stats["filtered"] = {k: len(v) for k, v in filtered.items()}

    # ============ 3. 选题 ============
    logger.info("=" * 50)
    logger.info(f"第3步：选取 {count} 个选题")
    logger.info("=" * 50)
    selected = select_topics(filtered, count)

    if not selected:
        logger.warning("没有匹配的选题，跳过本轮")
        stats["end_time"] = datetime.now().isoformat()
        return stats

    # ============ 4. AI 生成 + 发布 ============
    logger.info("=" * 50)
    logger.info("第4步：AI生成文章并发布")
    logger.info("=" * 50)

    # 初始化 AI Writer
    deepseek_config = config.get("deepseek", {})
    api_key = deepseek_config.get("api_key", "")
    if not api_key or api_key == "sk-your-deepseek-api-key":
        logger.error("DeepSeek API Key 未配置！请在 config.yaml 或环境变量 DEEPSEEK_API_KEY 中设置")
        stats["end_time"] = datetime.now().isoformat()
        return stats

    writer = AIWriter(
        api_key=api_key,
        base_url=deepseek_config.get("base_url", "https://api.deepseek.com"),
    )

    # 初始化发布器（非 dry_run 才检查登录）
    publisher = ToutiaoPublisher(work_dir=str(PROJECT_ROOT)) if not dry_run else None

    # 检查登录状态（仅真实发布模式）
    if not dry_run and not publisher.check_login():
        logger.warning("头条未登录！请先运行: python main.py --login")
        logger.warning("登录后重新运行程序")
        stats["end_time"] = datetime.now().isoformat()
        return stats

    # 加载历史记录（避免重复发布）
    history = load_published_history()
    published_titles = {h.get("title", "") for h in history}

    # 逐个生成并发布
    for i, topic in enumerate(selected, 1):
        logger.info(f"\n--- 处理第 {i}/{len(selected)} 篇 ---")
        logger.info(f"选题: [{topic['category']}] {topic['title']}")

        # 跳过已发布的
        if topic["title"] in published_titles:
            logger.info(f"  该选题已发布过，跳过")
            continue

        try:
            # AI 生成文章
            article = writer.generate_article(
                hot_title=topic["title"],
                category=topic["category"],
                platform=topic.get("platform", ""),
            )

            # 保存文章到文件
            article_dir = PROJECT_ROOT / "data" / "articles"
            article_dir.mkdir(parents=True, exist_ok=True)
            article_file = article_dir / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{i}.json"
            with open(article_file, "w", encoding="utf-8") as f:
                json.dump(article, f, ensure_ascii=False, indent=2)

            # 发布到头条
            publish_config = config.get("publish", {})
            cover_keyword = article.get("image_keywords", [""])[0] if article.get("image_keywords") else ""
            result = publisher.publish_article(
                title=article["title"],
                content=article["content"],
                category=article["category"],
                first_publish=publish_config.get("first_publish", True),
                ai_generated=publish_config.get("ai_declared", True),
                cover_keyword=cover_keyword,
            )

            if result["success"]:
                stats["published"] += 1
                logger.info(f"  ✅ 发布成功: {article['title']}")
            else:
                stats["failed"] += 1
                logger.error(f"  ❌ 发布失败: {result['message']}")

            # 记录历史
            history.append({
                "title": article["title"],
                "source_topic": topic["title"],
                "category": topic["category"],
                "published_at": datetime.now().isoformat(),
                "success": result["success"],
                "article_file": str(article_file),
            })
            save_published_history(history)
            published_titles.add(topic["title"])

            stats["generated"] += 1
            stats["articles"].append({
                "title": article["title"],
                "category": article["category"],
                "source": topic["title"],
                "success": result["success"],
            })

            # 间隔等待，避免发布太快
            if i < len(selected):
                wait_time = config.get("publish", {}).get("interval_seconds", 60)
                logger.info(f"  等待 {wait_time} 秒后继续...")
                time.sleep(wait_time)

        except Exception as e:
            logger.error(f"  ❌ 处理失败: {e}")
            stats["failed"] += 1
            continue

    stats["end_time"] = datetime.now().isoformat()
    return stats


def main():
    """主入口"""
    import argparse
    parser = argparse.ArgumentParser(description="热搜自动发文系统")
    parser.add_argument("--login", action="store_true", help="登录今日头条")
    parser.add_argument("--test-search", action="store_true", help="测试热搜采集")
    parser.add_argument("--test-filter", action="store_true", help="测试关键词过滤")
    parser.add_argument("--count", type=int, default=None, help="本次发布文章数量")
    parser.add_argument("--once", action="store_true", help="执行一次后退出（不启动定时）")
    parser.add_argument("--dry-run", action="store_true", help="生成文章但不发布到头条（测试用）")
    args = parser.parse_args()

    # 测试命令不需要 config.yaml
    if args.test_search:
        # 测试热搜采集
        items = fetch_all()
        print(f"\n总计 {len(items)} 条热搜:")
        for item in items[:30]:
            print(f"  [{item['platform']}] {item['title']}")
        return

    if args.test_filter:
        # 测试过滤
        items = fetch_all()
        filtered = filter_items(items)
        print("\n过滤结果:")
        for cat, cat_items in filtered.items():
            print(f"\n【{cat}】({len(cat_items)}条)")
            for item in cat_items:
                print(f"  - {item['title']} ({item['platform']})")

        # 选取选题（默认10个，不需要 config）
        selected = select_topics(filtered, 10)
        print(f"\n选中 {len(selected)} 个选题:")
        for s in selected:
            print(f"  [{s['category']}] {s['title']}")
        return

    # 以下命令需要 config
    config = load_config()

    if args.login:
        # 登录头条
        publisher = ToutiaoPublisher(work_dir=str(PROJECT_ROOT))
        publisher.login()
        return

    if args.once:
        # 执行一次
        stats = run_once(config, args.count)
        print(f"\n{'='*50}")
        print(f"执行完成！")
        print(f"  采集热搜: {stats['collected']} 条")
        print(f"  过滤结果: {stats['filtered']}")
        print(f"  生成文章: {stats['generated']} 篇")
        print(f"  发布成功: {stats['published']} 篇")
        print(f"  发布失败: {stats['failed']} 篇")
        return

    # 默认：启动定时调度
    from modules.scheduler import start_scheduler
    start_scheduler(config)


if __name__ == "__main__":
    main()
