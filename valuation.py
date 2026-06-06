"""基本情報・評価データ（yfinance .info から取得、SQLiteキャッシュ TTL=1時間）
※ yfinanceは遅延データ。投資助言ではなく情報表示用。
"""
import logging

import yfinance as yf

import cache_db

log   = logging.getLogger(__name__)
_TTL  = 3600   # 1時間
_REASONABLE_PER_JP = 15.0  # 日本株の保守的な妥当PER（AI/簡易推定）


def get_fundamentals(ticker: str) -> dict:
    """基本情報を取得。失敗しても空dictを返す（ページ落ちしない）"""
    key    = f"fund_{ticker}"
    cached = cache_db.get(key)
    if cached is not None:
        return cached

    data = {}
    try:
        info = yf.Ticker(ticker).info

        data = {
            # バリュエーション
            "per":              _f(info.get("trailingPE")),
            "forward_per":      _f(info.get("forwardPE")),
            "pbr":              _f(info.get("priceToBook")),
            "psr":              _f(info.get("priceToSalesTrailing12Months")),
            # 収益性
            "roe":              _pct(info.get("returnOnEquity")),
            "roa":              _pct(info.get("returnOnAssets")),
            "gross_margin":     _pct(info.get("grossMargins")),
            "operating_margin": _pct(info.get("operatingMargins")),
            # 1株指標
            "eps":              _f(info.get("trailingEps")),
            "forward_eps":      _f(info.get("forwardEps")),
            "dividend_yield":   _pct(info.get("dividendYield")),
            "dividend_per":     _f(info.get("lastDividendValue")),
            # 規模・リスク
            "market_cap":       info.get("marketCap"),
            "beta":             _f(info.get("beta")),
            "52w_high":         _f(info.get("fiftyTwoWeekHigh")),
            "52w_low":          _f(info.get("fiftyTwoWeekLow")),
            "avg_volume":       info.get("averageVolume"),
            # 成長
            "revenue_growth":   _pct(info.get("revenueGrowth")),
            "earnings_growth":  _pct(info.get("earningsGrowth")),
            # 属性
            "sector":           info.get("sector") or info.get("category") or "",
            "industry":         info.get("industry") or "",
            "currency":         info.get("currency", "USD"),
            "exchange":         info.get("exchange", ""),
            "employees":        info.get("fullTimeEmployees"),
            # 米国: アナリスト評価
            "target_mean":      _f(info.get("targetMeanPrice")),
            "target_high":      _f(info.get("targetHighPrice")),
            "target_low":       _f(info.get("targetLowPrice")),
            "recommendation":   info.get("recommendationKey", ""),
            "analyst_count":    info.get("numberOfAnalystOpinions"),
        }

        curr = _f(info.get("currentPrice") or info.get("regularMarketPrice"))
        data["current_price"] = curr

        if ticker.endswith(".T"):
            # 日本株: 簡易理論株価 EPS × 妥当PER（AI/簡易推定）
            eps = data.get("eps")
            if eps and eps > 0:
                data["theoretical_price"] = round(eps * _REASONABLE_PER_JP)
                data["theoretical_note"] = (
                    f"EPS({eps:.1f}円) × 妥当PER{_REASONABLE_PER_JP:.0f}倍"
                    " ※AI/簡易推定・投資助言ではありません"
                )
                if curr and curr > 0:
                    upside = (data["theoretical_price"] / curr - 1) * 100
                    data["theoretical_upside_pct"] = round(upside, 1)
        else:
            # 米国株: アナリスト目標株価 乖離率
            tgt = data.get("target_mean")
            if curr and tgt and curr > 0:
                data["target_upside_pct"] = round((tgt / curr - 1) * 100, 1)

    except Exception as e:
        log.warning(f"[valuation] {ticker}: {e}")

    cache_db.set(key, data, _TTL)
    return data


def _f(v):
    """None/inf/nan → None、それ以外は float に丸め"""
    if v is None:
        return None
    try:
        f = float(v)
        if f != f or abs(f) > 1e15:
            return None
        return round(f, 4)
    except Exception:
        return None


def _pct(v):
    """小数→%変換（0.05 → 5.0）して返す"""
    r = _f(v)
    if r is None:
        return None
    return round(r * 100, 2)
