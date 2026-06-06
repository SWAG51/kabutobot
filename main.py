"""kabutobot - 株式ペーパートレード自動売買Bot"""
import io
import logging
import signal
import sys
import threading
import time

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

import notifier
from config import DASHBOARD_PORT, WatchlistManager
from kabuto_agent import KabutoAgent
from dashboard import create_app
from paper_trader import PaperTrader
from scheduler import create_scheduler, add_agent_job

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("kabutobot.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

for _noisy in ("httpx", "httpcore", "yfinance", "urllib3", "peewee",
               "apscheduler", "werkzeug"):
    logging.getLogger(_noisy).setLevel(logging.WARNING)


def main():
    log.info("=" * 50)
    log.info("=== kabutobot 起動 ===")
    log.info("=" * 50)

    trader    = PaperTrader()
    watchlist = WatchlistManager()
    agent     = KabutoAgent(trader, watchlist, notifier)

    # スケジューラー起動
    sched = create_scheduler(trader, watchlist, notifier)
    add_agent_job(sched, agent)
    sched.start()
    log.info("[Scheduler] スケジューラー起動完了（エージェント10分ごと）")

    # ダッシュボード起動（別スレッド）
    app = create_app(trader, watchlist, notifier, agent=agent)
    threading.Thread(
        target=lambda: app.run(host="0.0.0.0", port=DASHBOARD_PORT,
                               debug=False, use_reloader=False),
        daemon=True,
        name="dashboard",
    ).start()
    log.info(f"[Dashboard] http://0.0.0.0:{DASHBOARD_PORT} 起動")

    # 初回エージェントサイクルをバックグラウンドで即時実行
    threading.Thread(target=agent.cycle, daemon=True, name="agent-init").start()
    log.info("[Agent] 初回スキャン開始（バックグラウンド）")

    # Graceful shutdown
    def shutdown(signum, frame):
        log.info("=== kabutobot 停止 ===")
        sched.shutdown(wait=False)
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    log.info("[kabutobot] 稼働中。Ctrl+C で停止")
    while True:
        time.sleep(60)


if __name__ == "__main__":
    main()
