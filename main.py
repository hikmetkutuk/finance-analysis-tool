from __future__ import annotations

import argparse
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


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    if args.refresh_macro:
        update_macro_config_main()

    tickers = load_tickers(args.input)
    start = time.time()
    print("Aşama: Değerleme")
    valuation_rows = run_valuation(tickers)
    valuation_frame = pd.DataFrame(valuation_rows)
    if not valuation_frame.empty:
        valuation_frame = order_valuation_columns(valuation_frame)

    print("Aşama: Financials + DCF")
    financials_frame, dcf_frame = build_financials_and_dcf_frames(
        tickers,
        parallel_workers=max(1, int(args.financials_workers)),
    )
    dcf_frame = attach_dcf_professional_value(dcf_frame, valuation_frame)

    print("Aşama: Oranlar")
    ratio_frame, _ = build_ratio_frames(tickers)
    print("Aşama: Şablon Rapor")

    if args.include_backtest:
        snapshot_valuations(tickers)
        evaluate_backtest(
            horizon_days=args.backtest_horizon_days,
            signal_threshold_pct=args.signal_threshold_pct,
        )

    write_template_report(
        output_path=args.output,
        tickers=tickers,
        valuation_frame=valuation_frame,
        financials_frame=financials_frame,
        dcf_frame=dcf_frame,
        ratio_frame=ratio_frame,
    )

    elapsed = time.time() - start
    print(f"Kaydedildi -> {args.output} ({elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
