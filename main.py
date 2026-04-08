from __future__ import annotations

import argparse
from datetime import datetime
from typing import Iterable, Optional

import pandas as pd

from benchmark_report import build_report_rows
from model_validation import build_validation_frame
from ratio_engine.constants import COLUMNS_ORDER, NUMERIC_COLUMNS
from ratio_engine.service import analyze_symbols
from sector import TR_PROFILE, US_PROFILE, build_sector_maps, build_sector_row
from update_macro_config import main as update_macro_config_main
from valuation import AVERAGE_FAIR_PRICE_LABEL, load_tickers, run_valuation
from valuation_backtest import evaluate_backtest, snapshot_valuations


DEFAULT_INPUT = "coverage.txt"
DEFAULT_OUTPUT = "investment_report.xlsx"
SIGNAL_CONFIDENCE_LABEL = "Sinyal Güven Seviyesi"


def parse_args(argv: Optional[Iterable[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Tek Excel raporunda yatirim analiz paketi")
    parser.add_argument("--input", default=DEFAULT_INPUT)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--refresh-macro", action="store_true")
    parser.add_argument("--auto-classify-sectors", action="store_true")
    parser.add_argument("--include-backtest", action="store_true")
    parser.add_argument("--backtest-horizon-days", type=int, default=30)
    parser.add_argument("--signal-threshold-pct", type=float, default=10.0)
    return parser.parse_args(list(argv) if argv is not None else None)


def order_valuation_columns(frame: pd.DataFrame) -> pd.DataFrame:
    preferred = [
        "Kod",
        "Sektör",
        "Para Birimi",
        "Sinyal Kalite Skoru",
        SIGNAL_CONFIDENCE_LABEL,
        "Güncel Fiyat",
        "Beklenen Getiri (%)",
        "WACC",
        "Ortalama Büyüme",
        "DCF Değerlemesi",
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


def build_sector_frames(auto_classify: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    tr_map, us_map = build_sector_maps(auto_classify=auto_classify)
    tr_rows = [build_sector_row(sector_name, tickers, TR_PROFILE) for sector_name, tickers in tr_map.items()]
    us_rows = [build_sector_row(sector_name, tickers, US_PROFILE) for sector_name, tickers in us_map.items()]
    return pd.DataFrame(tr_rows), pd.DataFrame(us_rows)


def build_summary_frame(
    input_count: int,
    valuation_frame: pd.DataFrame,
    ratio_frame: pd.DataFrame,
    ratio_errors_frame: pd.DataFrame,
    benchmark_frame: pd.DataFrame,
    validation_frame: pd.DataFrame,
    backtest_frame: pd.DataFrame,
) -> pd.DataFrame:
    high_quality = int((valuation_frame.get(SIGNAL_CONFIDENCE_LABEL, pd.Series(dtype=str)) == "High").sum())
    medium_quality = int((valuation_frame.get(SIGNAL_CONFIDENCE_LABEL, pd.Series(dtype=str)) == "Medium").sum())
    low_quality = int((valuation_frame.get(SIGNAL_CONFIDENCE_LABEL, pd.Series(dtype=str)) == "Low").sum())

    rows = [
        {"Metric": "Run Timestamp", "Value": datetime.now().isoformat(timespec="seconds")},
        {"Metric": "Input Ticker Count", "Value": input_count},
        {"Metric": "Valuation Rows", "Value": len(valuation_frame)},
        {"Metric": "Ratio Rows", "Value": len(ratio_frame)},
        {"Metric": "Ratio Failed Rows", "Value": len(ratio_errors_frame)},
        {"Metric": "Benchmark Rows", "Value": len(benchmark_frame)},
        {"Metric": "Validation Rows", "Value": len(validation_frame)},
        {"Metric": "Backtest Rows", "Value": len(backtest_frame)},
        {"Metric": "High Quality Signals", "Value": high_quality},
        {"Metric": "Medium Quality Signals", "Value": medium_quality},
        {"Metric": "Low Quality Signals", "Value": low_quality},
    ]
    return pd.DataFrame(rows)


def write_sheet(writer: pd.ExcelWriter, sheet_name: str, frame: pd.DataFrame) -> None:
    if frame.empty:
        pd.DataFrame([{"info": "no data"}]).to_excel(writer, sheet_name=sheet_name, index=False)
        return
    frame.to_excel(writer, sheet_name=sheet_name, index=False)


def main(argv: Optional[Iterable[str]] = None) -> int:
    args = parse_args(argv)
    if args.refresh_macro:
        update_macro_config_main()

    tickers = load_tickers(args.input)
    valuation_rows = run_valuation(tickers)
    valuation_frame = pd.DataFrame(valuation_rows)
    if not valuation_frame.empty:
        valuation_frame = order_valuation_columns(valuation_frame)

    ratio_frame, ratio_errors_frame = build_ratio_frames(tickers)
    tr_sector_frame, us_sector_frame = build_sector_frames(auto_classify=args.auto_classify_sectors)
    benchmark_frame = pd.DataFrame(build_report_rows())
    validation_frame = build_validation_frame(tickers)

    backtest_frame = pd.DataFrame()
    if args.include_backtest:
        snapshot_valuations(tickers)
        backtest_frame = evaluate_backtest(
            horizon_days=args.backtest_horizon_days,
            signal_threshold_pct=args.signal_threshold_pct,
        )

    summary_frame = build_summary_frame(
        input_count=len(tickers),
        valuation_frame=valuation_frame,
        ratio_frame=ratio_frame,
        ratio_errors_frame=ratio_errors_frame,
        benchmark_frame=benchmark_frame,
        validation_frame=validation_frame,
        backtest_frame=backtest_frame,
    )

    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        write_sheet(writer, "Summary", summary_frame)
        write_sheet(writer, "Valuation", valuation_frame)
        write_sheet(writer, "Ratios", ratio_frame)
        write_sheet(writer, "Ratio_Errors", ratio_errors_frame)
        write_sheet(writer, "Sector_TR", tr_sector_frame)
        write_sheet(writer, "Sector_US", us_sector_frame)
        write_sheet(writer, "Benchmark", benchmark_frame)
        write_sheet(writer, "Validation", validation_frame)
        if args.include_backtest:
            write_sheet(writer, "Backtest", backtest_frame)

    print(f"Kaydedildi -> {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
