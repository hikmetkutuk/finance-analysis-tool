import argparse
import json
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from data.sector import build_sector_maps

DEFAULT_TR_MULTIPLES_PATH = Path("sector_multiples_tr.csv")
DEFAULT_US_MULTIPLES_PATH = Path("sector_multiples_us.csv")
DEFAULT_OVERRIDES_PATH = Path("sector_overrides.json")
METRIC_COLUMNS = ("pe", "pb", "ev_ebitda")
METRIC_BOUNDS = {
    "pe": (1.0, 80.0),
    "pb": (0.2, 20.0),
    "ev_ebitda": (1.0, 40.0),
}


def safe_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def sanitize_metric(metric_name: str, metric_value: Optional[float]) -> Optional[float]:
    if metric_value is None:
        return None
    bounds = METRIC_BOUNDS.get(metric_name)
    if bounds is None:
        return metric_value
    lower, upper = bounds
    if not lower <= metric_value <= upper:
        return None
    return metric_value


def sanitize_metrics(metrics: dict[str, float]) -> dict[str, float]:
    sanitized: dict[str, float] = {}
    for metric_name, metric_value in metrics.items():
        sanitized_value = sanitize_metric(metric_name, metric_value)
        if sanitized_value is not None:
            sanitized[metric_name] = sanitized_value
    return sanitized


def extract_metrics(row: dict[str, Any]) -> dict[str, float]:
    metrics: dict[str, float] = {}
    for metric in METRIC_COLUMNS:
        metric_value = safe_float(row.get(metric))
        if metric_value is not None:
            metrics[metric] = metric_value
    return sanitize_metrics(metrics)


def build_market_overrides(sector_csv: Path, sector_map: dict[str, list[str]]) -> dict[str, dict[str, float]]:
    if not sector_csv.exists():
        return {}
    frame = pd.read_csv(sector_csv)
    if "sector" not in frame.columns:
        return {}
    overrides: dict[str, dict[str, float]] = {}
    for row in frame.to_dict("records"):
        sector_name = str(row.get("sector", "")).strip()
        if not sector_name:
            continue
        metrics = extract_metrics(row)
        if not metrics:
            continue
        for ticker in sector_map.get(sector_name, []):
            overrides[ticker] = dict(metrics)
    return overrides


def build_sector_overrides(
    tr_csv: Path = DEFAULT_TR_MULTIPLES_PATH,
    us_csv: Path = DEFAULT_US_MULTIPLES_PATH,
    auto_classify: bool = False,
) -> dict[str, dict[str, float]]:
    tr_map, us_map = build_sector_maps(auto_classify=auto_classify)
    overrides = build_market_overrides(tr_csv, tr_map)
    overrides.update(build_market_overrides(us_csv, us_map))
    return overrides


def normalize_loaded_overrides(raw: Any) -> dict[str, dict[str, float]]:
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, dict[str, float]] = {}
    for ticker, metrics in raw.items():
        if not isinstance(ticker, str) or not isinstance(metrics, dict):
            continue
        normalized_metrics = extract_metrics(metrics)
        if normalized_metrics:
            normalized[ticker] = normalized_metrics
    return normalized


def save_sector_overrides(
    overrides: dict[str, dict[str, float]],
    path: Path = DEFAULT_OVERRIDES_PATH,
) -> None:
    path.write_text(json.dumps(overrides, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def load_sector_overrides(
    path: Path = DEFAULT_OVERRIDES_PATH,
    rebuild_if_missing: bool = True,
    tr_csv: Path = DEFAULT_TR_MULTIPLES_PATH,
    us_csv: Path = DEFAULT_US_MULTIPLES_PATH,
) -> dict[str, dict[str, float]]:
    if path.exists():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
            loaded = normalize_loaded_overrides(raw)
            if loaded:
                return loaded
        except json.JSONDecodeError:
            pass
    if not rebuild_if_missing:
        return {}
    overrides = build_sector_overrides(tr_csv=tr_csv, us_csv=us_csv, auto_classify=False)
    if overrides:
        save_sector_overrides(overrides, path)
    return overrides


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Sektorel override sozlugu olusturur.")
    parser.add_argument("--tr-csv", default=str(DEFAULT_TR_MULTIPLES_PATH))
    parser.add_argument("--us-csv", default=str(DEFAULT_US_MULTIPLES_PATH))
    parser.add_argument("--output", default=str(DEFAULT_OVERRIDES_PATH))
    parser.add_argument("--auto-classify", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    overrides = build_sector_overrides(
        tr_csv=Path(args.tr_csv),
        us_csv=Path(args.us_csv),
        auto_classify=args.auto_classify,
    )
    save_sector_overrides(overrides, Path(args.output))
    print(f"Kaydedildi -> {args.output} ({len(overrides)} ticker)")


if __name__ == "__main__":
    main()
