# -*- coding: utf-8 -*-
"""
Live sector peer multiples fetched from yfinance at run-time.
Replaces static pe/ev_ebitda values from macro_config for US stocks.
"""
from __future__ import annotations

import time
from typing import Dict, Optional

import yfinance as yf

from data.sector import robust_median

# 5-6 liquid, well-covered representatives per sector — fetched once per run
# NOTE: A ticker should NOT appear in its own sector peer list (circular valuation bias).
SECTOR_PEERS_US: Dict[str, list[str]] = {
    "Teknoloji":         ["MSFT", "AAPL", "GOOGL", "ORCL", "INTU", "NOW"],
    "Yarı İletken":      ["NVDA", "AVGO", "TXN", "KLAC", "AMAT", "LRCX"],
    "E-Ticaret":         ["AMZN", "BKNG", "EBAY", "EXPE"],
    "İletişim & Medya":  ["NFLX", "DIS", "CMCSA", "GOOGL", "SPOT"],
    "Sağlık & İlaç":     ["LLY", "JNJ", "MRK", "UNH", "ABBV", "TMO"],
    "Finans":            ["JPM", "GS", "MS", "V", "MA", "SPGI"],
    "Enerji":            ["XOM", "CVX", "COP", "NEE", "EOG"],
    "Perakende & Tüketim": ["WMT", "COST", "HD", "PG", "KO", "MCD"],
    "Sanayi & Savunma":  ["HON", "CAT", "RTX", "UNP", "ETN", "LMT"],
    "Otomotiv":          ["TSLA", "F", "GM"],
    "Diğer ABD":         ["SPY", "QQQ"],  # broad market proxies as fallback
}

# Ticker-level peer overrides — skill metodolojisi ile aynı peer seçimi
TICKER_PEERS_US: Dict[str, list[str]] = {
    "META":  ["GOOGL", "AMZN", "NFLX"],
    "GOOGL": ["META", "AMZN", "NFLX"],
    "AMZN":  ["GOOGL", "META", "MSFT", "BKNG"],
    "NFLX":  ["DIS", "CMCSA", "SPOT", "GOOGL"],
}

# Sanity bounds — outliers (negative P/E, bubble valuations) filtered out
PE_MIN, PE_MAX = 5.0, 100.0
EV_EBITDA_MIN, EV_EBITDA_MAX = 3.0, 60.0
EV_REV_MIN, EV_REV_MAX = 0.3, 50.0

# Sector-level PE floors — live peer medians can't fall below these
SECTOR_PE_FLOORS: Dict[str, float] = {
    "Teknoloji": 20.0,
    "Yarı İletken": 20.0,
    "E-Ticaret": 18.0,
    "İletişim & Medya": 16.0,
    "Sağlık & İlaç": 15.0,
    "Finans": 10.0,
}


def _fetch_peer_info(ticker: str) -> dict:
    try:
        return yf.Ticker(ticker).info or {}
    except Exception:
        return {}


def _extract_pe(info: dict) -> Optional[float]:
    # prefer forward P/E; fall back to trailing
    for key in ("forwardPE", "trailingPE"):
        val = info.get(key)
        if val is not None:
            try:
                v = float(val)
                if PE_MIN <= v <= PE_MAX:
                    return v
            except (TypeError, ValueError):
                pass
    return None


def _extract_ev_rev(info: dict) -> Optional[float]:
    val = info.get("enterpriseToRevenue")
    if val is not None:
        try:
            v = float(val)
            if EV_REV_MIN <= v <= EV_REV_MAX:
                return v
        except (TypeError, ValueError):
            pass
    return None


def _extract_ev_ebitda(info: dict) -> Optional[float]:
    val = info.get("enterpriseToEbitda")
    if val is None:
        # derive from raw fields if available
        ev = info.get("enterpriseValue")
        eb = info.get("ebitda")
        if ev and eb and float(eb) > 0:
            val = float(ev) / float(eb)
    if val is not None:
        try:
            v = float(val)
            if EV_EBITDA_MIN <= v <= EV_EBITDA_MAX:
                return v
        except (TypeError, ValueError):
            pass
    return None


