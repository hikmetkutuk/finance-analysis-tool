from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

from data.market_data_provider import fetch_ticker_bundle, normalized_info
from valuation import AVERAGE_FAIR_PRICE_LABEL, load_tickers, value_ticker


HISTORY_PATH = Path("valuation_history.csv")
BACKTEST_REPORT_PATH = Path("valuation_backtest_report.csv")


@dataclass
class SnapshotRow:
    as_of: str
    ticker: str
    sector: str
    fair_value: Optional[float]
    current_price: Optional[float]
    upside_pct: Optional[float]
    warnings: str


def parse_tr_formatted_number(value: str) -> Optional[float]:
    if not value:
        return None
    normalized = value.replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except (TypeError, ValueError):
        return None


def fetch_price_near(ticker: str, target_date: datetime) -> Optional[float]:
    start = (target_date - timedelta(days=5)).strftime("%Y-%m-%d")
    end = (target_date + timedelta(days=7)).strftime("%Y-%m-%d")
    try:
        history = yf.Ticker(ticker).history(start=start, end=end, interval="1d")
    except (RuntimeError, ValueError, TypeError, KeyError, OSError):
        return None
    if history is None:
        return None
    if not isinstance(history, pd.DataFrame):
        return None
    if history.empty:
        return None
    if "Close" not in history.columns:
        return None
    close = history["Close"].dropna()
    if close.empty:
        return None
    try:
        return float(close.iloc[0])
    except (TypeError, ValueError):
        return None


def build_snapshot_row(ticker: str, as_of: str) -> SnapshotRow:
    result = value_ticker(ticker)
    fair_value = parse_tr_formatted_number(result.get(AVERAGE_FAIR_PRICE_LABEL, ""))
    info = normalized_info(fetch_ticker_bundle(ticker))
    current_price = info.get("currentPrice")
    upside_pct = None
    if fair_value and current_price and current_price > 0:
        upside_pct = (fair_value / current_price - 1) * 100
    return SnapshotRow(
        as_of=as_of,
        ticker=ticker,
        sector=result.get("Sektör", ""),
        fair_value=fair_value,
        current_price=current_price,
        upside_pct=upside_pct,
        warnings=result.get("Model Kalite Uyarıları", ""),
    )


def snapshot_valuations(tickers: list[str], as_of: Optional[str] = None) -> pd.DataFrame:
    if as_of is None:
        as_of = date.today().isoformat()
    rows = [build_snapshot_row(ticker, as_of) for ticker in tickers]
    frame = pd.DataFrame([row.__dict__ for row in rows])
    if HISTORY_PATH.exists():
        history = pd.read_csv(HISTORY_PATH)
        frame = pd.concat([history, frame], ignore_index=True)
        frame = frame.drop_duplicates(subset=["as_of", "ticker"], keep="last")
    frame.to_csv(HISTORY_PATH, index=False)
    return frame


def evaluate_backtest(horizon_days: int = 30, signal_threshold_pct: float = 10.0) -> pd.DataFrame:
    if not HISTORY_PATH.exists():
        return pd.DataFrame()
    history = pd.read_csv(HISTORY_PATH)
    if history.empty:
        return history

    evaluations = []
    for _, row in history.iterrows():
        as_of_value = str(row.get("as_of", "")).strip()
        ticker = str(row.get("ticker", "")).strip()
        upside = row.get("upside_pct")
        if not as_of_value or not ticker or pd.isna(upside):
            continue
        try:
            as_of_dt = datetime.strptime(as_of_value, "%Y-%m-%d")
        except ValueError:
            continue
        target_date = as_of_dt + timedelta(days=horizon_days)
        if target_date.date() > date.today():
            continue

        current_price = row.get("current_price")
        future_price = fetch_price_near(ticker, target_date)
        if pd.isna(current_price) or current_price in (None, 0) or future_price is None:
            continue
        forward_return_pct = (future_price / float(current_price) - 1) * 100
        signal = float(upside) >= signal_threshold_pct
        evaluations.append(
            {
                "as_of": as_of_value,
                "ticker": ticker,
                "sector": row.get("sector", ""),
                "upside_pct": float(upside),
                "signal": signal,
                "current_price": float(current_price),
                "future_price": future_price,
                "forward_return_pct": forward_return_pct,
                "hit": bool(signal and forward_return_pct > 0),
            }
        )

    report = pd.DataFrame(evaluations)
    report.to_csv(BACKTEST_REPORT_PATH, index=False)
    return report


def print_backtest_summary(report: pd.DataFrame) -> None:
    if report.empty:
        print("Backtest için yeterli geçmiş veri yok.")
        return
    signaled = report[report["signal"] == True]  # noqa: E712
    hit_rate = (signaled["hit"].mean() * 100) if not signaled.empty else 0.0
    avg_signal_return = signaled["forward_return_pct"].mean() if not signaled.empty else 0.0
    avg_all_return = report["forward_return_pct"].mean()
    print(f"Kayıt: {len(report)}")
    print(f"Sinyal sayısı: {len(signaled)}")
    print(f"Hit rate: {hit_rate:.2f}%")
    print(f"Avg signal return: {avg_signal_return:.2f}%")
    print(f"Avg all return: {avg_all_return:.2f}%")


def main() -> None:
    tickers = load_tickers("coverage.txt")
    snapshot_valuations(tickers)
    report = evaluate_backtest(horizon_days=30, signal_threshold_pct=10.0)
    print(f"Kaydedildi -> {HISTORY_PATH}")
    print(f"Kaydedildi -> {BACKTEST_REPORT_PATH}")
    print_backtest_summary(report)


if __name__ == "__main__":
    main()
