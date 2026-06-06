"""シンプル RSI + MAクロス バックテストエンジン"""
import yfinance as yf
import pandas as pd


def run_backtest(ticker: str, period: str = "1y") -> dict:
    try:
        df = yf.Ticker(ticker).history(period=period)
        if df.empty or len(df) < 30:
            return {"error": "データ不足"}

        close = df["Close"].squeeze()
        if not isinstance(close, pd.Series):
            close = pd.Series(close)

        ma5  = close.rolling(5).mean()
        ma25 = close.rolling(25).mean()

        delta = close.diff()
        gain  = delta.clip(lower=0).ewm(com=13, min_periods=14).mean()
        loss  = (-delta.clip(upper=0)).ewm(com=13, min_periods=14).mean()
        rsi   = 100 - (100 / (1 + gain / loss.replace(0, float("inf"))))

        trades = []
        pos = None
        for i in range(30, len(df)):
            p   = float(close.iloc[i])
            r   = float(rsi.iloc[i])
            m5  = float(ma5.iloc[i])
            m25 = float(ma25.iloc[i])
            if pd.isna(r) or pd.isna(m5) or pd.isna(m25):
                continue
            if pos is None:
                if r < 30 and m5 > m25:
                    pos = {"bp": p, "bd": str(df.index[i])[:10]}
            else:
                if r > 70 or m5 < m25:
                    pnl = (p - pos["bp"]) / pos["bp"] * 100
                    trades.append({
                        "buy_date":   pos["bd"],
                        "sell_date":  str(df.index[i])[:10],
                        "buy_price":  round(pos["bp"], 4),
                        "sell_price": round(p, 4),
                        "pnl_pct":    round(pnl, 2),
                    })
                    pos = None

        if not trades:
            return {
                "ticker": ticker, "trades": [], "win_rate": 0,
                "total_return": 0, "trade_count": 0, "avg_return": 0,
                "period": period,
            }

        wins  = sum(1 for t in trades if t["pnl_pct"] > 0)
        total = sum(t["pnl_pct"] for t in trades)
        return {
            "ticker":       ticker,
            "trades":       trades[-20:],
            "win_rate":     round(wins / len(trades) * 100, 1),
            "total_return": round(total, 2),
            "trade_count":  len(trades),
            "avg_return":   round(total / len(trades), 2),
            "period":       period,
        }
    except Exception as e:
        return {"error": str(e)}