_CACHE_TTL_SECONDS = 4 * 3600
_multiples_cache: dict = {"data": None, "fetched_at": 0.0}
_ticker_multiples_cache: Dict[str, Dict[str, float]] = {}


def get_ticker_multiples(ticker: str) -> Optional[Dict[str, float]]:
    """Ticker'a özel peer listesi varsa o sektörün multiplerini döndürür."""
    ticker = ticker.upper().replace(".IS", "")
    if ticker not in TICKER_PEERS_US:
        return None
    if ticker in _ticker_multiples_cache:
        return _ticker_multiples_cache[ticker]
    peers = TICKER_PEERS_US[ticker]
    pe_vals, ev_vals, ev_rev_vals = _collect_sector_vals(peers, 0.1)
    entry: Dict[str, float] = {}
    from data.sector import robust_median  # noqa: F811
    pe_med = robust_median(pe_vals)
    ev_med = robust_median(ev_vals)
    ev_rev_med = robust_median(ev_rev_vals)
    if pe_med is not None:
        entry["pe"] = pe_med
    if ev_med is not None:
        entry["ev_ebitda"] = ev_med
    if ev_rev_med is not None:
        entry["ev_rev"] = ev_rev_med
    if entry:
        print(f"[peer_multiples] {ticker} (ticker-override): P/E={entry.get('pe')} EV/EBITDA={entry.get('ev_ebitda')} EV/Rev={entry.get('ev_rev')}")
    _ticker_multiples_cache[ticker] = entry
    return entry if entry else None


def get_live_sector_multiples() -> Dict[str, Dict[str, float]]:
    """Cached wrapper — re-fetches at most once every 4 hours."""
    now = time.time()
    if _multiples_cache["data"] is not None and now - _multiples_cache["fetched_at"] < _CACHE_TTL_SECONDS:
        return _multiples_cache["data"]
    result = fetch_live_sector_multiples()
    _multiples_cache["data"] = result
    _multiples_cache["fetched_at"] = now
    return result


def _collect_sector_vals(tickers: list[str], delay: float) -> tuple[list[float], list[float], list[float]]:
    pe_vals: list[float] = []
    ev_vals: list[float] = []
    ev_rev_vals: list[float] = []
    for ticker in tickers:
        info = _fetch_peer_info(ticker)
        pe = _extract_pe(info)
        ev = _extract_ev_ebitda(info)
        ev_rev = _extract_ev_rev(info)
        if pe is not None:
            pe_vals.append(pe)
        if ev is not None:
            ev_vals.append(ev)
        if ev_rev is not None:
            ev_rev_vals.append(ev_rev)
        time.sleep(delay)
    return pe_vals, ev_vals, ev_rev_vals


def fetch_live_sector_multiples(
    peers: Dict[str, list[str]] | None = None,
    delay: float = 0.1,
) -> Dict[str, Dict[str, float]]:
    """
    Returns {sector: {"pe": median_pe, "ev_ebitda": median_ev_ebitda}}.
    Sectors with insufficient data are omitted (caller falls back to static config).
    """
    sector_map = peers or SECTOR_PEERS_US
    result: Dict[str, Dict[str, float]] = {}

    for sector, tickers in sector_map.items():
        pe_vals, ev_vals, ev_rev_vals = _collect_sector_vals(tickers, delay)
        entry: Dict[str, float] = {}
        pe_med = robust_median(pe_vals)
        ev_med = robust_median(ev_vals)
        ev_rev_med = robust_median(ev_rev_vals)
        if pe_med is not None:
            floor = SECTOR_PE_FLOORS.get(sector, 0.0)
            entry["pe"] = max(pe_med, floor)
        if ev_med is not None:
            entry["ev_ebitda"] = ev_med
        if ev_rev_med is not None:
            entry["ev_rev"] = ev_rev_med
        if entry:
            result[sector] = entry
            print(f"[peer_multiples] {sector}: P/E={entry.get('pe')} EV/EBITDA={entry.get('ev_ebitda')} EV/Rev={entry.get('ev_rev')}")

    return result
