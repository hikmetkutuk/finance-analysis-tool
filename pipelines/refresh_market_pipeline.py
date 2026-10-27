from __future__ import annotations

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

import pandas as pd

from data.sector import TR_PROFILE, calculate_sector_multiples, prepare_sector_map
from data.sector_override_builder import (
    build_market_overrides,
    load_sector_overrides,
    save_sector_overrides,
)
from data.sector_risk import market_sector_peers, refresh_sector_risk_config
from pipelines.update_macro_config import update_tr_macro_config

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOT_ROOT = ROOT / "data" / "market_snapshots"
STATUS_FILE = ROOT / "market_refresh_status.json"
MANAGED_FILES = (
    ROOT / "macro_config.json",
    ROOT / "sector_assignments.json",
    ROOT / "sector_overrides.json",
    ROOT / "sector_multiples_tr.csv",
    ROOT / "sector_risk_config.json",
)
MARKET_REFRESH_ERRORS = (
    OSError,
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    json.JSONDecodeError,
    pd.errors.ParserError,
)


def _timestamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%S%fZ")


def _write_status(payload: dict) -> None:
    temporary = STATUS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(STATUS_FILE)


def _backup() -> Path:
    destination = SNAPSHOT_ROOT / _timestamp()
    destination.mkdir(parents=True, exist_ok=False)
    for source in MANAGED_FILES:
        if source.exists():
            shutil.copy2(source, destination / source.name)
    return destination


def _restore(snapshot: Path) -> None:
    for destination in MANAGED_FILES:
        source = snapshot / destination.name
        if source.exists():
            shutil.copy2(source, destination)


def _validate_universe() -> list[str]:
    source = ROOT / "xu030.txt"
    tickers = [line.strip().upper() for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(tickers) != 30 or len(set(tickers)) != 30:
        raise ValueError(f"XU030 evreni 30 benzersiz ticker içermeli; bulunan: {len(set(tickers))}")
    invalid = [ticker for ticker in tickers if not ticker.endswith(".IS")]
    if invalid:
        raise ValueError(f".IS eki eksik ticker: {', '.join(invalid)}")
    return tickers


def _validate_sector_multiples(path: Path, required_sectors: set[str]) -> None:
    frame = pd.read_csv(path)
    required = {"sector", "ticker_count_total"}
    if frame.empty or not required.issubset(frame.columns):
        raise ValueError("Sektör çarpanı çıktısı boş veya geçersiz")
    available_sectors = set(frame["sector"].dropna().astype(str))
    missing_sectors = sorted(required_sectors - available_sectors)
    if missing_sectors:
        raise ValueError(f"Sektör çarpanı eksik: {', '.join(missing_sectors)}")
    ticker_total = cast(Any, frame["ticker_count_total"].sum())
    if int(ticker_total) < len(required_sectors):
        raise ValueError("Sektör çarpanı peer örneklemi yetersiz")


def refresh_xu030_market_data() -> dict:
    """Manuel tam yenileme; herhangi bir hatada son sağlıklı dosyaları geri yükler."""
    started_at = datetime.now(UTC).isoformat()
    snapshot = _backup()
    try:
        tickers = _validate_universe()
        update_tr_macro_config()
        sector_map = prepare_sector_map(TR_PROFILE, auto_classify=True)
        refresh_sector_risk_config("tr", set(sector_map))
        peer_sector_map = market_sector_peers("tr", set(sector_map))
        multiples_path = ROOT / "sector_multiples_tr.csv"
        calculate_sector_multiples(peer_sector_map, str(multiples_path), TR_PROFILE)
        _validate_sector_multiples(multiples_path, set(sector_map))

        overrides = load_sector_overrides(rebuild_if_missing=False)
        tr_overrides = build_market_overrides(multiples_path, sector_map)
        if set(tr_overrides) != set(tickers):
            missing = sorted(set(tickers) - set(tr_overrides))
            raise ValueError(f"Sektör override kaydı eksik: {', '.join(missing)}")
        overrides.update(tr_overrides)
        save_sector_overrides(overrides)

        result = {
            "status": "completed",
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "ticker_count": len(tickers),
            "snapshot": str(snapshot.relative_to(ROOT)),
        }
        _write_status(result)
        return result
    except MARKET_REFRESH_ERRORS as exc:
        _restore(snapshot)
        result = {
            "status": "failed",
            "started_at": started_at,
            "finished_at": datetime.now(UTC).isoformat(),
            "error": str(exc),
            "restored_from": str(snapshot.relative_to(ROOT)),
        }
        _write_status(result)
        raise


def main() -> int:
    print(json.dumps(refresh_xu030_market_data(), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
