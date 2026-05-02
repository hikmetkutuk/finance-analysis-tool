from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import platform
import subprocess
import sys
import time
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

import pandas as pd

from reporting.financials_report import build_financials_and_dcf_frames
from reporting.template_report import write_template_report
from ratio_engine.constants import COLUMNS_ORDER, NUMERIC_COLUMNS
from ratio_engine.service import analyze_symbols
from pipelines.update_macro_config import main as update_macro_config_main
from valuation import AVERAGE_FAIR_PRICE_LABEL, load_tickers, run_valuation
from reporting.valuation_backtest import evaluate_backtest, snapshot_valuations


DEFAULT_INPUT = "coverage.txt"
DEFAULT_OUTPUT = "investment_report.xlsx"
SIGNAL_CONFIDENCE_LABEL = "Sinyal Güven Seviyesi"
SECTOR_LABEL = "Sektör"
CODE_COLUMN = "Kod"
VALUATION_DCF_COLUMN = "DCF Değerlemesi"
DCF_PROFESSIONAL_VALUE_COLUMN = "Profesyonel Değer"
DEFAULT_LOG_DIR = Path("logs")
RUN_LOGGER_NAME = "analysis_run"
MACRO_CONFIG_PATH = Path("macro_config.json")


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tek Excel raporunda yatirim analiz paketi")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--refresh-macro", action="store_true")
    parser.add_argument("--auto-classify-sectors", action="store_true")
    parser.add_argument("--include-backtest", action="store_true")
    parser.add_argument("--skip-benchmark", action="store_true")
    parser.add_argument("--backtest-horizon-days", type=int, default=30)
    parser.add_argument("--signal-threshold-pct", type=float, default=10.0)
    parser.add_argument("--full-sector-universe", action="store_true")
    parser.add_argument("--financials-workers", type=int, default=4)
    parser.add_argument("--log-file")
    parser.add_argument("--run-metadata-output")
    return parser.parse_args(list(argv) if argv is not None else None)


def order_valuation_columns(frame: pd.DataFrame) -> pd.DataFrame:
    preferred = [
        CODE_COLUMN,
        SECTOR_LABEL,
        "Para Birimi",
        "Sinyal Kalite Skoru",
        SIGNAL_CONFIDENCE_LABEL,
        "Güncel Fiyat",
        "Beklenen Getiri (%)",
        "WACC",
        "Ortalama Büyüme",
        VALUATION_DCF_COLUMN,
        "F/K Değerlemesi",
        "PD/DD Finansal Model",
        "EV/EBITDA Değerlemesi",
        "DDM Değerlemesi",
        "EFK Değerlemesi",
        "NDK Değerlemesi",
        "Graham Değerlemesi",
        "Model Kalite Uyarıları",
        AVERAGE_FAIR_PRICE_LABEL,
    ]
    ordered = [column for column in preferred if column in frame.columns]
    ordered.extend(column for column in frame.columns if column not in ordered)
    return frame[ordered]


