# -*- coding: utf-8 -*-
"""
Live market parameter fetcher.
Caches results to avoid redundant network calls within the same run.

Sources:
  ERP  — Damodaran's monthly implied ERP spreadsheet (ERPbymonth.xlsx)
  BIST rf — FRED series INTDSRTRM193N (TCMB policy rate, monthly)
  US rf   — yfinance ^TNX (already handled in valuation.py)
"""
from __future__ import annotations

import io
import time
import urllib.request
from typing import Optional

_cache: dict[str, dict] = {}
_ERP_TTL  = 7 * 24 * 3600   # 7 days — Damodaran updates monthly
_RF_TTL   = 24 * 3600        # 24 hours — TCMB meets monthly

_HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; finance-analysis-tool)"}
_TIMEOUT  = 10

_DAMODARAN_URL = (
    "https://pages.stern.nyu.edu/~adamodar/pc/implprem/ERPbymonth.xlsx"
)
_FRED_BIST_URL = (
    "https://fred.stlouisfed.org/graph/fredgraph.csv?id=INTDSRTRM193N"
)


def _get(key: str) -> Optional[float]:
    entry = _cache.get(key)
    if entry and time.time() - entry["ts"] < entry["ttl"]:
        return entry["val"]
    return None


def _put(key: str, val: float, ttl: float) -> float:
    _cache[key] = {"val": val, "ts": time.time(), "ttl": ttl}
    return val


def _fetch_bytes(url: str) -> bytes:
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=_TIMEOUT) as r:
        return r.read()


def _erp_col_index(header: tuple) -> int:
    try:
        return next(
            i for i, h in enumerate(header)
            if h and "ERP (T12m)" in str(h)
            and "adj" not in str(h).lower()
            and "smooth" not in str(h).lower()
        )
    except StopIteration:
        return 9  # known fallback position


def _parse_erp_from_rows(rows: list, col_idx: int) -> Optional[float]:
    for row in reversed(rows[1:]):
        val = row[col_idx] if col_idx < len(row) else None
        if val is None:
            continue
        try:
            v = float(str(val).replace("%", "").replace(",", "."))
            if v > 0.5:
                v /= 100
            if 0.01 <= v <= 0.15:
                return v
        except (ValueError, TypeError):
            continue
    return None


def fetch_us_erp(fallback: float) -> float:
    """Damodaran implied ERP (T12m) — last available month."""
    cached = _get("us_erp")
    if cached is not None:
        return cached

    try:
        import openpyxl  # already installed (required for xlsxwriter path)

        data = _fetch_bytes(_DAMODARAN_URL)
        wb = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
        rows = list(wb.active.iter_rows(values_only=True))
        col_idx = _erp_col_index(rows[0])
        erp = _parse_erp_from_rows(rows, col_idx)

        if erp is not None:
            print(f"[live_params] US ERP from Damodaran: {erp*100:.2f}%")
            return _put("us_erp", erp, _ERP_TTL)

    except Exception as exc:
        print(f"[live_params] ERP fetch failed: {exc}")

    print(f"[live_params] US ERP fallback: {fallback*100:.2f}%")
    return _put("us_erp", fallback, _ERP_TTL)


def fetch_bist_rf(fallback: float) -> float:
    """
    TCMB policy rate from FRED series INTDSRTRM193N (monthly, % form).
    Falls back to macro_config value on any error.
    """
    cached = _get("bist_rf")
    if cached is not None:
        return cached

    try:
        raw = _fetch_bytes(_FRED_BIST_URL).decode("utf-8", errors="ignore")
        lines = [
            l.strip() for l in raw.splitlines()
            if l.strip() and "DATE" not in l and "." in l and "NA" not in l
        ]
        if lines:
            last_val = float(lines[-1].split(",")[1])  # e.g. "2026-06-01,38.75"
            rf = last_val / 100.0
            if 0.05 <= rf <= 1.0:  # sanity: 5-100%
                print(f"[live_params] BIST rf from FRED: {rf*100:.2f}%")
                return _put("bist_rf", rf, _RF_TTL)
    except Exception as exc:
        print(f"[live_params] BIST rf fetch failed: {exc}")

    print(f"[live_params] BIST rf fallback: {fallback*100:.2f}%")
    return _put("bist_rf", fallback, _RF_TTL)
