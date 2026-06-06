"""ニュース取得モジュール
- 日本株: Google News RSS (無料・スクレイピングなし)
- 米国株: yfinance .news
- SQLiteキャッシュ TTL=30分
"""
import logging
import urllib.parse

import yfinance as yf

import cache_db

log      = logging.getLogger(__name__)
_NEWS_TTL = 1800  # 30分


def get_news(ticker: str, company_name: str = "") -> list[dict]:
    key    = f"news_{ticker}"
    cached = cache_db.get(key)
    if cached is not None:
        return cached

    is_jp = ticker.endswith(".T")
    news  = []

    if is_jp:
        news = _fetch_google_rss(company_name or ticker, ticker)
    else:
        news = _fetch_yf_news(ticker)

    cache_db.set(key, news, _NEWS_TTL)
    return news


def _fetch_google_rss(name: str, ticker: str) -> list[dict]:
    try:
        import feedparser
    except ImportError:
        log.warning("[news] feedparser未インストール: pip install feedparser")
        return []
    try:
        q    = urllib.parse.quote(name)
        url  = f"https://news.google.com/rss/search?q={q}&hl=ja&gl=JP&ceid=JP:ja"
        feed = feedparser.parse(url)
        result = []
        for e in (feed.entries or [])[:12]:
            result.append({
                "title":     e.get("title", ""),
                "link":      e.get("link", ""),
                "publisher": (e.get("source") or {}).get("title", ""),
                "published": e.get("published", "")[:16] if e.get("published") else "",
            })
        return result
    except Exception as e:
        log.warning(f"[news] Google RSS {ticker}: {e}")
        return []


def _fetch_yf_news(ticker: str) -> list[dict]:
    try:
        raw = yf.Ticker(ticker).news or []
        return [{
            "title":     n.get("title", ""),
            "link":      n.get("link", ""),
            "publisher": n.get("publisher", ""),
            "published": "",
        } for n in raw[:12]]
    except Exception as e:
        log.warning(f"[news] yfinance {ticker}: {e}")
        return []
