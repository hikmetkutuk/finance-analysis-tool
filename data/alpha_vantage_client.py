from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any, Optional
from urllib.parse import urlencode
from urllib.request import urlopen

import pandas as pd


ALPHA_VANTAGE_API_KEY_ENV = "ALPHAVANTAGE_API_KEY"
ALPHA_VANTAGE_BASE_URL = "https://www.alphavantage.co/query"
ALPHA_VANTAGE_TIMEOUT_SECONDS = 15
BALANCE_ROW_CURRENT_DEBT = "Current Debt"
BALANCE_ROW_LONG_TERM_DEBT = "Long Term Debt"

INCOME_FIELD_MAP = {
    "totalRevenue": "Total Revenue",
    "operatingIncome": "Operating Income",
    "netIncome": "Net Income",
}

BALANCE_FIELD_MAP = {
    "totalAssets": "Total Assets",
    "cashAndCashEquivalentsAtCarryingValue": "Cash And Cash Equivalents",
    "cashAndShortTermInvestments": "Cash And Cash Equivalents And Short Term Investments",
    "currentNetReceivables": "Accounts Receivable",
    "inventory": "Inventory",
    "totalCurrentAssets": "Total Current Assets",
    "totalCurrentLiabilities": "Total Current Liabilities",
    "shortTermDebt": BALANCE_ROW_CURRENT_DEBT,
    "currentLongTermDebt": "Current Debt And Capital Lease Obligation",
    "longTermDebt": BALANCE_ROW_LONG_TERM_DEBT,
    "totalLiabilities": "Total Liabilities",
    "totalShareholderEquity": "Stockholders Equity",
    "commonStockSharesOutstanding": "Ordinary Shares Number",
}

CASHFLOW_FIELD_MAP = {
    "operatingCashflow": "Operating Cash Flow",
    "capitalExpenditures": "Capital Expenditures",
    "depreciationDepletionAndAmortization": "Depreciation And Amortization",
}


@dataclass(frozen=True)
class AlphaVantageDataset:
    info: dict[str, Any]
    annual_income: pd.DataFrame
    quarterly_income: pd.DataFrame
    annual_balance: pd.DataFrame
    quarterly_balance: pd.DataFrame
    annual_cashflow: pd.DataFrame
    quarterly_cashflow: pd.DataFrame
    last_close: Optional[float]
    warnings: list[str]


def _safe_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _safe_ratio(value: Any) -> Optional[float]:
    number = _safe_float(value)
    if number is None:
        return None
    return number / 100.0 if abs(number) > 1.5 else number


def _api_key() -> Optional[str]:
    raw = os.getenv(ALPHA_VANTAGE_API_KEY_ENV, "").strip()
    return raw or None


def alpha_vantage_enabled() -> bool:
    return _api_key() is not None


def _fetch_json(function_name: str, symbol: str, api_key: str) -> dict[str, Any]:
    query = urlencode({"function": function_name, "symbol": symbol, "apikey": api_key})
    url = f"{ALPHA_VANTAGE_BASE_URL}?{query}"
    try:
        with urlopen(url, timeout=ALPHA_VANTAGE_TIMEOUT_SECONDS) as response:
            raw = response.read().decode("utf-8")
    except OSError as error:
        raise OSError(f"alpha_vantage_request_failed:{function_name}") from error
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError as error:
        raise ValueError(f"alpha_vantage_invalid_json:{function_name}") from error
    if not isinstance(payload, dict):
        raise ValueError(f"alpha_vantage_invalid_payload:{function_name}")
    if payload.get("Error Message"):
        raise ValueError(f"alpha_vantage_error:{function_name}")
    if payload.get("Note") or payload.get("Information"):
        raise RuntimeError(f"alpha_vantage_throttled:{function_name}")
    return payload


def _coerce_value(value: Any) -> Any:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped or stripped == "None":
            return None
        numeric = _safe_float(stripped)
        return numeric if numeric is not None else stripped
    return value


def _frame_from_reports(reports: Any, field_map: dict[str, str]) -> pd.DataFrame:
    if not isinstance(reports, list) or not reports:
        return pd.DataFrame()
    normalized_rows: list[dict[str, Any]] = []
    for row in reports:
        if not isinstance(row, dict):
            continue
        fiscal_date = row.get("fiscalDateEnding")
        if not isinstance(fiscal_date, str) or not fiscal_date.strip():
            continue
        normalized = {"fiscalDateEnding": pd.Timestamp(fiscal_date)}
        for raw_key, label in field_map.items():
            normalized[label] = _coerce_value(row.get(raw_key))
        normalized_rows.append(normalized)
    if not normalized_rows:
        return pd.DataFrame()
    frame = pd.DataFrame(normalized_rows).set_index("fiscalDateEnding").T
    frame = frame.reindex(sorted(frame.columns, reverse=True), axis=1)
    return frame


