from __future__ import annotations

import argparse
import time
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable, Optional

import pandas as pd
from openpyxl.utils import get_column_letter

from reporting.benchmark_report import build_report_rows
from reporting.financials_report import build_financials_and_dcf_frames
from reporting.model_validation import build_validation_frame
from ratio_engine.constants import COLUMNS_ORDER, NUMERIC_COLUMNS
from ratio_engine.service import analyze_symbols
from data.sector import TR_PROFILE, US_PROFILE, build_sector_maps, build_sector_row
from pipelines.update_macro_config import main as update_macro_config_main
from valuation import AVERAGE_FAIR_PRICE_LABEL, load_tickers, run_valuation
from reporting.valuation_backtest import evaluate_backtest, snapshot_valuations


DEFAULT_INPUT = "coverage.txt"
DEFAULT_OUTPUT = "investment_report.xlsx"
SIGNAL_CONFIDENCE_LABEL = "Sinyal Güven Seviyesi"
SECTOR_LABEL = "Sektör"


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
        "Kod",
        SECTOR_LABEL,
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


def filter_sector_map(sector_map: dict[str, list[str]], selected_tickers: list[str]) -> dict[str, list[str]]:
    selected = {ticker.upper() for ticker in selected_tickers}
    filtered: dict[str, list[str]] = {}
    for sector_name, sector_tickers in sector_map.items():
        matched = [ticker for ticker in sector_tickers if ticker.upper() in selected]
        if matched:
            filtered[sector_name] = matched
    return filtered


def build_sector_frames(
    auto_classify: bool,
    selected_tickers: list[str],
    full_universe: bool,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    tr_map, us_map = build_sector_maps(auto_classify=auto_classify)
    if not full_universe:
        tr_map = filter_sector_map(tr_map, selected_tickers)
        us_map = filter_sector_map(us_map, selected_tickers)
    tr_rows = [build_sector_row(sector_name, tickers, TR_PROFILE) for sector_name, tickers in tr_map.items()]
    us_rows = [build_sector_row(sector_name, tickers, US_PROFILE) for sector_name, tickers in us_map.items()]
    return reorder_sector_frame(pd.DataFrame(tr_rows)), reorder_sector_frame(pd.DataFrame(us_rows))


def reorder_sector_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    rename_map = {
        "sector": SECTOR_LABEL,
        "pb": "PD / DD",
        "pe": "F/K",
        "fd": "FD",
        "ev_ebitda": "Firma Değeri/Favök",
    }
    frame = frame.rename(columns=rename_map)
    preferred = [SECTOR_LABEL, "PD / DD", "F/K", "FD", "Firma Değeri/Favök"]
    ordered = [column for column in preferred if column in frame.columns]
    ordered.extend(column for column in frame.columns if column not in ordered)
    return frame[ordered]


def build_summary_frame(
    input_count: int,
    valuation_frame: pd.DataFrame,
    financials_frame: pd.DataFrame,
    dcf_frame: pd.DataFrame,
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
        {"Metric": "Financials Rows", "Value": len(financials_frame)},
        {"Metric": "DCF Rows", "Value": len(dcf_frame)},
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
    display_frame = format_frame_for_tr_display(frame)
    display_frame.to_excel(writer, sheet_name=sheet_name, index=False)
    style_numeric_columns(writer, sheet_name, display_frame)


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


def style_numeric_columns(writer: pd.ExcelWriter, sheet_name: str, frame: pd.DataFrame) -> None:
    worksheet = writer.sheets[sheet_name]
    for column_index, column_name in enumerate(frame.columns, start=1):
        series = frame[column_name]
        excel_column = get_column_letter(column_index)
        lengths = [len(str(column_name))]
        lengths.extend(len(str(value)) for value in series.dropna().head(100))
        max_len = max(lengths)
        worksheet.column_dimensions[excel_column].width = min(40, max(12, max_len + 2))



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

    print("Aşama: Oranlar")
    ratio_frame, ratio_errors_frame = build_ratio_frames(tickers)
    print("Aşama: Sektör")
    sector_auto_classify = args.auto_classify_sectors and args.full_sector_universe
    if args.auto_classify_sectors and not args.full_sector_universe:
        print("Not: --auto-classify-sectors yalnızca --full-sector-universe ile birlikte uygulanır.")
    tr_sector_frame, us_sector_frame = build_sector_frames(
        auto_classify=sector_auto_classify,
        selected_tickers=tickers,
        full_universe=args.full_sector_universe,
    )
    benchmark_frame = pd.DataFrame()
    if not args.skip_benchmark:
        print("Aşama: Benchmark")
        benchmark_frame = pd.DataFrame(build_report_rows())
    print("Aşama: Doğrulama")
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
        financials_frame=financials_frame,
        dcf_frame=dcf_frame,
        ratio_frame=ratio_frame,
        ratio_errors_frame=ratio_errors_frame,
        benchmark_frame=benchmark_frame,
        validation_frame=validation_frame,
        backtest_frame=backtest_frame,
    )

    with pd.ExcelWriter(args.output, engine="openpyxl") as writer:
        write_sheet(writer, "Summary", summary_frame)
        write_sheet(writer, "Valuation", valuation_frame)
        write_sheet(writer, "Financials", financials_frame)
        write_sheet(writer, "DCF", dcf_frame)
        write_sheet(writer, "Ratios", ratio_frame)
        write_sheet(writer, "Ratio_Errors", ratio_errors_frame)
        write_sheet(writer, "Sector_TR", tr_sector_frame)
        write_sheet(writer, "Sector_US", us_sector_frame)
        if not args.skip_benchmark:
            write_sheet(writer, "Benchmark", benchmark_frame)
        write_sheet(writer, "Validation", validation_frame)
        if args.include_backtest:
            write_sheet(writer, "Backtest", backtest_frame)

    elapsed = time.time() - start
    print(f"Kaydedildi -> {args.output} ({elapsed:.1f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
