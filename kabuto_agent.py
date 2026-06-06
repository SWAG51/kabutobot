"""
自律分析エージェント
10分ごとに全銘柄スキャン・シグナル変化を通知・PTS監視・感情分析・価格アラート確認
売買は人間が行う。エージェントは分析・通知のみ。
"""
import json
import logging
from datetime import datetime
from pathlib import Path

import yfinance as yf

from analyzer import analyze, _fetch_ohlcv
from config import DATA_DIR, DISCORD_WEBHOOK_URL
from pts_monitor import check_pts_alerts
from sentiment import get_sentiment

log = logging.getLogger(__name__)

ANALYSIS_CACHE_FILE  = DATA_DIR / "analysis_cache.json"
MARKET_CACHE_FILE    = DATA_DIR / "market_cache.json"
AGENT_LOG_FILE       = DATA_DIR / "agent_log.json"
PTS_CACHE_FILE       = DATA_DIR / "pts_cache.json"
SENTIMENT_CACHE_FILE = DATA_DIR / "sentiment_cache.json"

MARKET_INDICES = {
    "^N225": "日経225",
    "^GSPC": "S&P500",
    "^IXIC": "NASDAQ",
    "JPY=X": "USD/JPY",
}

EXTRA_US = ["AMD", "META", "AMZN", "CRM", "PLTR", "ARM", "COIN", "SMCI", "UBER", "SNOW"]
EXTRA_JP = ["6098.T", "4063.T", "6902.T", "8035.T", "4568.T", "9983.T", "3659.T"]


