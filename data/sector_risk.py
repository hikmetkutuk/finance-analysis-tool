from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from statistics import median
from typing import Any

from data.sector import fetch_info, load_sector_assignments, safe_float

DEFAULT_PATH = Path("sector_risk_config.json")
MIN_PEERS = 3
MAX_PEERS = 10


def _unlevered_beta(info: dict[str, Any], fallback_tax_rate: float) -> float | None:
    beta = safe_float(info.get("beta"))
    equity = safe_float(info.get("marketCap"))
    debt = safe_float(info.get("totalDebt"))
    tax_rate = safe_float(info.get("effectiveTaxRate")) or fallback_tax_rate
    if beta is None or equity is None or debt is None or not 0.2 <= beta <= 3.5 or equity <= 0 or debt < 0:
        return None
    debt_to_equity = min(debt / equity, 5.0)
    denominator = 1 + (1 - min(max(tax_rate, 0.0), 0.40)) * debt_to_equity
    unlevered = beta / denominator if denominator > 0 else None
    return unlevered if unlevered is not None and 0.2 <= unlevered <= 2.0 else None


def _balanced_sample(tickers: list[str]) -> list[str]:
    ordered = sorted(tickers)
    if len(ordered) <= MAX_PEERS:
        return ordered
    step = (len(ordered) - 1) / (MAX_PEERS - 1)
    return [ordered[round(index * step)] for index in range(MAX_PEERS)]


def market_sector_peers(market: str, target_sectors: set[str] | None = None) -> dict[str, list[str]]:
    assignments = load_sector_assignments().get(market, {})
    sectors: dict[str, list[str]] = {}
    for ticker, sector_name in assignments.items():
        if target_sectors is None or sector_name in target_sectors:
            sectors.setdefault(sector_name, []).append(ticker)
    return {sector: _balanced_sample(tickers) for sector, tickers in sectors.items()}


def _load_existing(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"as_of": None, "defaults": {}, "sectors": {}}
    return raw if isinstance(raw, dict) else {"as_of": None, "defaults": {}, "sectors": {}}


def refresh_sector_risk_config(
    market: str,
    target_sectors: set[str] | None = None,
    path: Path = DEFAULT_PATH,
) -> dict[str, Any]:
    config = _load_existing(path)
    sectors_config = config.setdefault("sectors", {})
    defaults_config = config.setdefault("defaults", {})
    fallback_tax_rate = 0.25 if market == "tr" else 0.21
    market_values: list[float] = []

    for sector_name, tickers in market_sector_peers(market, target_sectors).items():
        values = [
            beta
            for ticker in tickers
            if (beta := _unlevered_beta(fetch_info(ticker), fallback_tax_rate)) is not None
        ]
        if len(values) < MIN_PEERS:
            continue
        sector_beta = round(float(median(values)), 4)
        market_values.extend(values)
        sectors_config[f"{market}:{sector_name}"] = {
            "unlevered_beta": sector_beta,
            "sample_size": len(values),
            "source": "live_sector_peer_median",
        }

    if market_values:
        defaults_config[market] = {
            "unlevered_beta": round(float(median(market_values)), 4),
            "sample_size": len(market_values),
            "source": "live_market_peer_median",
        }
    config["as_of"] = datetime.now(UTC).isoformat()
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    temporary.replace(path)
    return config
