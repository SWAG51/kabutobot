"""設定マネージャー"""
import json
from pathlib import Path

_FILE = Path(__file__).parent / "data" / "settings.json"
_DEFAULTS = {
    "discord_webhook": "",
    "discord_enabled": True,
    "rsi_overbought": 70,
    "rsi_oversold": 30,
    "pts_alert_pct": 3.0,
}


class SettingsManager:
    def __init__(self):
        self._d = dict(_DEFAULTS)
        self.load()

    def load(self):
        if _FILE.exists():
            try:
                self._d = {**_DEFAULTS, **json.loads(_FILE.read_text("utf-8"))}
            except Exception:
                pass

    def all(self):
        return dict(self._d)

    def get(self, key, default=None):
        return self._d.get(key, default)

    def update(self, data: dict):
        for k in _DEFAULTS:
            if k in data:
                self._d[k] = data[k]
        _FILE.parent.mkdir(exist_ok=True)
        _FILE.write_text(json.dumps(self._d, ensure_ascii=False, indent=2), "utf-8")