class KabutoAgent:
    def __init__(self, trader, watchlist_manager, notifier_mod,
                 settings_manager=None, alert_manager=None):
        self.trader    = trader
        self.watchlist = watchlist_manager
        self.notifier  = notifier_mod
        self.settings  = settings_manager
        self.alerts    = alert_manager
        self._prev_signals: dict  = {}
        self._sentiment_cycle: int = 0

    def cycle(self):
        log.info("[Agent] ─── サイクル開始 ───")
        try:
            self._update_market()
        except Exception as e:
            log.warning(f"[Agent] 市場指数更新失敗: {e}")
        try:
            self._scan_watchlist()
        except Exception as e:
            log.warning(f"[Agent] ウォッチリストスキャン失敗: {e}")
        try:
            self._check_pts()
        except Exception as e:
            log.warning(f"[Agent] PTS確認失敗: {e}")
        try:
            self._check_price_alerts()
        except Exception as e:
            log.warning(f"[Agent] 価格アラート確認失敗: {e}")
        try:
            self._scan_extra()
        except Exception as e:
            log.warning(f"[Agent] 機会探索失敗: {e}")
        self._sentiment_cycle += 1
        # 感情分析は4サイクル(40分)に1回
        if self._sentiment_cycle % 4 == 1:
            try:
                self._update_sentiment()
            except Exception as e:
                log.warning(f"[Agent] 感情分析失敗: {e}")
        # ニュースキャッシュは3サイクル(30分)に1回
        if self._sentiment_cycle % 3 == 1:
            try:
                self._refresh_news()
            except Exception as e:
                log.warning(f"[Agent] ニュース更新失敗: {e}")
        # 基本情報キャッシュは6サイクル(60分)に1回
        if self._sentiment_cycle % 6 == 1:
            try:
                self._refresh_fundamentals()
            except Exception as e:
                log.warning(f"[Agent] 基本情報更新失敗: {e}")
        log.info("[Agent] ─── サイクル完了 ───")

    # ── 市場指数更新 ──

    def _update_market(self):
        result = {}
        for symbol, name in MARKET_INDICES.items():
            try:
                hist = yf.Ticker(symbol).history(period="5d")
                if len(hist) >= 2:
                    curr = float(hist["Close"].iloc[-1])
                    prev = float(hist["Close"].iloc[-2])
                    result[symbol] = {
                        "name":       name,
                        "price":      round(curr, 2),
                        "change_pct": round((curr / prev - 1) * 100, 2),
                    }
            except Exception:
                pass
        _save(MARKET_CACHE_FILE, {"data": result, "updated": _now()})

    # ── ウォッチリスト全銘柄スキャン ──

    def _scan_watchlist(self):
        all_stocks = self.watchlist.get_jp() + self.watchlist.get_us()

        ob = self.settings.get("rsi_overbought", 70) if self.settings else 70
        os = self.settings.get("rsi_oversold",   30) if self.settings else 30

        existing = {}
        if ANALYSIS_CACHE_FILE.exists():
            try:
                existing = json.loads(
                    ANALYSIS_CACHE_FILE.read_text(encoding="utf-8")
                ).get("data", {})
            except Exception:
                pass

        cache = {}
        for stock in all_stocks:
            ticker = stock["ticker"]
            try:
                result = analyze(ticker, rsi_overbought=ob, rsi_oversold=os)
                if result is None:
                    continue

                df = _fetch_ohlcv(ticker)
                if df is not None:
                    close = df["Close"].squeeze()
                    result["prices_20d"] = [
                        round(float(x), 4) for x in close.iloc[-20:].tolist()
                    ]
                    if len(close) >= 2:
                        result["daily_change_pct"] = round(
                            (float(close.iloc[-1]) / float(close.iloc[-2]) - 1) * 100, 2
                        )

                result["name"] = stock.get("name", ticker)

                for key in ("sentiment", "pts"):
                    if ticker in existing and key in existing[ticker]:
                        result[key] = existing[ticker][key]

                cache[ticker] = result

                prev_sig = self._prev_signals.get(ticker)
                curr_sig = result["signal"]
                if prev_sig is not None and prev_sig != curr_sig:
                    self._on_signal_change(ticker, prev_sig, curr_sig, result)
                self._prev_signals[ticker] = curr_sig

            except Exception as e:
                log.warning(f"[Agent] {ticker}: {e}")

        _save(ANALYSIS_CACHE_FILE, {"data": cache, "updated": _now()})
        log.info(f"[Agent] 分析キャッシュ更新: {len(cache)}銘柄")

    def _on_signal_change(self, ticker: str, old: str, new: str, result: dict):
        from scheduler import log_signal
        log_signal(result)
        name = result.get("name", ticker)

        if new == "BUY":
            msg = f"🟢 {name}({ticker}) BUY @ {result['price']} — {result['reason']}"
            _discord_notify(
                f"🟢 BUY シグナル [{name}]",
                f"銘柄: {ticker}\n価格: {result['price']}\n"
                f"理由: {result['reason']}\nRSI: {result['rsi']:.1f}",
                0x34C759,
                self.settings,
            )
        elif new == "SELL":
            msg = f"🔴 {name}({ticker}) SELL @ {result['price']} — {result['reason']}"
            _discord_notify(
                f"🔴 SELL シグナル [{name}]",
                f"銘柄: {ticker}\n価格: {result['price']}\n"
                f"理由: {result['reason']}\nRSI: {result['rsi']:.1f}",
                0xFF3B30,
                self.settings,
            )
        else:
            msg = f"📊 {name}({ticker}) シグナル変化: {old} → {new}"
        _add_log(msg)

    # ── PTS・時間外取引チェック ──

    def _check_pts(self):
        all_stocks = self.watchlist.get_jp() + self.watchlist.get_us()
        alerts = check_pts_alerts(all_stocks, threshold_pct=1.0)
        threshold = self.settings.get("pts_alert_pct", 3.0) if self.settings else 3.0

        pts_map: dict = {}
        for a in alerts:
            pts_map[a["ticker"]] = a
            msg = (
                f"⏰ PTS [{a.get('name', a['ticker'])}] "
                f"{a['pts_change_pct']:+.2f}% @ {a['pts_price']} ({a['pts_type']})"
            )
            _add_log(msg)
            if abs(a["pts_change_pct"]) >= threshold:
                _discord_notify(
                    f"⏰ PTS大変動 [{a.get('name', a['ticker'])}]",
                    f"銘柄: {a['ticker']}\n"
                    f"通常値: {a['regular_price']} → PTS: {a['pts_price']}\n"
                    f"変動率: {a['pts_change_pct']:+.2f}%",
                    0xFF9F0A,
                    self.settings,
                )

        _save(PTS_CACHE_FILE, {"data": pts_map, "updated": _now()})

        if pts_map and ANALYSIS_CACHE_FILE.exists():
            try:
                c = json.loads(ANALYSIS_CACHE_FILE.read_text(encoding="utf-8"))
                for t, pts in pts_map.items():
                    if t in c.get("data", {}):
                        c["data"][t]["pts"] = pts
                ANALYSIS_CACHE_FILE.write_text(
                    json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                pass

    # ── 価格アラートチェック ──

    def _check_price_alerts(self):
        if not self.alerts or not ANALYSIS_CACHE_FILE.exists():
            return
        try:
            cache = json.loads(ANALYSIS_CACHE_FILE.read_text("utf-8")).get("data", {})
            for ticker, data in cache.items():
                price = data.get("price", 0)
                if not price:
                    continue
                for idx, alert in self.alerts.check(ticker, price):
                    name    = alert.get("name", ticker)
                    dir_str = "以上に到達" if alert["direction"] == "above" else "以下に到達"
                    msg = f"🔔 価格アラート [{name}] {price} が {alert['target_price']} {dir_str}"
                    _add_log(msg)
                    _discord_notify(
                        f"🔔 価格アラート [{name}]",
                        f"銘柄: {ticker}\n現在価格: {price}\n"
                        f"目標価格: {alert['target_price']} {dir_str}",
                        0x00C7BE,
                        self.settings,
                    )
        except Exception as e:
            log.warning(f"[Agent] 価格アラート確認失敗: {e}")

    # ── 感情分析更新（40分に1回）──

    def _update_sentiment(self):
        all_stocks = self.watchlist.get_jp() + self.watchlist.get_us()
        sent_map: dict = {}

        for stock in all_stocks:
            ticker = stock["ticker"]
            try:
                s = get_sentiment(ticker)
                sent_map[ticker] = s
            except Exception:
                pass

        _save(SENTIMENT_CACHE_FILE, {"data": sent_map, "updated": _now()})

        if ANALYSIS_CACHE_FILE.exists():
            try:
                c = json.loads(ANALYSIS_CACHE_FILE.read_text(encoding="utf-8"))
                for t, s in sent_map.items():
                    if t in c.get("data", {}):
                        c["data"][t]["sentiment"] = s
                ANALYSIS_CACHE_FILE.write_text(
                    json.dumps(c, ensure_ascii=False, indent=2), encoding="utf-8"
                )
            except Exception:
                pass

        log.info(f"[Agent] 感情分析更新: {len(sent_map)}銘柄")

    # ── ニュースキャッシュ事前更新（30分に1回）──

    def _refresh_news(self):
        from news_fetcher import get_news
        all_stocks = self.watchlist.get_jp() + self.watchlist.get_us()
        count = 0
        for stock in all_stocks:
            ticker = stock["ticker"]
            try:
                get_news(ticker, stock.get("name", ""))
                count += 1
            except Exception:
                pass
        log.info(f"[Agent] ニュースキャッシュ更新: {count}銘柄")

    # ── 基本情報キャッシュ事前更新（60分に1回）──

    def _refresh_fundamentals(self):
        from valuation import get_fundamentals
        all_stocks = self.watchlist.get_jp() + self.watchlist.get_us()
        count = 0
        for stock in all_stocks:
            ticker = stock["ticker"]
            try:
                get_fundamentals(ticker)
                count += 1
            except Exception:
                pass
        log.info(f"[Agent] 基本情報キャッシュ更新: {count}銘柄")

    # ── 監視外銘柄の機会探索 ──

    def _scan_extra(self):
        existing = {s["ticker"] for s in self.watchlist.get_jp() + self.watchlist.get_us()}
        for ticker in EXTRA_US + EXTRA_JP:
            if ticker in existing:
                continue
            try:
                result = analyze(ticker)
                if result and result.get("cross") == "golden":
                    msg = (
                        f"💡 機会発見: {ticker} ゴールデンクロス "
                        f"RSI={result['rsi']:.1f} @{result['price']}"
                    )
                    _add_log(msg)
                    _discord_notify(
                        f"💡 新規機会発見 [{ticker}]",
                        f"ゴールデンクロス発生\n価格: {result['price']}\n"
                        f"RSI: {result['rsi']:.1f}\n→ 監視銘柄への追加を推奨",
                        0x00CED1,
                        self.settings,
                    )
            except Exception:
                pass


# ── ユーティリティ ──

def _now() -> str:
    return datetime.now().isoformat()


def _save(path: Path, data):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        log.warning(f"[Agent] 保存失敗 {path.name}: {e}")


def _add_log(message: str):
    log.info(f"[Agent] {message}")
    logs = []
    if AGENT_LOG_FILE.exists():
        try:
            logs = json.loads(AGENT_LOG_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    logs.append({"time": _now(), "msg": message})
    _save(AGENT_LOG_FILE, logs[-300:])


def _discord_notify(title: str, desc: str, color: int, settings=None):
    url     = DISCORD_WEBHOOK_URL
    enabled = True
    if settings:
        s_url = settings.get("discord_webhook", "")
        if s_url:
            url = s_url
        enabled = settings.get("discord_enabled", True)
    if not url or not enabled:
        return
    try:
        import requests
        requests.post(
            url,
            json={"embeds": [{"title": title, "description": desc, "color": color}]},
            timeout=5,
        )
    except Exception:
        pass
