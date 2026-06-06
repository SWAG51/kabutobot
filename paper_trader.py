"""ペーパートレード管理: 仮想口座での売買シミュレーション"""
import json
import logging
from datetime import datetime
from pathlib import Path

from config import (
    BALANCE_FILE,
    INITIAL_BALANCE_JPY,
    INITIAL_BALANCE_USD,
    MAX_POSITION_PCT,
    MAX_POSITIONS,
    POSITIONS_FILE,
    STOP_LOSS_PCT,
    TAKE_PROFIT_PCT,
    TRADES_FILE,
)

log = logging.getLogger(__name__)


class PaperTrader:
    def __init__(self):
        self.positions: dict = {}
        self.trades:    list = []
        self.balance_usd = INITIAL_BALANCE_USD
        self.balance_jpy = INITIAL_BALANCE_JPY
        self.load()

    # ── 残高 ──

    def get_balance(self, currency: str) -> float:
        return self.balance_usd if currency == "USD" else self.balance_jpy

    def _adjust_balance(self, currency: str, amount: float):
        if currency == "USD":
            self.balance_usd += amount
        else:
            self.balance_jpy += amount

    def get_total_equity(self, currency: str) -> float:
        total = self.get_balance(currency)
        for pos in self.positions.values():
            if pos["currency"] == currency:
                total += pos.get("current_value", pos["amount"])
        return total

    def _max_invest(self, currency: str) -> float:
        return self.get_total_equity(currency) * MAX_POSITION_PCT

    # ── 買い ──

    def buy(self, ticker: str, price: float, currency: str,
            name: str = "", signal_data: dict | None = None) -> dict | None:
        if len(self.positions) >= MAX_POSITIONS:
            log.info(f"[Trade] {ticker}: 最大保有数({MAX_POSITIONS})到達 → スキップ")
            return None
        if ticker in self.positions:
            log.info(f"[Trade] {ticker}: 既に保有中")
            return None

        invest = min(self._max_invest(currency), self.get_balance(currency))
        if invest < 1:
            log.warning(f"[Trade] {ticker}: 残高不足 ({invest:.2f} {currency})")
            return None

        quantity = invest / price
        position = {
            "ticker":        ticker,
            "name":          name,
            "currency":      currency,
            "entry_price":   price,
            "quantity":      quantity,
            "amount":        invest,
            "current_price": price,
            "current_value": invest,
            "pnl":           0.0,
            "pnl_pct":       0.0,
            "stop_loss":     price * (1 - STOP_LOSS_PCT),
            "take_profit":   price * (1 + TAKE_PROFIT_PCT),
            "tp_taken":      False,
            "entry_time":    datetime.now().isoformat(),
        }
        self.positions[ticker] = position
        self._adjust_balance(currency, -invest)

        self.trades.append({
            "ticker":    ticker,
            "name":      name,
            "currency":  currency,
            "action":    "BUY",
            "price":     price,
            "quantity":  round(quantity, 6),
            "amount":    round(invest, 2),
            "timestamp": datetime.now().isoformat(),
            "reason":    (signal_data or {}).get("reason", "買いシグナル"),
            "pnl":       0.0,
            "pnl_pct":   0.0,
        })
        self.save()
        log.info(f"[Trade] 買い: {ticker} @ {price:.4f} × {quantity:.4f} = {invest:.2f} {currency}")
        return position

    # ── 売り ──

    def sell(self, ticker: str, price: float, reason: str,
             partial: float = 1.0) -> dict | None:
        if ticker not in self.positions:
            return None

        pos      = self.positions[ticker]
        currency = pos["currency"]
        sell_qty = pos["quantity"] * partial
        proceeds = sell_qty * price
        cost     = pos["amount"] * partial
        pnl      = proceeds - cost
        pnl_pct  = (price / pos["entry_price"] - 1) * 100

        try:
            hold_days = (datetime.now() - datetime.fromisoformat(pos["entry_time"])).days
        except Exception:
            hold_days = 0

        self._adjust_balance(currency, proceeds)

        trade = {
            "ticker":      ticker,
            "name":        pos["name"],
            "currency":    currency,
            "action":      "SELL",
            "price":       price,
            "entry_price": pos["entry_price"],
            "quantity":    round(sell_qty, 6),
            "amount":      round(proceeds, 2),
            "timestamp":   datetime.now().isoformat(),
            "reason":      reason,
            "pnl":         round(pnl, 2),
            "pnl_pct":     round(pnl_pct, 2),
            "hold_days":   hold_days,
        }
        self.trades.append(trade)

        if partial >= 1.0:
            del self.positions[ticker]
            log.info(f"[Trade] 売り: {ticker} @ {price:.4f} PnL={pnl:+.2f} ({pnl_pct:+.1f}%) [{reason}]")
        else:
            pos["quantity"]  -= sell_qty
            pos["amount"]    -= cost
            pos["tp_taken"]   = True
            log.info(f"[Trade] 一部売り({partial*100:.0f}%): {ticker} @ {price:.4f} PnL={pnl:+.2f} ({pnl_pct:+.1f}%) [{reason}]")

        self.save()
        return trade

    # ── 損切り・利確チェック ──

    def update_positions(self, prices: dict) -> list:
        triggered = []
        for ticker, pos in list(self.positions.items()):
            price = prices.get(ticker)
            if price is None:
                continue

            pnl_pct = (price / pos["entry_price"] - 1) * 100
            pos["current_price"] = price
            pos["current_value"] = pos["quantity"] * price
            pos["pnl"]           = pos["current_value"] - pos["amount"]
            pos["pnl_pct"]       = round(pnl_pct, 2)

            if price <= pos["stop_loss"]:
                trade = self.sell(ticker, price, "損切り")
                if trade:
                    triggered.append({**trade, "type": "stop_loss"})
            elif price >= pos["take_profit"] and not pos.get("tp_taken"):
                trade = self.sell(ticker, price, "利確(50%)", partial=0.5)
                if trade:
                    triggered.append({**trade, "type": "take_profit"})

        self.save()
        return triggered

    # ── 統計 ──

    def get_stats(self) -> dict:
        sells    = [t for t in self.trades if t["action"] == "SELL"]
        wins     = [t for t in sells if t["pnl"] > 0]
        losses   = [t for t in sells if t["pnl"] <= 0]
        win_rate = len(wins) / len(sells) * 100 if sells else 0.0
        pnl_usd  = sum(t["pnl"] for t in sells if t["currency"] == "USD")
        pnl_jpy  = sum(t["pnl"] for t in sells if t["currency"] == "JPY")
        eq_usd   = self.get_total_equity("USD")
        eq_jpy   = self.get_total_equity("JPY")
        return {
            "total_trades":    len(sells),
            "win_trades":      len(wins),
            "lose_trades":     len(losses),
            "win_rate":        round(win_rate, 1),
            "total_pnl_usd":   round(pnl_usd, 2),
            "total_pnl_jpy":   round(pnl_jpy, 0),
            "balance_usd":     round(self.balance_usd, 2),
            "balance_jpy":     round(self.balance_jpy, 0),
            "equity_usd":      round(eq_usd, 2),
            "equity_jpy":      round(eq_jpy, 0),
            "return_usd_pct":  round((eq_usd / INITIAL_BALANCE_USD - 1) * 100, 2),
            "return_jpy_pct":  round((eq_jpy / INITIAL_BALANCE_JPY - 1) * 100, 2),
            "open_positions":  len(self.positions),
            "max_positions":   MAX_POSITIONS,
        }

    # ── 保存・読み込み ──

    def save(self):
        try:
            POSITIONS_FILE.write_text(
                json.dumps(self.positions, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            log.warning(f"[Trade] ポジション保存失敗: {e}")

        try:
            TRADES_FILE.write_text(
                json.dumps(self.trades[-500:], ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            log.warning(f"[Trade] 取引履歴保存失敗: {e}")

        try:
            history = []
            if BALANCE_FILE.exists():
                try:
                    history = json.loads(BALANCE_FILE.read_text(encoding="utf-8"))
                except Exception:
                    pass
            history.append({
                "timestamp": datetime.now().isoformat(),
                "usd":       round(self.balance_usd, 2),
                "jpy":       round(self.balance_jpy, 0),
                "equity_usd": round(self.get_total_equity("USD"), 2),
                "equity_jpy": round(self.get_total_equity("JPY"), 0),
            })
            BALANCE_FILE.write_text(
                json.dumps(history[-1000:], ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except Exception as e:
            log.warning(f"[Trade] 残高履歴保存失敗: {e}")

    def load(self):
        if POSITIONS_FILE.exists():
            try:
                self.positions = json.loads(POSITIONS_FILE.read_text(encoding="utf-8"))
                log.info(f"[Trade] ポジション復元: {len(self.positions)}件")
            except Exception as e:
                log.warning(f"[Trade] ポジション読み込み失敗: {e}")
        if TRADES_FILE.exists():
            try:
                self.trades = json.loads(TRADES_FILE.read_text(encoding="utf-8"))
                log.info(f"[Trade] 取引履歴復元: {len(self.trades)}件")
            except Exception as e:
                log.warning(f"[Trade] 取引履歴読み込み失敗: {e}")
