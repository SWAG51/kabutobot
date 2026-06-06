"""ニュース感情分析モジュール (yfinance news + キーワードスコアリング)"""
import logging

import yfinance as yf

log = logging.getLogger(__name__)

_POS = [
    "beat", "record", "surge", "rally", "strong", "profit", "growth",
    "upgrade", "buy", "bullish", "soar", "jump", "rise", "gain", "boost",
    "上昇", "好調", "増益", "強気", "上方修正", "最高値",
]
_NEG = [
    "miss", "decline", "fall", "weak", "loss", "downgrade", "sell",
    "bearish", "drop", "slump", "cut", "concern", "warn", "disappoint",
    "下落", "不調", "減益", "弱気", "下方修正", "最安値",
]


def get_sentiment(ticker: str) -> dict:
    """yfinance ニュースをキーワードスコアリングして感情スコアを返す。
    score: -1.0(弱気) ~ +1.0(強気)  /  label: 強気|中立|弱気|N/A
    """
    try:
        news = yf.Ticker(ticker).news or []
        total = 0.0
        items = []
        for n in news[:10]:
            title = (n.get("title") or "").lower()
            pos = sum(1 for w in _POS if w in title)
            neg = sum(1 for w in _NEG if w in title)
            s = pos - neg
            total += s
            items.append({
                "title":     n.get("title", ""),
                "publisher": n.get("publisher", ""),
                "link":      n.get("link", ""),
                "score":     s,
            })

        count = len(items) or 1
        normalized = round(total / count, 2)

        if normalized > 0.3:
            label, color = "強気", "#34c759"
        elif normalized < -0.3:
            label, color = "弱気", "#ff3b30"
        else:
            label, color = "中立", "#8e8e93"

        return {
            "score": normalized,
            "label": label,
            "color": color,
            "news":  items[:5],
            "count": count,
        }
    except Exception as e:
        log.debug(f"[Sentiment] {ticker}: {e}")
        return {"score": 0.0, "label": "N/A", "color": "#8e8e93", "news": [], "count": 0}
