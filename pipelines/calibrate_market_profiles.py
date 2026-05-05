from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from reporting.valuation_backtest import (  # noqa: E402
    BACKTEST_REPORT_PATH,
    CALIBRATION_REPORT_PATH,
    build_calibration_report,
    evaluate_backtest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TR ve US backtest sonuclarini market bazli kalibre eder.")
    parser.add_argument("--horizon-days", type=int, default=30)
    parser.add_argument("--signal-threshold-pct", type=float, default=10.0)
    parser.add_argument("--skip-refresh", action="store_true")
    return parser.parse_args()


def read_backtest_report(path: Path) -> pd.DataFrame:
    report = pd.read_csv(path)
    if isinstance(report, pd.DataFrame):
        return report
    return report.read()


def main() -> int:
    args = parse_args()
    if args.skip_refresh and BACKTEST_REPORT_PATH.exists():
        report = read_backtest_report(BACKTEST_REPORT_PATH)
    else:
        report = evaluate_backtest(
            horizon_days=args.horizon_days,
            signal_threshold_pct=args.signal_threshold_pct,
        )
    calibration = build_calibration_report(report)
    if calibration.empty:
        print("Kalibrasyon icin yeterli backtest verisi yok.")
        return 1
    print(f"Kaydedildi -> {CALIBRATION_REPORT_PATH}")
    print(calibration.head(20).to_string(index=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
