"""
銘柄マスタDB管理
- JP株: JPX data_j.xls (日次キャッシュ)
- US株: SEC EDGAR company_tickers.json (週次キャッシュ)
"""
import json
import logging
import sqlite3
import time
from datetime import datetime
from pathlib import Path

import requests

from config import DATA_DIR

log = logging.getLogger(__name__)

MASTER_DB = DATA_DIR / "stock_master.db"
JPX_URL   = "https://www.jpx.co.jp/markets/statistics-equities/misc/tvdivq0000001vg2-att/data_j.xls"
SEC_URL   = "https://www.sec.gov/files/company_tickers.json"
JPX_CACHE = DATA_DIR / "data_j.xls"
SEC_CACHE = DATA_DIR / "sec_tickers.json"
_HEADERS  = {"User-Agent": "kabutobot/1.0 (personal use)"}


def _init_db():
    con = sqlite3.connect(MASTER_DB, check_same_thread=False)
    con.execute("""
        CREATE TABLE IF NOT EXISTS jp_stocks (
            code TEXT PRIMARY KEY,
            name TEXT,
            market TEXT,
            sector33 TEXT,
            yf_ticker TEXT,
            updated TEXT
        )""")
    con.execute("""
        CREATE TABLE IF NOT EXISTS us_stocks (
            ticker TEXT PRIMARY KEY,
            name TEXT,
            updated TEXT
        )""")
    con.execute("CREATE INDEX IF NOT EXISTS jp_name_idx ON jp_stocks(name)")
    con.execute("CREATE INDEX IF NOT EXISTS jp_sec_idx  ON jp_stocks(sector33)")
    con.execute("CREATE INDEX IF NOT EXISTS us_name_idx ON us_stocks(name)")
    con.commit()
    return con


def _needs_update(path: Path, days: int = 1) -> bool:
    if not path.exists():
        return True
    return time.time() - path.stat().st_mtime > days * 86400


def update_jp_master(force: bool = False) -> int:
    if not force and not _needs_update(JPX_CACHE, days=1):
        return 0
    try:
        log.info("[Master] JPX data_j.xls DL中...")
        r = requests.get(JPX_URL, headers=_HEADERS, timeout=30)
        r.raise_for_status()
        JPX_CACHE.write_bytes(r.content)
    except Exception as e:
        log.warning(f"[Master] JPX DL失敗: {e}")
        if not JPX_CACHE.exists():
            return 0

    try:
        import xlrd
        wb = xlrd.open_workbook(str(JPX_CACHE))
        ws = wb.sheet_by_index(0)
    except Exception as e:
        log.warning(f"[Master] XLS解析失敗: {e}")
        return 0

    con = _init_db()
    now = datetime.now().isoformat()
    count = 0
    for i in range(1, ws.nrows):
        row = ws.row_values(i)
        if len(row) < 3:
            continue
        # 列: [0]日付 [1]コード [2]銘柄名 [3]市場区分 [4]33業種コード [5]33業種区分
        raw_code = row[1]
        if isinstance(raw_code, float):
            raw_code = int(raw_code)
        code = str(raw_code).strip()
        # 4桁数字 or 英字混じりコード(130A等)
        if not code or len(code) > 5:
            continue
        if code.isdigit():
            code = code.zfill(4)
        name     = str(row[2]).strip()
        market   = str(row[3]).strip() if len(row) > 3 else ""
        sector33 = str(row[5]).strip() if len(row) > 5 else ""
        if sector33 in ("-", ""):
            sector33 = ""
        yf_ticker = code + ".T"
        con.execute(
            "INSERT OR REPLACE INTO jp_stocks VALUES(?,?,?,?,?,?)",
            (code, name, market, sector33, yf_ticker, now)
        )
        count += 1
    con.commit()
    con.close()
    log.info(f"[Master] JP更新: {count}件")
    return count


