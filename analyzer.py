"""テクニカル分析: 移動平均クロス + RSI によるシグナル判定"""
import logging

import pandas as pd
import yfinance as yf

from config import LONG_MA, RSI_OVERBOUGHT, RSI_OVERSOLD, RSI_PERIOD, SHORT_MA

log = logging.getLogger(__name__)


def _fetch_ohlcv(ticker: str, period: str = "60d") -> pd.DataFrame | None:
    try:
        df = yf.download(ticker, period=period, interval="1d", progress=False, auto_adjust=True)
        if df is None or df.empty:
            log.warning(f"[analyzer] {ticker}: データ空")
            return None
        # MultiIndex対応（単一銘柄でも発生することがある）
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        if len(df) < LONG_MA + 3:
            log.warning(f"[analyzer] {ticker}: データ不足 {len(df)}件")
            return None
        return df
    except Exception as e:
        log.warning(f"[analyzer] {ticker}: 取得失敗 {e}")
        return None


def _calc_rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta    = series.diff()
    gain     = delta.clip(lower=0)
    loss     = (-delta).clip(lower=0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs  = avg_gain / avg_loss.replace(0, float("inf"))
    return 100 - (100 / (1 + rs))


def analyze(ticker: str, rsi_overbought: int | None = None, rsi_oversold: int | None = None) -> dict | None:
    """
    銘柄を分析してシグナルを返す。
    戻り値例:
      {"ticker": "AAPL", "signal": "BUY", "reason": "ゴールデンクロス", ...}
    """
    df = _fetch_ohlcv(ticker)
    if df is None:
        return None

    close = df["Close"].squeeze()
    if not isinstance(close, pd.Series):
        close = pd.Series(close)

    ma_s  = close.rolling(SHORT_MA).mean()
    ma_l  = close.rolling(LONG_MA).mean()
    rsi   = _calc_rsi(close)

    prev_s = float(ma_s.iloc[-2])
    prev_l = float(ma_l.iloc[-2])
    curr_s = float(ma_s.iloc[-1])
    curr_l = float(ma_l.iloc[-1])
    curr_r = float(rsi.iloc[-1])
    price  = float(close.iloc[-1])

    ob = rsi_overbought if rsi_overbought is not None else RSI_OVERBOUGHT
    os = rsi_oversold   if rsi_oversold   is not None else RSI_OVERSOLD

    is_golden = (prev_s <= prev_l) and (curr_s > curr_l)
    is_dead   = (prev_s >= prev_l) and (curr_s < curr_l)

    signal = "HOLD"
    reason = "シグナルなし"
    cross  = None

    if is_golden:
        cross = "golden"
        if curr_r < ob:
            signal, reason = "BUY", f"ゴールデンクロス (RSI={curr_r:.1f})"
        else:
            reason = f"ゴールデンクロスだが買われすぎ (RSI={curr_r:.1f}>{ob})"
    elif is_dead:
        cross = "dead"
        if curr_r > os:
            signal, reason = "SELL", f"デッドクロス (RSI={curr_r:.1f})"
        else:
            reason = f"デッドクロスだが売られすぎ (RSI={curr_r:.1f}<{os})"
    elif curr_s > curr_l:
        reason = "短期MA > 長期MA (上昇トレンド中)"
    else:
        reason = "短期MA < 長期MA (下降トレンド中)"

    currency = "JPY" if ticker.endswith(".T") else "USD"

    return {
        "ticker":    ticker,
        "price":     round(price, 4),
        "currency":  currency,
        "ma_short":  round(curr_s, 4),
        "ma_long":   round(curr_l, 4),
        "rsi":       round(curr_r, 2),
        "signal":    signal,
        "reason":    reason,
        "cross":     cross,
        "timestamp": pd.Timestamp.now().isoformat(),
    }


def get_chart_data(ticker: str, period: str = "60d") -> dict | None:
    """チャートモーダル用: 価格 + MA + RSI + MACD + ボリンジャーバンド + 出来高"""
    df = _fetch_ohlcv(ticker, period=period)
    if df is None:
        return None

    close = df["Close"].squeeze()
    if not isinstance(close, pd.Series):
        close = pd.Series(close)

    ma5  = close.rolling(SHORT_MA).mean()
    ma25 = close.rolling(LONG_MA).mean()
    rsi  = _calc_rsi(close)

    # MACD (12, 26, 9)
    ema12     = close.ewm(span=12, adjust=False).mean()
    ema26     = close.ewm(span=26, adjust=False).mean()
    macd      = ema12 - ema26
    macd_sig  = macd.ewm(span=9, adjust=False).mean()
    macd_hist = macd - macd_sig

    # Bollinger Bands (20, 2σ)
    bb_mid   = close.rolling(20).mean()
    bb_std   = close.rolling(20).std()
    bb_upper = bb_mid + 2 * bb_std
    bb_lower = bb_mid - 2 * bb_std

    def _fmt(s):
        return [round(float(x), 4) if pd.notna(x) else None for x in s]

    volume = []
    if "Volume" in df.columns:
        vol = df["Volume"].squeeze()
        volume = [int(x) if pd.notna(x) else 0 for x in vol]

    dates = [str(d.date()) for d in df.index]
    return {
        "ticker":      ticker,
        "dates":       dates,
        "close":       _fmt(close),
        "ma5":         _fmt(ma5),
        "ma25":        _fmt(ma25),
        "rsi":         _fmt(rsi),
        "volume":      volume,
        "macd":        _fmt(macd),
        "macd_signal": _fmt(macd_sig),
        "macd_hist":   _fmt(macd_hist),
        "bb_upper":    _fmt(bb_upper),
        "bb_mid":      _fmt(bb_mid),
        "bb_lower":    _fmt(bb_lower),
    }


def get_current_price(ticker: str) -> float | None:
    """ポジション監視用: 最新価格のみ取得"""
    try:
        hist = yf.Ticker(ticker).history(period="1d", interval="5m")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        hist = yf.Ticker(ticker).history(period="2d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
        return None
    except Exception as e:
        log.warning(f"[analyzer] {ticker}: 現在値取得失敗 {e}")
        return None
