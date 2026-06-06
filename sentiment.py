"""感情分析モジュール
- 米国株: vaderSentiment (ローカル・無料) → フォールバックでキーワード法
- 日本株: キーワード辞書方式
- 結果には「AI/簡易推定」を明記（投資助言ではない）
"""
import logging

import yfinance as yf

log = logging.getLogger(__name__)

# ── キーワード辞書（JP/EN共用） ──
_POS = [
    "beat","record","surge","rally","strong","profit","growth",
    "upgrade","buy","bullish","soar","jump","rise","gain","boost","exceed",
    "上昇","好調","増益","強気","上方修正","最高値","増収","黒字","回復","拡大",
]
_NEG = [
    "miss","decline","fall","weak","loss","downgrade","sell",
    "bearish","drop","slump","cut","concern","warn","disappoint","shortfall",
    "下落","不調","減益","弱気","下方修正","最安値","減収","赤字","低迷","縮小",
]


def get_sentiment(ticker: str) -> dict:
    """感情スコアを返す。score: -1.0(弱気)〜+1.0(強気)
    ※AI/簡易推定。精度は限定的。投資助言ではありません。
    """
    try:
        news = yf.Ticker(ticker).news or []
        items = _score_items(news)
        return _aggregate(items)
    except Exception as e:
        log.debug(f"[Sentiment] {ticker}: {e}")
        return _empty()


def get_sentiment_from_news(news_list: list, ticker: str = "") -> dict:
    """news_fetcherから取得したニュースリストを採点する"""
    if not news_list:
        return _empty()
    is_us = not ticker.endswith(".T") if ticker else True
    if is_us:
        result = _try_vader(news_list)
        if result:
            return result
    items = _score_items(news_list)
    return _aggregate(items)


def _try_vader(news_list: list) -> dict | None:
    """vaderSentimentでUS株ニュースを採点。インポート失敗なら None を返す"""
    try:
        from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
        analyzer = SentimentIntensityAnalyzer()
        items = []
        for n in news_list:
            title = n.get("title", "")
            vs    = analyzer.polarity_scores(title)
            s     = round(vs["compound"], 3)
            items.append({
                "title":     title,
                "publisher": n.get("publisher", ""),
                "link":      n.get("link", ""),
                "score":     s,
            })
        if not items:
            return None
        avg = sum(i["score"] for i in items) / len(items)
        return {
            "score":  round(avg, 3),
            "label":  _label(avg),
            "color":  _color(avg),
            "news":   items[:6],
            "count":  len(items),
            "method": "VADER（簡易推定）",
        }
    except ImportError:
        log.debug("[Sentiment] vaderSentiment 未インストール → キーワード法で代替")
        return None
    except Exception as e:
        log.debug(f"[Sentiment] VADER失敗: {e}")
        return None


def _score_items(news_list: list) -> list:
    scored = []
    for n in news_list[:12]:
        title = (n.get("title") or "").lower()
        pos   = sum(1 for w in _POS if w in title)
        neg   = sum(1 for w in _NEG if w in title)
        s     = pos - neg
        scored.append({
            "title":     n.get("title", ""),
            "publisher": n.get("publisher", ""),
            "link":      n.get("link", ""),
            "score":     s,
        })
    return scored


def _aggregate(items: list) -> dict:
    if not items:
        return _empty()
    total = sum(i["score"] for i in items)
    count = len(items)
    norm  = round(total / count, 3)
    return {
        "score":  norm,
        "label":  _label(norm),
        "color":  _color(norm),
        "news":   items[:6],
        "count":  count,
        "method": "キーワード法（簡易推定）",
    }


def _label(score: float) -> str:
    if score > 0.3:  return "強気"
    if score < -0.3: return "弱気"
    return "中立"


def _color(score: float) -> str:
    if score > 0.3:  return "#34c759"
    if score < -0.3: return "#ff3b30"
    return "#8e8e93"


def _empty() -> dict:
    return {"score": 0.0, "label": "N/A", "color": "#8e8e93",
            "news": [], "count": 0, "method": "—"}
