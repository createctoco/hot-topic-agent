"""
定时调度模块
每天发布10篇文章，分散在 8:00-22:00 之间
"""
import os
import time
import logging
import schedule
from datetime import datetime
from main import run_once, load_config

logger = logging.getLogger("scheduler")


def generate_schedule_times(daily_count: int = 10) -> list:
    """
    生成每天发布的时间点列表
    10篇文章分散在 8:00-22:00 之间，间隔约1.4小时
    """
    start_hour = 8
    end_hour = 22
    total_minutes = (end_hour - start_hour) * 60
    if daily_count <= 1:
        return [f"{start_hour:02d}:00"]

    interval = total_minutes // (daily_count - 1)
    times = []
    for i in range(daily_count):
        minutes = start_hour * 60 + i * interval
        hour = minutes // 60
        minute = minutes % 60
        times.append(f"{hour:02d}:{minute:02d}")

    logger.info(f"定时发布时间表 ({daily_count}篇/天): {', '.join(times)}")
    return times


def publish_job():
    """单次发布任务"""
    logger.info(f"定时任务触发: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    try:
        config = load_config()
        stats = run_once(config, articles_count=1)  # 每次发布1篇
        logger.info(f"发布完成: 成功{stats['published']}篇, 失败{stats['failed']}篇")
    except Exception as e:
        logger.error(f"定时任务异常: {e}")


def start_scheduler(config: dict):
    """
    启动定时调度
    """
    daily_count = config.get("daily_count", 10)

    # 生成发布时间表
    times = generate_schedule_times(daily_count)

    # 注册定时任务
    for t in times:
        schedule.every().day.at(t).do(publish_job)
        logger.info(f"已注册定时任务: 每天 {t} 发布")

    logger.info(f"\n{'='*50}")
    logger.info(f"热搜自动发文系统已启动！")
    logger.info(f"每天发布 {daily_count} 篇文章")
    logger.info(f"发布时间: {', '.join(times)}")
    logger.info(f"领域: 跨境电商、外贸、AI、科技")
    logger.info(f"{'='*50}\n")

    # 立即执行一次（可选）—— 非交互模式跳过
    run_now = os.environ.get("RUN_NOW", "").lower() in ("1", "true", "yes", "y")
    if run_now:
        logger.info("环境变量 RUN_NOW=true，立即执行一次")
        stats = run_once(config)
        logger.info(f"首次执行完成: 发布{stats['published']}篇")
    elif os.environ.get("NON_INTERACTIVE", "").lower() in ("1", "true"):
        logger.info("非交互模式，跳过首次执行确认")
    else:
        logger.info("是否立即执行一次？(y/n): ", end="")
        try:
            user_input = input().strip().lower()
            if user_input == "y":
                stats = run_once(config)
                logger.info(f"首次执行完成: 发布{stats['published']}篇")
        except (EOFError, KeyboardInterrupt):
            pass

    # 持续运行
    logger.info("定时调度已启动，按 Ctrl+C 退出...")
    try:
        while True:
            schedule.run_pending()
            time.sleep(30)  # 每30秒检查一次
    except KeyboardInterrupt:
        logger.info("程序已停止")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    )
    config = load_config()
    start_scheduler(config)
