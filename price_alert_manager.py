"""価格アラートマネージャー"""
import json
from pathlib import Path

_FILE = Path(__file__).parent / "data" / "price_alerts.json"


class PriceAlertManager:
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

    def add(self, ticker: str, name: str, target_price: float,
            direction: str, currency: str = "JPY"):
        self._d.append({
            "ticker":       ticker.upper(),
            "name":         name,
            "target_price": float(target_price),
            "direction":    direction,   # "above" | "below"
            "currency":     currency,
            "triggered":    False,
        })
        self._save()

    def remove(self, idx: int):
        if 0 <= idx < len(self._d):
            self._d.pop(idx)
            self._save()

    def reset(self, idx: int):
        if 0 <= idx < len(self._d):
            self._d[idx]["triggered"] = False
            self._save()

    def check(self, ticker: str, current_price: float) -> list:
        """発動したアラートを返す（同時にtriggered=Trueにする）"""
        hit = []
        for i, a in enumerate(self._d):
            if a["ticker"] != ticker.upper() or a.get("triggered"):
                continue
            if (a["direction"] == "above" and current_price >= a["target_price"]) or \
               (a["direction"] == "below" and current_price <= a["target_price"]):
                self._d[i]["triggered"] = True
                hit.append((i, a))
        if hit:
            self._save()
        return hit

    def _save(self):
        _FILE.parent.mkdir(exist_ok=True)
        _FILE.write_text(json.dumps(self._d, ensure_ascii=False, indent=2), "utf-8")
