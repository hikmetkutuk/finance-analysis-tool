from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from data.market_data_provider import fetch_ticker_bundle, normalized_info
from valuation import AVERAGE_FAIR_PRICE_LABEL, load_tickers, value_ticker


VALIDATION_REPORT_PATH = Path("valuation_validation_report.csv")


def parse_tr_formatted_number(value: str) -> Optional[float]:
    if not value:
        return None
    normalized = value.replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except (TypeError, ValueError):
        return None


def build_validation_frame(tickers: list[str]) -> pd.DataFrame:
    rows = []
    for ticker in tickers:
        valuation_row = value_ticker(ticker)
        fair_value = parse_tr_formatted_number(valuation_row.get(AVERAGE_FAIR_PRICE_LABEL, ""))
        info = normalized_info(fetch_ticker_bundle(ticker))
        current_price = info.get("currentPrice")
        valuation_gap_pct = None
        abs_error_pct = None
        if fair_value and current_price and current_price > 0:
            valuation_gap_pct = (fair_value / current_price - 1) * 100
            abs_error_pct = abs((current_price - fair_value) / current_price) * 100
        rows.append(
            {
                "ticker": ticker,
                "sector": valuation_row.get("Sektör", ""),
                "fair_value": fair_value,
                "current_price": current_price,
                "valuation_gap_pct": valuation_gap_pct,
                "abs_error_pct": abs_error_pct,
                "warnings": valuation_row.get("Model Kalite Uyarıları", ""),
            }
        )
    return pd.DataFrame(rows)


def print_summary(frame: pd.DataFrame) -> None:
    valid = frame.dropna(subset=["fair_value", "current_price"])
    if valid.empty:
        print("Doğrulama için yeterli veri yok.")
        return
    mape = valid["abs_error_pct"].mean()
    median_error = valid["abs_error_pct"].median()
    low_quality = valid[valid["warnings"].str.len() > 0]
    print(f"Coverage: {len(valid)}/{len(frame)}")
    print(f"MAPE: {mape:.2f}%")
    print(f"Median abs error: {median_error:.2f}%")
    print(f"Warningli kayıt: {len(low_quality)}")


def main() -> None:
    tickers = load_tickers("coverage.txt")
    frame = build_validation_frame(tickers)
    frame.to_csv(VALIDATION_REPORT_PATH, index=False)
    print(f"Kaydedildi -> {VALIDATION_REPORT_PATH}")
    print_summary(frame)


if __name__ == "__main__":
    main()
