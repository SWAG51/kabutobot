"""
TDnet適時開示 - やのしん無料API
URL: https://webapi.yanoshin.jp/webapi/tdnet/list/{code4}.json?limit=20
個人運営APIのため: レート制限・キャッシュ・エラー無視を徹底
"""
import json
import logging
import time
from pathlib import Path

import requests

from config import DATA_DIR

log = logging.getLogger(__name__)

TDNET_DIR   = DATA_DIR / "tdnet"
TDNET_DIR.mkdir(exist_ok=True)
TTL_SECONDS = 14400   # 4時間キャッシュ
RATE_LIMIT  = 2.5     # リクエスト間隔(秒)
BASE_URL    = "https://webapi.yanoshin.jp/webapi/tdnet/list"
_last_req   = 0.0


def _cache_path(code4: str) -> Path:
    return TDNET_DIR / f"{code4}.json"


def _is_fresh(code4: str) -> bool:
    p = _cache_path(code4)
    return p.exists() and (time.time() - p.stat().st_mtime) < TTL_SECONDS


def get_tdnet(ticker: str, limit: int = 20) -> list:
    """yfinanceティッカーまたは4桁コードから適時開示リストを返す"""
    code4 = ticker.upper().replace(".T", "").strip()
    if not code4 or len(code4) > 6:
        return []

    if _is_fresh(code4):
        try:
            return json.loads(_cache_path(code4).read_text(encoding="utf-8"))
        except Exception:
            pass

    return _fetch(code4, limit)


def _fetch(code4: str, limit: int) -> list:
    global _last_req
    wait = RATE_LIMIT - (time.time() - _last_req)
    if wait > 0:
        time.sleep(wait)

    try:
        url = f"{BASE_URL}/{code4}.json?limit={limit}"
        r   = requests.get(url, timeout=10, headers={"User-Agent": "kabutobot/1.0 (personal)"})
        _last_req = time.time()

        if r.status_code == 404:
            _cache_path(code4).write_text("[]", encoding="utf-8")
            return []
        r.raise_for_status()
        raw = r.json()
    except Exception as e:
        log.debug(f"[TDnet] {code4}: {e}")
        return []

    # レスポンス形式を柔軟に処理
    if isinstance(raw, list):
        items_raw = raw
    elif isinstance(raw, dict):
        items_raw = raw.get("items", raw.get("list", raw.get("data", [])))
        if not isinstance(items_raw, list):
            items_raw = []
    else:
        items_raw = []

    items = []
    for d in items_raw:
        if not isinstance(d, dict):
            continue
        # やのしんAPI: {Tdnet: {...}} のラッパー構造に対応
        inner = d.get("Tdnet", d)
        if not isinstance(inner, dict):
            continue

        title  = inner.get("title", inner.get("headline", inner.get("subject", "")))
        date   = inner.get("pubdate", inner.get("date", inner.get("submit_date", "")))
        doc_id = inner.get("id", "")
        url_   = inner.get("url", inner.get("pdf_url", ""))
        if not url_ and doc_id:
            url_ = f"https://www.release.tdnet.info/inbs/I_main_00_{doc_id}.html"

        if title:
            items.append({"date": str(date)[:10], "title": str(title), "url": str(url_)})

    try:
        _cache_path(code4).write_text(
            json.dumps(items, ensure_ascii=False), encoding="utf-8"
        )
    except Exception:
        pass

    return items


def prefetch_watchlist(jp_stocks: list):
    """監視JP銘柄のTDnetを事前取得（バックグラウンド用）"""
    for s in jp_stocks:
        t = s.get("ticker", "")
        if t.endswith(".T"):
            code4 = t[:-2]
            if not _is_fresh(code4):
                _fetch(code4, 20)
