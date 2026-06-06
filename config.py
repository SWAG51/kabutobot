"""設定値・ウォッチリスト管理"""
import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

# Discord
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "")

# 資金設定
INITIAL_BALANCE_USD = float(os.environ.get("INITIAL_BALANCE_USD", "100000"))
INITIAL_BALANCE_JPY = float(os.environ.get("INITIAL_BALANCE_JPY", "10000000"))
MAX_POSITION_PCT    = float(os.environ.get("MAX_POSITION_PCT",    "10")) / 100
STOP_LOSS_PCT       = float(os.environ.get("STOP_LOSS_PCT",       "5"))  / 100
TAKE_PROFIT_PCT     = float(os.environ.get("TAKE_PROFIT_PCT",     "15")) / 100
MAX_POSITIONS       = int(os.environ.get("MAX_POSITIONS",         "10"))

# ダッシュボード
DASHBOARD_PORT = int(os.environ.get("DASHBOARD_PORT", "5057"))

# テクニカル指標
SHORT_MA        = 5
LONG_MA         = 25
RSI_PERIOD      = 14
RSI_OVERBOUGHT  = 70
RSI_OVERSOLD    = 30

# データファイル
POSITIONS_FILE = DATA_DIR / "positions.json"
TRADES_FILE    = DATA_DIR / "trades.json"
BALANCE_FILE   = DATA_DIR / "balance.json"
SIGNALS_FILE   = DATA_DIR / "signals.json"
WATCHLIST_FILE = DATA_DIR / "watchlist.json"


class WatchlistManager:
    _DEFAULT_JP = [
        {"ticker": "7203.T", "name": "トヨタ自動車"},
        {"ticker": "6758.T", "name": "ソニーグループ"},
        {"ticker": "7974.T", "name": "任天堂"},
        {"ticker": "9984.T", "name": "ソフトバンクグループ"},
        {"ticker": "6861.T", "name": "キーエンス"},
    ]
    _DEFAULT_US = [
        {"ticker": "AAPL",  "name": "アップル"},
        {"ticker": "GOOGL", "name": "グーグル"},
        {"ticker": "MSFT",  "name": "マイクロソフト"},
        {"ticker": "NVDA",  "name": "エヌビディア"},
        {"ticker": "TSLA",  "name": "テスラ"},
    ]

    def __init__(self):
        self._jp: list = []
        self._us: list = []
        self.load()

    def get_jp(self) -> list:
        return list(self._jp)

    def get_us(self) -> list:
        return list(self._us)

    def add(self, ticker: str, name: str, market: str):
        lst = self._jp if market == "JP" else self._us
        if not any(s["ticker"] == ticker for s in lst):
            lst.append({"ticker": ticker, "name": name})
            self.save()

    def remove(self, ticker: str, market: str):
        if market == "JP":
            self._jp = [s for s in self._jp if s["ticker"] != ticker]
        else:
            self._us = [s for s in self._us if s["ticker"] != ticker]
        self.save()

    def rename(self, ticker: str, name: str, market: str):
        lst = self._jp if market == "JP" else self._us
        for s in lst:
            if s["ticker"] == ticker:
                s["name"] = name
                self.save()
                break

    def save(self):
        try:
            WATCHLIST_FILE.write_text(
                json.dumps({"jp": self._jp, "us": self._us}, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
        except Exception:
            pass

    def load(self):
        if WATCHLIST_FILE.exists():
            try:
                data = json.loads(WATCHLIST_FILE.read_text(encoding="utf-8"))
                self._jp = data.get("jp", list(self._DEFAULT_JP))
                self._us = data.get("us", list(self._DEFAULT_US))
                return
            except Exception:
                pass
        self._jp = list(self._DEFAULT_JP)
        self._us = list(self._DEFAULT_US)
