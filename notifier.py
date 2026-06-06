"""Discord通知"""
import logging
from datetime import datetime

import requests

from config import DISCORD_WEBHOOK_URL

log = logging.getLogger(__name__)


def _send(payload: dict):
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
        r.raise_for_status()
    except Exception as e:
        log.warning(f"[Discord] 送信失敗: {e}")


def _embed(title: str, description: str, color: int) -> dict:
    return {"embeds": [{"title": title, "description": description, "color": color}]}


def _fmt(val: float, currency: str) -> str:
    if currency == "JPY":
        return f"¥{val:,.0f}"
    return f"${val:,.4f}"


def notify_buy_signal(result: dict):
    cur = result["currency"]
    desc = (
        f"📈 ゴールデンクロス発生\n"
        f"現在値:  {_fmt(result['price'], cur)}\n"
        f"5日MA:   {_fmt(result['ma_short'], cur)}\n"
        f"25日MA:  {_fmt(result['ma_long'], cur)}\n"
        f"RSI:     {result['rsi']:.1f}\n"
        f"理由:    {result['reason']}"
    )
    _send(_embed(f"🟢 買いシグナル [{result['ticker']}]", desc, 0x2ECC71))


def notify_sell_signal(result: dict):
    cur = result["currency"]
    desc = (
        f"📉 デッドクロス発生\n"
        f"現在値:  {_fmt(result['price'], cur)}\n"
        f"RSI:     {result['rsi']:.1f}\n"
        f"理由:    {result['reason']}"
    )
    _send(_embed(f"🔴 売りシグナル [{result['ticker']}]", desc, 0xE74C3C))


def notify_stop_loss(trade: dict):
    cur   = trade["currency"]
    sym   = "¥" if cur == "JPY" else "$"
    entry = trade.get("entry_price", 0)
    desc  = (
        f"購入値:   {_fmt(entry, cur)}\n"
        f"現在値:   {_fmt(trade['price'], cur)}\n"
        f"損益:     {sym}{trade['pnl']:+,.2f} ({trade['pnl_pct']:+.1f}%)\n"
        f"保有期間: {trade.get('hold_days', 0)}日"
    )
    _send(_embed(f"🔴 損切り発動 [{trade['ticker']}]", desc, 0xE74C3C))


def notify_take_profit(trade: dict):
    cur  = trade["currency"]
    sym  = "¥" if cur == "JPY" else "$"
    desc = (
        f"現在値:    {_fmt(trade['price'], cur)}\n"
        f"確定損益:  {sym}{trade['pnl']:+,.2f} ({trade['pnl_pct']:+.1f}%)\n"
        f"残り50%継続保有"
    )
    _send(_embed(f"🟡 利確(50%) [{trade['ticker']}]", desc, 0xF39C12))


def notify_morning_report(stats: dict, positions: dict):
    today    = datetime.now().strftime("%Y/%m/%d")
    pos_lines = []
    for ticker, pos in positions.items():
        icon = "✅" if pos["pnl_pct"] >= 0 else "❌"
        cur  = pos["currency"]
        val  = pos.get("current_value", pos["amount"])
        val_str = f"¥{val/10000:.1f}万" if cur == "JPY" else f"${val:,.0f}"
        pos_lines.append(f"  {icon} {ticker}  {pos['pnl_pct']:+.1f}%  {val_str}")

    pos_block = "\n".join(pos_lines) if pos_lines else "  （保有なし）"
    desc = (
        f"💰 仮想口座残高\n"
        f"  USD: ${stats['equity_usd']:,.0f} ({stats['return_usd_pct']:+.2f}%)\n"
        f"  JPY: {stats['equity_jpy']/10000:.1f}万円 ({stats['return_jpy_pct']:+.2f}%)\n\n"
        f"📈 保有中ポジション ({len(positions)}件)\n"
        f"{pos_block}\n\n"
        f"📊 通算成績\n"
        f"  取引回数: {stats['total_trades']}回\n"
        f"  勝率: {stats['win_rate']}%\n"
        f"  通算PnL: ${stats['total_pnl_usd']:+,.0f} / {stats['total_pnl_jpy']:+,.0f}円"
    )
    _send(_embed(f"📊 朝の損益レポート {today}", desc, 0x3498DB))


def notify_weekly_report(stats: dict):
    today = datetime.now().strftime("%Y/%m/%d")
    desc  = (
        f"週次成績サマリー\n"
        f"USD口座: ${stats['equity_usd']:,.0f} ({stats['return_usd_pct']:+.2f}%)\n"
        f"JPY口座: {stats['equity_jpy']/10000:.1f}万円 ({stats['return_jpy_pct']:+.2f}%)\n\n"
        f"取引回数: {stats['total_trades']}回\n"
        f"勝率: {stats['win_rate']}%\n"
        f"通算PnL: ${stats['total_pnl_usd']:+,.0f} / {stats['total_pnl_jpy']:+,.0f}円"
    )
    _send(_embed(f"📅 週次レポート {today}", desc, 0x9B59B6))
