"""
PTS（私設取引システム）/ 時間外取引モニター
米国株: preMarketPrice / postMarketPrice
日本株: yfinance info の同フィールドを利用
"""
import logging
from datetime import datetime

import yfinance as yf
import pytz

log = logging.getLogger(__name__)
JST = pytz.timezone("Asia/Tokyo")


def get_pts_data(ticker: str) -> dict | None:
    """PTS・時間外価格を取得して返す。データなしなら None。"""
    try:
        info = yf.Ticker(ticker).info
        reg  = (info.get("regularMarketPrice")
                or info.get("currentPrice")
                or info.get("ask") or 0)

        post = info.get("postMarketPrice")
        pre  = info.get("preMarketPrice")
        pts  = post or pre
        if not pts or pts == reg:
            return None

        post_pct = info.get("postMarketChangePercent")
        pre_pct  = info.get("preMarketChangePercent")
        pts_pct  = post_pct or pre_pct or 0

        # yfinanceはバージョンによって小数(0.02)と%値(2.0)が混在
        if pts_pct and abs(pts_pct) < 1.0:
            pts_pct *= 100

        return {
            "ticker":         ticker,
            "regular_price":  round(float(reg), 4),
            "pts_price":      round(float(pts), 4),
            "pts_type":       "post" if post else "pre",
            "pts_change_pct": round(float(pts_pct), 2),
            "timestamp":      datetime.now(JST).isoformat(),
        }
    except Exception as e:
        log.debug(f"[PTS] {ticker}: {e}")
        return None


def check_pts_alerts(stocks: list, threshold_pct: float = 2.0) -> list[dict]:
    """閾値以上の変動があった銘柄リストを返す"""
    alerts = []
    for stock in stocks:
        data = get_pts_data(stock["ticker"])
        if not data:
            continue
        chg = abs(data["pts_change_pct"])
        if chg >= threshold_pct:
            data["name"]      = stock.get("name", stock["ticker"])
            data["alert_pct"] = chg
            alerts.append(data)
            log.info(f"[PTS] {stock['ticker']}: {data['pts_change_pct']:+.2f}%")
    return alerts
