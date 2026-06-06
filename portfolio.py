"""ポートフォリオマネージャー"""
import json
from datetime import datetime
from pathlib import Path

_FILE = Path(__file__).parent / "data" / "portfolio.json"


class PortfolioManager:
    def __init__(self):
        self._d: list = []
        self.load()

    def load(self):
        if _FILE.exists():
            try:
                self._d = json.loads(_FILE.read_text("utf-8"))
            except Exception:
                self._d = []

    def all(self):
        return list(self._d)

    def add(self, ticker: str, name: str, qty: float, buy_price: float, currency: str = "JPY"):
        self._d.append({
            "ticker":    ticker.upper(),
            "name":      name,
            "qty":       float(qty),
            "buy_price": float(buy_price),
            "currency":  currency,
            "date":      datetime.now().isoformat()[:10],
        })
        self._save()

    def remove(self, idx: int):
        if 0 <= idx < len(self._d):
            self._d.pop(idx)
            self._save()

    def _save(self):
        _FILE.parent.mkdir(exist_ok=True)
        _FILE.write_text(json.dumps(self._d, ensure_ascii=False, indent=2), "utf-8")