def _latest_balance_value(frame: pd.DataFrame, row_name: str) -> Optional[float]:
    if not isinstance(frame, pd.DataFrame) or frame.empty or row_name not in frame.index:
        return None
    series = frame.loc[row_name]
    if isinstance(series, pd.Series):
        series = series.dropna()
        if series.empty:
            return None
        return _safe_float(series.iloc[0])
    return None


def _overview_to_info(overview: dict[str, Any], balance_sheet: pd.DataFrame, global_quote: dict[str, Any]) -> dict[str, Any]:
    current_price = _safe_float(global_quote.get("05. price"))
    total_debt = _latest_balance_value(balance_sheet, BALANCE_ROW_CURRENT_DEBT)
    if total_debt is None:
        total_debt = _latest_balance_value(balance_sheet, BALANCE_ROW_LONG_TERM_DEBT)
    long_term_debt = _latest_balance_value(balance_sheet, BALANCE_ROW_LONG_TERM_DEBT)
    current_debt = _latest_balance_value(balance_sheet, BALANCE_ROW_CURRENT_DEBT)
    total_debt = sum(value for value in (current_debt, long_term_debt) if value is not None) or total_debt
    return {
        "beta": _safe_float(overview.get("Beta")),
        "marketCap": _safe_float(overview.get("MarketCapitalization")),
        "totalDebt": total_debt,
        "sharesOutstanding": _safe_float(overview.get("SharesOutstanding")),
        "trailingEps": _safe_float(overview.get("EPS")),
        "forwardEps": _safe_float(overview.get("DilutedEPSTTM")),
        "trailingPE": _safe_float(overview.get("PERatio")),
        "forwardPE": _safe_float(overview.get("ForwardPE")),
        "earningsGrowth": _safe_ratio(overview.get("QuarterlyEarningsGrowthYOY")),
        "revenueGrowth": _safe_ratio(overview.get("QuarterlyRevenueGrowthYOY")),
        "dividendRate": _safe_float(overview.get("DividendPerShare")),
        "ebitda": _safe_float(overview.get("EBITDA")),
        "bookValue": _safe_float(overview.get("BookValue")),
        "priceToBook": _safe_float(overview.get("PriceToBookRatio")),
        "returnOnEquity": _safe_ratio(overview.get("ReturnOnEquityTTM")),
        "currentPrice": current_price,
        "longName": overview.get("Name"),
        "sector": overview.get("Sector"),
        "industry": overview.get("Industry"),
        "currency": overview.get("Currency"),
        "exchange": overview.get("Exchange"),
    }


def fetch_alpha_vantage_dataset(symbol: str) -> Optional[AlphaVantageDataset]:
    api_key = _api_key()
    if api_key is None:
        return None
    overview = _fetch_json("OVERVIEW", symbol, api_key)
    income_payload = _fetch_json("INCOME_STATEMENT", symbol, api_key)
    balance_payload = _fetch_json("BALANCE_SHEET", symbol, api_key)
    cashflow_payload = _fetch_json("CASH_FLOW", symbol, api_key)
    quote_payload = _fetch_json("GLOBAL_QUOTE", symbol, api_key)
    global_quote = quote_payload.get("Global Quote", {}) if isinstance(quote_payload.get("Global Quote"), dict) else {}

    annual_income = _frame_from_reports(income_payload.get("annualReports"), INCOME_FIELD_MAP)
    quarterly_income = _frame_from_reports(income_payload.get("quarterlyReports"), INCOME_FIELD_MAP)
    annual_balance = _frame_from_reports(balance_payload.get("annualReports"), BALANCE_FIELD_MAP)
    quarterly_balance = _frame_from_reports(balance_payload.get("quarterlyReports"), BALANCE_FIELD_MAP)
    annual_cashflow = _frame_from_reports(cashflow_payload.get("annualReports"), CASHFLOW_FIELD_MAP)
    quarterly_cashflow = _frame_from_reports(cashflow_payload.get("quarterlyReports"), CASHFLOW_FIELD_MAP)

    info = _overview_to_info(overview, annual_balance, global_quote)
    warnings: list[str] = []
    if not info:
        warnings.append("alpha_vantage_info_unavailable")
    if annual_income.empty:
        warnings.append("alpha_vantage_income_unavailable")
    if annual_balance.empty:
        warnings.append("alpha_vantage_balance_unavailable")
    if annual_cashflow.empty:
        warnings.append("alpha_vantage_cashflow_unavailable")

    return AlphaVantageDataset(
        info=info,
        annual_income=annual_income,
        quarterly_income=quarterly_income,
        annual_balance=annual_balance,
        quarterly_balance=quarterly_balance,
        annual_cashflow=annual_cashflow,
        quarterly_cashflow=quarterly_cashflow,
        last_close=_safe_float(global_quote.get("05. price")),
        warnings=warnings,
    )
