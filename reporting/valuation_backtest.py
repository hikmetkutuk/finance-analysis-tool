from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

import pandas as pd
import yfinance as yf

from data.market_data_provider import fetch_ticker_bundle, normalized_info
from valuation import AVERAGE_FAIR_PRICE_LABEL, load_tickers, value_ticker


HISTORY_PATH = Path("valuation_history.csv")
BACKTEST_REPORT_PATH = Path("valuation_backtest_report.csv")
CALIBRATION_REPORT_PATH = Path("valuation_calibration_report.csv")


@dataclass
class SnapshotRow:
    as_of: str
    ticker: str
    market: str
    sector: str
    fair_value: Optional[float]
    current_price: Optional[float]
    upside_pct: Optional[float]
    confidence: Optional[float]
    ratio_score: Optional[float]
    status: str
    warnings: str


def parse_tr_formatted_number(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.replace(".", "").replace(",", ".")
    try:
        return float(normalized)
    except (TypeError, ValueError):
        return None


def text_value(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


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


def infer_market(ticker: str) -> str:
    return "tr" if ticker.upper().endswith(".IS") else "us"


def signal_bucket(upside_pct: float) -> str:
    if upside_pct < 0:
        return "negative"
    if upside_pct < 10:
        return "0_10"
    if upside_pct < 20:
        return "10_20"
    if upside_pct < 35:
        return "20_35"
    return "35_plus"


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
        market=infer_market(ticker),
        sector=text_value(result.get("Sektör")),
        fair_value=fair_value,
        current_price=current_price,
        upside_pct=upside_pct,
        confidence=parse_tr_formatted_number(result.get("Güven")),
        ratio_score=parse_tr_formatted_number(result.get("Rasyo")),
        status=text_value(result.get("Sonuç Durumu")),
        warnings=text_value(result.get("Model Kalite Uyarıları")),
    )


def snapshot_valuations(tickers: list[str], as_of: Optional[str] = None) -> pd.DataFrame:
    resolved_as_of = as_of if as_of is not None else date.today().isoformat()
    rows = [build_snapshot_row(ticker, resolved_as_of) for ticker in tickers]
    frame = pd.DataFrame([row.__dict__ for row in rows])
    if HISTORY_PATH.exists():
        history = pd.read_csv(HISTORY_PATH)
        frame = pd.concat([history, frame], ignore_index=True)
        frame = frame.drop_duplicates(subset=["as_of", "ticker"], keep="last")
    frame.to_csv(HISTORY_PATH, index=False)
    return frame


def build_calibration_report(report: pd.DataFrame) -> pd.DataFrame:
    if report.empty:
        return pd.DataFrame()
    enriched = report.copy()
    enriched["signal_bucket"] = enriched["upside_pct"].apply(signal_bucket)
    grouped_rows: list[dict[str, Any]] = []
    group_columns = ["market", "sector", "signal_bucket"]
    for keys, group in enriched.groupby(group_columns, dropna=False):
        market, sector, bucket = keys
        signals = group[group["signal"] == True]  # noqa: E712
        grouped_rows.append(
            {
                "market": market,
                "sector": sector,
                "signal_bucket": bucket,
                "rows": len(group),
                "signals": int(group["signal"].sum()),
                "hit_rate_pct": round((signals["hit"].mean() * 100.0), 2) if not signals.empty else None,
                "avg_signal_return_pct": round(float(signals["forward_return_pct"].mean()), 2) if not signals.empty else None,
                "avg_all_return_pct": round(float(group["forward_return_pct"].mean()), 2),
                "median_return_pct": round(float(group["forward_return_pct"].median()), 2),
            }
        )
    calibration = pd.DataFrame(grouped_rows)
    calibration = calibration.sort_values(by=["market", "sector", "signal_bucket"], kind="stable").reset_index(drop=True)
    calibration.to_csv(CALIBRATION_REPORT_PATH, index=False)
    return calibration


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
                "market": row.get("market", infer_market(ticker)),
                "sector": row.get("sector", ""),
                "upside_pct": float(upside),
                "signal": signal,
                "current_price": float(current_price),
                "future_price": future_price,
                "forward_return_pct": forward_return_pct,
                "confidence": row.get("confidence"),
                "ratio_score": row.get("ratio_score"),
                "status": row.get("status", ""),
                "hit": bool(signal and forward_return_pct > 0),
            }
        )

    report = pd.DataFrame(evaluations)
    report.to_csv(BACKTEST_REPORT_PATH, index=False)
    build_calibration_report(report)
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
    if "market" in report.columns:
        for market, market_group in report.groupby("market", dropna=False):
            market_signals = market_group[market_group["signal"] == True]  # noqa: E712
            market_hit_rate = (market_signals["hit"].mean() * 100.0) if not market_signals.empty else 0.0
            market_avg_return = market_group["forward_return_pct"].mean()
            print(f"{market} avg return: {market_avg_return:.2f}% | hit rate: {market_hit_rate:.2f}%")


def main() -> None:
    tickers = load_tickers("coverage.txt")
    snapshot_valuations(tickers)
    report = evaluate_backtest(horizon_days=30, signal_threshold_pct=10.0)
    print(f"Kaydedildi -> {HISTORY_PATH}")
    print(f"Kaydedildi -> {BACKTEST_REPORT_PATH}")
    if CALIBRATION_REPORT_PATH.exists():
        print(f"Kaydedildi -> {CALIBRATION_REPORT_PATH}")
    print_backtest_summary(report)


if __name__ == "__main__":
    main()
