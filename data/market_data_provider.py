from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import pandas as pd
import yfinance as yf


FETCH_ERRORS = (RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError)


@dataclass
class TickerBundle:
    ticker: str
    info: Dict[str, Any]
    fast_info: Dict[str, Any]
    financials: pd.DataFrame
    balance_sheet: pd.DataFrame
    cashflow: pd.DataFrame
    last_close: Optional[float]
    warnings: list[str]


def safe_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def as_dataframe(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value
    return pd.DataFrame()


def get_last_close(stock: yf.Ticker) -> Optional[float]:
    try:
        history = stock.history(period="5d", interval="1d")
    except FETCH_ERRORS:
        return None
    if history is None:
        return None
    if not isinstance(history, pd.DataFrame):
        return None
    if history.empty:
        return None
    if "Close" not in history.columns:
        return None
    close_values = history["Close"].dropna()
    if close_values.empty:
        return None
    return safe_float(close_values.iloc[-1])


def fetch_ticker_bundle(ticker: str) -> TickerBundle:
    stock = yf.Ticker(ticker)
    warnings: list[str] = []

    try:
        info = stock.info
        info = info if isinstance(info, dict) else {}
    except FETCH_ERRORS:
        info = {}
        warnings.append("info_unavailable")

    try:
        fast_info_obj = stock.fast_info
        fast_info = dict(fast_info_obj) if fast_info_obj is not None else {}
    except FETCH_ERRORS:
        fast_info = {}
        warnings.append("fast_info_unavailable")

    try:
        financials = as_dataframe(stock.financials)
    except FETCH_ERRORS:
        financials = pd.DataFrame()
        warnings.append("financials_unavailable")

    try:
        balance_sheet = as_dataframe(stock.balance_sheet)
    except FETCH_ERRORS:
        balance_sheet = pd.DataFrame()
        warnings.append("balance_sheet_unavailable")

    try:
        cashflow = as_dataframe(stock.cashflow)
    except FETCH_ERRORS:
        cashflow = pd.DataFrame()
        warnings.append("cashflow_unavailable")

    last_close = get_last_close(stock)
    if last_close is None:
        warnings.append("last_close_unavailable")

    return TickerBundle(
        ticker=ticker,
        info=info,
        fast_info=fast_info,
        financials=financials,
        balance_sheet=balance_sheet,
        cashflow=cashflow,
        last_close=last_close,
        warnings=warnings,
    )


def coalesce_numeric(*values: Any) -> Optional[float]:
    for value in values:
        num = safe_float(value)
        if num is not None:
            return num
    return None


def normalized_info(bundle: TickerBundle) -> Dict[str, Optional[float]]:
    info = bundle.info
    fast = bundle.fast_info
    normalized = {
        "beta": coalesce_numeric(info.get("beta"), 1.0),
        "marketCap": coalesce_numeric(info.get("marketCap"), fast.get("marketCap")),
        "totalDebt": coalesce_numeric(info.get("totalDebt")),
        "interestRate": coalesce_numeric(info.get("interestRate")),
        "sharesOutstanding": coalesce_numeric(info.get("sharesOutstanding"), fast.get("shares")),
        "floatShares": coalesce_numeric(info.get("floatShares")),
        "totalCash": coalesce_numeric(info.get("totalCash")),
        "trailingEps": coalesce_numeric(info.get("trailingEps")),
        "dividendRate": coalesce_numeric(info.get("dividendRate"), 0.0),
        "ebitda": coalesce_numeric(info.get("ebitda")),
        "priceToBook": coalesce_numeric(info.get("priceToBook"), fast.get("priceToBook")),
        "bookValue": coalesce_numeric(info.get("bookValue")),
        "returnOnEquity": coalesce_numeric(info.get("returnOnEquity")),
        "currentPrice": coalesce_numeric(info.get("currentPrice"), fast.get("lastPrice"), bundle.last_close),
    }
    return normalized


def validate_bundle(bundle: TickerBundle, info: Dict[str, Optional[float]]) -> list[str]:
    warnings = list(bundle.warnings)
    if info.get("sharesOutstanding") is None and info.get("floatShares") is None:
        warnings.append("shares_missing")
    if info.get("marketCap") is None:
        warnings.append("market_cap_missing")
    if info.get("currentPrice") is None:
        warnings.append("price_missing")
    if info.get("trailingEps") is None:
        warnings.append("eps_missing")
    return warnings
