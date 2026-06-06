"""スケジュール管理: 市場時間に合わせた自動スキャン"""
import json
import logging
from datetime import datetime

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from config import SIGNALS_FILE

log = logging.getLogger(__name__)
JST = pytz.timezone("Asia/Tokyo")


def _is_weekday() -> bool:
    return datetime.now(JST).weekday() < 5  # 0=月 4=金


def log_signal(result: dict):
    signals = []
    if SIGNALS_FILE.exists():
        try:
            signals = json.loads(SIGNALS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    signals.append(result)
    try:
        SIGNALS_FILE.write_text(
            json.dumps(signals[-500:], ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except Exception as e:
        log.warning(f"[Scheduler] シグナル保存失敗: {e}")


def _scan(trader, watchlist_manager, notifier_mod, market: str):
    """指定市場の全銘柄をスキャンしてシグナル記録・通知（売買は人間が行う）"""
    from analyzer import analyze

    stocks = watchlist_manager.get_jp() if market == "JP" else watchlist_manager.get_us()
    log.info(f"[Scheduler] {market}スキャン開始 ({len(stocks)}銘柄)")

    for stock in stocks:
        ticker = stock["ticker"]
        try:
            result = analyze(ticker)
            if result is None:
                continue
            log_signal(result)

            if result["signal"] == "BUY":
                try:
                    notifier_mod.notify_buy_signal(result)
                except Exception:
                    pass
            elif result["signal"] == "SELL":
                try:
                    notifier_mod.notify_sell_signal(result)
                except Exception:
                    pass

        except Exception as e:
            log.warning(f"[Scheduler] {ticker} スキャンエラー: {e}")


def job_jp_scan(trader, watchlist_manager, notifier_mod):
    if not _is_weekday():
        return
    _scan(trader, watchlist_manager, notifier_mod, "JP")


def job_us_scan(trader, watchlist_manager, notifier_mod):
    if not _is_weekday():
        return
    _scan(trader, watchlist_manager, notifier_mod, "US")


def job_swing_scan(trader, watchlist_manager, notifier_mod):
    """毎朝 8:05 全銘柄スキャン（シグナル記録・通知のみ）"""
    log.info("[Scheduler] スイングスキャン開始")
    from analyzer import analyze

    for stock in watchlist_manager.get_jp() + watchlist_manager.get_us():
        try:
            result = analyze(stock["ticker"])
            if result is None:
                continue
            log_signal(result)
            if result["signal"] == "BUY":
                try:
                    notifier_mod.notify_buy_signal(result)
                except Exception:
                    pass
            elif result["signal"] == "SELL":
                try:
                    notifier_mod.notify_sell_signal(result)
                except Exception:
                    pass
        except Exception as e:
            log.warning(f"[Scheduler] {stock['ticker']} スイングエラー: {e}")


def job_monitor_positions(trader, notifier_mod):
    """5分ごとにポジション監視（損切り・利確）"""
    if not trader.positions:
        return
    from analyzer import get_current_price

    prices = {}
    for ticker in list(trader.positions.keys()):
        try:
            p = get_current_price(ticker)
            if p:
                prices[ticker] = p
        except Exception:
            pass

    triggered = trader.update_positions(prices)
    for event in triggered:
        try:
            if event["type"] == "stop_loss":
                notifier_mod.notify_stop_loss(event)
            elif event["type"] == "take_profit":
                notifier_mod.notify_take_profit(event)
        except Exception as e:
            log.warning(f"[Scheduler] 通知エラー: {e}")


def job_morning_report(trader, notifier_mod):
    try:
        notifier_mod.notify_morning_report(trader.get_stats(), trader.positions)
    except Exception as e:
        log.warning(f"[Scheduler] 朝レポートエラー: {e}")


def job_weekly_report(trader, notifier_mod):
    try:
        notifier_mod.notify_weekly_report(trader.get_stats())
    except Exception as e:
        log.warning(f"[Scheduler] 週次レポートエラー: {e}")


def create_scheduler(trader, watchlist_manager, notifier_mod) -> BackgroundScheduler:
    sched = BackgroundScheduler(timezone="Asia/Tokyo")

    # 毎朝レポート (8:00 JST)
    sched.add_job(job_morning_report, CronTrigger(hour=8, minute=0, timezone="Asia/Tokyo"),
                  args=[trader, notifier_mod])

    # スイングスキャン (8:05 JST)
    sched.add_job(job_swing_scan, CronTrigger(hour=8, minute=5, timezone="Asia/Tokyo"),
                  args=[trader, watchlist_manager, notifier_mod])

    # 日本株オープン (9:00 JST)
    sched.add_job(job_jp_scan, CronTrigger(hour=9, minute=0, timezone="Asia/Tokyo"),
                  args=[trader, watchlist_manager, notifier_mod])

    # 日本株クローズ前 (15:25 JST)
    sched.add_job(job_jp_scan, CronTrigger(hour=15, minute=25, timezone="Asia/Tokyo"),
                  args=[trader, watchlist_manager, notifier_mod])

    # 米国株オープン (22:30 JST)
    sched.add_job(job_us_scan, CronTrigger(hour=22, minute=30, timezone="Asia/Tokyo"),
                  args=[trader, watchlist_manager, notifier_mod])

    # 米国株クローズ前 (5:00 JST)
    sched.add_job(job_us_scan, CronTrigger(hour=5, minute=0, timezone="Asia/Tokyo"),
                  args=[trader, watchlist_manager, notifier_mod])

    # ポジション監視 (5分ごと)
    sched.add_job(job_monitor_positions, CronTrigger(minute="*/5", timezone="Asia/Tokyo"),
                  args=[trader, notifier_mod])

    # 週次レポート (日曜 20:00 JST)
    sched.add_job(job_weekly_report,
                  CronTrigger(day_of_week="sun", hour=20, minute=0, timezone="Asia/Tokyo"),
                  args=[trader, notifier_mod])

    return sched


def add_agent_job(sched: BackgroundScheduler, agent):
    """エージェントを10分ごとに実行"""
    sched.add_job(
        agent.cycle,
        CronTrigger(minute="*/10", timezone="Asia/Tokyo"),
    )