def update_us_master(force: bool = False) -> int:
    if not force and not _needs_update(SEC_CACHE, days=7):
        return 0
    try:
        log.info("[Master] SEC EDGAR tickers.json DL中...")
        r = requests.get(SEC_URL, headers=_HEADERS, timeout=30)
        r.raise_for_status()
        SEC_CACHE.write_bytes(r.content)
    except Exception as e:
        log.warning(f"[Master] SEC DL失敗: {e}")
        if not SEC_CACHE.exists():
            return 0

    try:
        raw = SEC_CACHE.read_bytes()
        data = json.loads(raw.decode("utf-8", errors="replace"))
    except Exception as e:
        log.warning(f"[Master] SEC JSON解析失敗: {e}")
        return 0

    con = _init_db()
    now = datetime.now().isoformat()
    count = 0
    for entry in data.values():
        ticker = str(entry.get("ticker", "")).strip().upper()
        title  = str(entry.get("title",  "")).strip()
        if not ticker or len(ticker) > 6:
            continue
        con.execute(
            "INSERT OR REPLACE INTO us_stocks VALUES(?,?,?)",
            (ticker, title, now)
        )
        count += 1
    con.commit()
    con.close()
    log.info(f"[Master] US更新: {count}件")
    return count


def search_jp(query: str, limit: int = 25) -> list:
    if not MASTER_DB.exists():
        return []
    q = query.strip()
    if not q:
        return []
    try:
        con = sqlite3.connect(MASTER_DB, check_same_thread=False)
        con.row_factory = sqlite3.Row

        # コード完全一致を優先
        exact = list(con.execute(
            "SELECT code,name,market,sector33,yf_ticker FROM jp_stocks "
            "WHERE code=? OR yf_ticker=? LIMIT 5",
            (q.zfill(4) if q.isdigit() else q.upper(), q.upper())
        ).fetchall())

        like = f"%{q}%"
        extra = con.execute(
            "SELECT code,name,market,sector33,yf_ticker FROM jp_stocks "
            "WHERE name LIKE ? OR sector33 LIKE ? ORDER BY name LIMIT ?",
            (like, like, limit)
        ).fetchall()

        seen = {r["code"] for r in exact}
        rows = exact + [r for r in extra if r["code"] not in seen]
        con.close()

        return [{"code": r["code"], "name": r["name"], "market": r["market"],
                 "sector33": r["sector33"], "ticker": r["yf_ticker"]} for r in rows[:limit]]
    except Exception as e:
        log.debug(f"[Master] search_jp: {e}")
        return []


def search_us(query: str, limit: int = 15) -> list:
    if not MASTER_DB.exists():
        return []
    q = query.strip()
    if not q:
        return []
    try:
        con = sqlite3.connect(MASTER_DB, check_same_thread=False)
        con.row_factory = sqlite3.Row

        exact = list(con.execute(
            "SELECT ticker,name FROM us_stocks WHERE ticker=? LIMIT 5",
            (q.upper(),)
        ).fetchall())

        like = f"%{q}%"
        extra = con.execute(
            "SELECT ticker,name FROM us_stocks "
            "WHERE ticker LIKE ? OR name LIKE ? ORDER BY ticker LIMIT ?",
            (f"{q.upper()}%", like, limit)
        ).fetchall()

        seen = {r["ticker"] for r in exact}
        rows = exact + [r for r in extra if r["ticker"] not in seen]
        con.close()

        return [{"ticker": r["ticker"], "name": r["name"]} for r in rows[:limit]]
    except Exception as e:
        log.debug(f"[Master] search_us: {e}")
        return []


def get_count() -> dict:
    if not MASTER_DB.exists():
        return {"jp": 0, "us": 0}
    try:
        con = sqlite3.connect(MASTER_DB, check_same_thread=False)
        jp = con.execute("SELECT COUNT(*) FROM jp_stocks").fetchone()[0]
        us = con.execute("SELECT COUNT(*) FROM us_stocks").fetchone()[0]
        con.close()
        return {"jp": jp, "us": us}
    except Exception:
        return {"jp": 0, "us": 0}


def ensure_master_fresh():
    """起動時・日次: 古ければバックグラウンド更新"""
    import threading
    _init_db()

    def _bg():
        update_jp_master()
        update_us_master()

    threading.Thread(target=_bg, daemon=True, name="master-update").start()