def build_ratio_frames(tickers: list[str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows, failed_symbols = analyze_symbols(tickers, market="auto")
    ratio_frame = pd.DataFrame(rows)
    if not ratio_frame.empty:
        ordered_cols = [column for column in COLUMNS_ORDER if column in ratio_frame.columns]
        ratio_frame = ratio_frame[ordered_cols]
        existing_numeric_cols = [column for column in NUMERIC_COLUMNS if column in ratio_frame.columns]
        if existing_numeric_cols:
            ratio_frame[existing_numeric_cols] = ratio_frame[existing_numeric_cols].round(2)
    errors_frame = pd.DataFrame(failed_symbols)
    return ratio_frame, errors_frame


def attach_dcf_professional_value(dcf_frame: pd.DataFrame, valuation_frame: pd.DataFrame) -> pd.DataFrame:
    if dcf_frame.empty:
        return dcf_frame

    enriched = dcf_frame.copy()
    if (
        valuation_frame.empty
        or CODE_COLUMN not in valuation_frame.columns
        or VALUATION_DCF_COLUMN not in valuation_frame.columns
        or CODE_COLUMN not in enriched.columns
    ):
        enriched[DCF_PROFESSIONAL_VALUE_COLUMN] = pd.NA
        return enriched

    valuation_lookup = valuation_frame[[CODE_COLUMN, VALUATION_DCF_COLUMN]].copy()
    valuation_lookup = valuation_lookup.dropna(subset=[CODE_COLUMN]).drop_duplicates(subset=[CODE_COLUMN], keep="last")
    valuation_lookup[VALUATION_DCF_COLUMN] = pd.to_numeric(valuation_lookup[VALUATION_DCF_COLUMN], errors="coerce")
    enriched[DCF_PROFESSIONAL_VALUE_COLUMN] = enriched[CODE_COLUMN].map(
        valuation_lookup.set_index(CODE_COLUMN)[VALUATION_DCF_COLUMN]
    )
    return enriched


def format_tr_numeric(value: Any) -> Any:
    if value is None or pd.isna(value):
        return ""
    try:
        decimal_value = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return value

    sign = "-" if decimal_value < 0 else ""
    decimal_value = abs(decimal_value)
    text = format(decimal_value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    integer_part, dot, fractional_part = text.partition(".")
    try:
        grouped_integer = f"{int(integer_part):,}".replace(",", ".")
    except ValueError:
        grouped_integer = integer_part
    if dot and fractional_part:
        return f"{sign}{grouped_integer},{fractional_part}"
    return f"{sign}{grouped_integer}"


def format_frame_for_tr_display(frame: pd.DataFrame) -> pd.DataFrame:
    display_frame = frame.copy()
    for column_name in display_frame.columns:
        series = display_frame[column_name]
        if not pd.api.types.is_numeric_dtype(series):
            continue
        display_frame[column_name] = series.apply(format_tr_numeric)
    return display_frame


def _default_log_path(output_path: str) -> Path:
    output_name = Path(output_path).stem or "analysis"
    return DEFAULT_LOG_DIR / f"{output_name}.log"


def _default_metadata_path(output_path: str) -> Path:
    output_file = Path(output_path)
    return output_file.with_suffix(".run.json")


def _ensure_parent_dir(path: Path) -> None:
    if path.parent and str(path.parent) != ".":
        path.parent.mkdir(parents=True, exist_ok=True)


def configure_logging(log_path: Path) -> logging.Logger:
    _ensure_parent_dir(log_path)
    logger = logging.getLogger(RUN_LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False
    formatter = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)
    return logger


def _market_counts(tickers: list[str]) -> dict[str, int]:
    return {
        "tr": sum(1 for ticker in tickers if ticker.upper().endswith(".IS")),
        "us": sum(1 for ticker in tickers if not ticker.upper().endswith(".IS")),
    }


def _macro_config_as_of() -> Optional[str]:
    if not MACRO_CONFIG_PATH.exists():
        return None
    try:
        raw = json.loads(MACRO_CONFIG_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None
    as_of = raw.get("as_of")
    return str(as_of) if isinstance(as_of, str) and as_of.strip() else None


def _git_revision() -> Optional[str]:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    revision = completed.stdout.strip()
    return revision or None


def build_run_metadata(
    args: argparse.Namespace,
    tickers: list[str],
    output_path: str,
    log_path: Path,
    metadata_path: Path,
    started_at: str,
) -> dict[str, Any]:
    return {
        "started_at": started_at,
        "input_path": str(args.input),
        "output_path": str(output_path),
        "log_path": str(log_path),
        "metadata_path": str(metadata_path),
        "tickers_total": len(tickers),
        "market_counts": _market_counts(tickers),
        "include_backtest": bool(args.include_backtest),
        "financials_workers": int(args.financials_workers),
        "macro_config_as_of": _macro_config_as_of(),
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "git_revision": _git_revision(),
    }


def finalize_run_metadata(
    metadata: dict[str, Any],
    elapsed_seconds: float,
    valuation_frame: pd.DataFrame,
    ratio_frame: pd.DataFrame,
    financials_frame: pd.DataFrame,
) -> dict[str, Any]:
    finalized = dict(metadata)
    finalized["finished_at"] = datetime.now(timezone.utc).isoformat()
    finalized["elapsed_seconds"] = round(float(elapsed_seconds), 2)
    finalized["valuation_rows"] = int(len(valuation_frame))
    finalized["ratio_rows"] = int(len(ratio_frame))
    finalized["financial_rows"] = int(len(financials_frame))
    return finalized


def write_run_metadata(metadata_path: Path, metadata: dict[str, Any]) -> None:
    _ensure_parent_dir(metadata_path)
    metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    output_path = str(args.output)
    log_path = Path(args.log_file) if args.log_file else _default_log_path(output_path)
    metadata_path = Path(args.run_metadata_output) if args.run_metadata_output else _default_metadata_path(output_path)
    logger = configure_logging(log_path)
    started_at = datetime.now(timezone.utc).isoformat()
    if args.refresh_macro:
        update_macro_config_main()

    tickers = load_tickers(args.input)
    run_metadata = build_run_metadata(args, tickers, output_path, log_path, metadata_path, started_at)
    start = time.time()
    logger.info("Asama: Degerleme")
    valuation_rows = run_valuation(tickers)
    valuation_frame = pd.DataFrame(valuation_rows)
    if not valuation_frame.empty:
        valuation_frame = order_valuation_columns(valuation_frame)

    logger.info("Asama: Financials + DCF")
    financials_frame, dcf_frame = build_financials_and_dcf_frames(
        tickers,
        parallel_workers=max(1, int(args.financials_workers)),
    )
    dcf_frame = attach_dcf_professional_value(dcf_frame, valuation_frame)

    logger.info("Asama: Oranlar")
    ratio_frame, _ = build_ratio_frames(tickers)
    logger.info("Asama: Sablon Rapor")

    if args.include_backtest:
        snapshot_valuations(tickers)
        evaluate_backtest(
            horizon_days=args.backtest_horizon_days,
            signal_threshold_pct=args.signal_threshold_pct,
        )

    write_template_report(
        output_path=output_path,
        tickers=tickers,
        valuation_frame=valuation_frame,
        financials_frame=financials_frame,
        dcf_frame=dcf_frame,
        ratio_frame=ratio_frame,
        run_metadata=run_metadata,
    )

    elapsed = time.time() - start
    finalized_metadata = finalize_run_metadata(run_metadata, elapsed, valuation_frame, ratio_frame, financials_frame)
    write_run_metadata(metadata_path, finalized_metadata)
    logger.info("Kaydedildi -> %s (%.1fs)", output_path, elapsed)
    logger.info("Kaydedildi -> %s", metadata_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
