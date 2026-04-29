from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
import re
from datetime import date
from typing import Any, Optional

import pandas as pd

from data.market_data_provider import FETCH_ERRORS, TickerBundle, fetch_ticker_bundle, normalized_info


ROW_OPERATING_INCOME = "Operating Income"
ROW_NET_INCOME = "Net Income"
ROW_OPERATING_CASH_FLOW = "Operating Cash Flow"
COL_OPERATING_INCOME = ROW_OPERATING_INCOME
COL_NET_INCOME = ROW_NET_INCOME
COL_OPERATING_CASH_FLOW = ROW_OPERATING_CASH_FLOW

OPERATING_INCOME_FIELDS = [ROW_OPERATING_INCOME, "Total Operating Income"]
TAX_FIELDS = ["Tax Provision", "Income Tax Expense"]
DEPRECIATION_FIELDS = ["Depreciation And Amortization", "Depreciation"]
CAPEX_FIELDS = ["Capital Expenditures"]
RECEIVABLE_FIELDS = ["Accounts Receivable", "Total Receivables"]
INVENTORY_FIELDS = ["Inventory", "Inventories"]
LIABILITY_FIELDS = ["Total Liabilities", "Total Liabilities Net Minority Interest"]
NET_INCOME_FIELDS = [ROW_NET_INCOME, "Net Income Applicable to Common Shares"]
TOTAL_ASSET_FIELDS = ["Total Assets"]
EQUITY_FIELDS = ["Common Stock Equity", "Stockholders Equity", "Total Equity Gross Minority Interest"]
TOTAL_DEBT_FIELDS = ["Total Debt", "Current Debt", "Long Term Debt", "Long Term Debt And Capital Lease Obligation"]
CURRENT_ASSET_FIELDS = ["Current Assets", "Total Current Assets"]
CURRENT_LIABILITY_FIELDS = ["Current Liabilities", "Total Current Liabilities"]
OPERATING_CASH_FLOW_FIELDS = [
    ROW_OPERATING_CASH_FLOW,
    "Total Cash From Operating Activities",
    "Cash Flow From Continuing Operating Activities",
]
PAID_IN_CAPITAL_FIELDS = ["Capital Stock", "Common Stock", "Share Issued", "Ordinary Shares Number"]
CASH_FIELDS = ["Cash And Cash Equivalents", "Cash And Cash Equivalents And Short Term Investments", "Cash"]

DCF_METRICS = [
    ("Net Faaliyet Kârı", OPERATING_INCOME_FIELDS),
    ("Vergi", TAX_FIELDS),
    ("Amortisman", DEPRECIATION_FIELDS),
    ("Sabit Sermaye", CAPEX_FIELDS),
    ("Toplam Alacak", RECEIVABLE_FIELDS),
    ("Stok", INVENTORY_FIELDS),
    ("Toplam Borç", LIABILITY_FIELDS),
]
DCF_CODE_COLUMN = "Kod"

FINANCIAL_COLUMNS = [
    "Symbol",
    "Name",
    "EBITDA",
    "ROE (%) Annual",
    "EV/EBITDA",
    "P/CF",
    "P/E",
    "EPS",
    "Forward EPS",
    "Forward P/E",
    "Analyst Target Mean",
    "Analyst Target Median",
    "Analyst Count",
    "Earnings Growth",
    "Revenue Growth",
    "Free Cash Flow",
    COL_OPERATING_CASH_FLOW,
    "P/B",
    "P/S",
    "Beta",
    "Asset Growth (%)",
    "Net Income Growth (Annual, %)",
    COL_NET_INCOME,
    COL_OPERATING_INCOME,
    "Shareholders' Equity",
    "Debt-to-Assets Ratio",
    "Paid-in Capital",
    "Net Working Capital",
    "Net Debt/EBITDA(Annual, %)",
]


def _safe_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def _round_or_none(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    return round(float(value), digits)


def _extract_year(column: Any) -> Optional[int]:
    year_attr = getattr(column, "year", None)
    if isinstance(year_attr, int):
        return year_attr
    if isinstance(column, int):
        return column if 1900 <= column <= 2100 else None
    text = str(column)
    match = re.search(r"(19|20)\d{2}", text)
    if not match:
        return None
    return int(match.group(0))


def _row_name(frame: pd.DataFrame, fields: list[str]) -> Optional[str]:
    for field in fields:
        if field in frame.index:
            return field
    return None


def _latest_value(frame: pd.DataFrame, fields: list[str]) -> Optional[float]:
    if frame.empty:
        return None
    row = _row_name(frame, fields)
    if row is None:
        return None
    series = frame.loc[row].dropna()
    if series.empty:
        return None
    return _safe_float(series.iloc[0])


def _previous_value(frame: pd.DataFrame, fields: list[str]) -> Optional[float]:
    if frame.empty:
        return None
    row = _row_name(frame, fields)
    if row is None:
        return None
    series = frame.loc[row].dropna()
    if series.shape[0] < 2:
        return None
    return _safe_float(series.iloc[1])


def _value_for_year(frame: pd.DataFrame, fields: list[str], year: int) -> Optional[float]:
    if frame.empty:
        return None
    row = _row_name(frame, fields)
    if row is None:
        return None
    for column in frame.columns:
        if _extract_year(column) != year:
            continue
        try:
            return _safe_float(frame.loc[row, column])
        except (KeyError, TypeError, ValueError):
            return None
    return None


def _pct_change(current: Optional[float], previous: Optional[float]) -> Optional[float]:
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1.0) * 100.0


def _ratio_pct(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or denominator in (None, 0):
        return None
    return (numerator / denominator) * 100.0


def _clean_ticker(ticker: str) -> str:
    return ticker[:-3] if ticker.upper().endswith(".IS") else ticker


def _compute_enterprise_to_ebitda(bundle: TickerBundle, ebitda: Optional[float]) -> Optional[float]:
    enterprise_to_ebitda = _safe_float(bundle.info.get("enterpriseToEbitda"))
    if enterprise_to_ebitda is not None:
        return enterprise_to_ebitda
    enterprise_value = _safe_float(bundle.info.get("enterpriseValue"))
    if enterprise_value is None or ebitda in (None, 0):
        return None
    return enterprise_value / ebitda


def _compute_price_to_cashflow(bundle: TickerBundle, info: dict[str, Optional[float]], annual_cashflow: pd.DataFrame) -> Optional[float]:
    p_cf = _safe_float(bundle.info.get("priceToCashflow"))
    if p_cf is not None:
        return p_cf
    operating_cash_flow = _latest_value(annual_cashflow, OPERATING_CASH_FLOW_FIELDS)
    market_cap = info.get("marketCap")
    if market_cap is None or operating_cash_flow in (None, 0):
        return None
    return market_cap / operating_cash_flow


def _compute_total_debt(annual_balance: pd.DataFrame) -> Optional[float]:
    total_debt = _latest_value(annual_balance, TOTAL_DEBT_FIELDS)
    if total_debt is not None:
        return total_debt
    return _latest_value(annual_balance, LIABILITY_FIELDS)


def _compute_net_working_capital(current_assets: Optional[float], current_liabilities: Optional[float]) -> Optional[float]:
    if current_assets is None or current_liabilities is None:
        return None
    return current_assets - current_liabilities


def _compute_net_debt_to_ebitda(total_debt: Optional[float], cash_like: Optional[float], ebitda: Optional[float]) -> Optional[float]:
    if total_debt is None or cash_like is None or ebitda in (None, 0):
        return None
    return ((total_debt - cash_like) / ebitda) * 100.0


def _compute_roe(
    info: dict[str, Optional[float]],
    net_income: Optional[float],
    shareholders_equity: Optional[float],
) -> Optional[float]:
    roe = _safe_float(info.get("returnOnEquity"))
    if roe is not None:
        return roe * 100.0
    if net_income is None or shareholders_equity in (None, 0):
        return None
    return (net_income / shareholders_equity) * 100.0


def _valid_share_count(candidate: Optional[float], implied_shares: Optional[float]) -> bool:
    if candidate is None or candidate <= 0:
        return False
    if implied_shares is None or implied_shares <= 0:
        return True
    ratio = candidate / implied_shares
    return 0.5 <= ratio <= 2.0


def compute_share_count(info: dict[str, Optional[float]], annual_balance: pd.DataFrame) -> Optional[float]:
    implied_shares = info.get("impliedShares")
    candidates = (
        info.get("sharesOutstanding"),
        info.get("floatShares"),
        _latest_value(annual_balance, PAID_IN_CAPITAL_FIELDS),
        implied_shares,
    )
    for candidate in candidates:
        if _valid_share_count(candidate, implied_shares):
            return candidate
    return implied_shares


def _extract_growth_metrics(
    annual_income: pd.DataFrame,
    annual_balance: pd.DataFrame,
) -> dict[str, Optional[float]]:
    total_assets = _latest_value(annual_balance, TOTAL_ASSET_FIELDS)
    prev_total_assets = _previous_value(annual_balance, TOTAL_ASSET_FIELDS)
    net_income = _latest_value(annual_income, NET_INCOME_FIELDS)
    prev_net_income = _previous_value(annual_income, NET_INCOME_FIELDS)
    return {
        "total_assets": total_assets,
        "asset_growth": _pct_change(total_assets, prev_total_assets),
        "net_income": net_income,
        "net_income_growth": _pct_change(net_income, prev_net_income),
        "operating_income": _latest_value(annual_income, OPERATING_INCOME_FIELDS),
    }


def _extract_balance_metrics(
    annual_balance: pd.DataFrame,
    info: dict[str, Optional[float]],
    ebitda: Optional[float],
    total_assets: Optional[float],
) -> dict[str, Optional[float]]:
    shareholders_equity = _latest_value(annual_balance, EQUITY_FIELDS)
    total_debt = _compute_total_debt(annual_balance)
    current_assets = _latest_value(annual_balance, CURRENT_ASSET_FIELDS)
    current_liabilities = _latest_value(annual_balance, CURRENT_LIABILITY_FIELDS)
    paid_in_capital = compute_share_count(info, annual_balance)
    cash_like = _latest_value(annual_balance, CASH_FIELDS)
    if cash_like is None:
        cash_like = info.get("totalCash")
    return {
        "shareholders_equity": shareholders_equity,
        "debt_to_assets_ratio": _ratio_pct(total_debt, total_assets),
        "paid_in_capital": paid_in_capital,
        "net_working_capital": _compute_net_working_capital(current_assets, current_liabilities),
        "net_debt_to_ebitda": _compute_net_debt_to_ebitda(total_debt, cash_like, ebitda),
    }


def _financials_row_from_bundle(ticker: str, bundle: TickerBundle) -> dict[str, Any]:
    info = normalized_info(bundle)

    annual_income = bundle.financials
    annual_balance = bundle.balance_sheet
    annual_cashflow = bundle.cashflow

    ebitda = info.get("ebitda")
    enterprise_to_ebitda = _compute_enterprise_to_ebitda(bundle, ebitda)
    p_cf = _compute_price_to_cashflow(bundle, info, annual_cashflow)
    growth_metrics = _extract_growth_metrics(annual_income, annual_balance)
    balance_metrics = _extract_balance_metrics(
        annual_balance=annual_balance,
        info=info,
        ebitda=ebitda,
        total_assets=growth_metrics["total_assets"],
    )
    roe = _compute_roe(
        info=info,
        net_income=growth_metrics["net_income"],
        shareholders_equity=balance_metrics["shareholders_equity"],
    )

    return {
        "Symbol": _clean_ticker(ticker),
        "Name": bundle.info.get("longName") or bundle.info.get("shortName") or "",
        "EBITDA": _round_or_none(ebitda),
        "ROE (%) Annual": _round_or_none(roe),
        "EV/EBITDA": _round_or_none(enterprise_to_ebitda),
        "P/CF": _round_or_none(p_cf),
        "P/E": _round_or_none(_safe_float(bundle.info.get("trailingPE"))),
        "EPS": _round_or_none(info.get("trailingEps")),
        "Forward EPS": _round_or_none(info.get("forwardEps")),
        "Forward P/E": _round_or_none(info.get("forwardPE")),
        "Analyst Target Mean": _round_or_none(info.get("targetMeanPrice")),
        "Analyst Target Median": _round_or_none(info.get("targetMedianPrice")),
        "Analyst Count": _round_or_none(info.get("numberOfAnalystOpinions"), 0),
        "Earnings Growth": _round_or_none(info.get("earningsGrowth")),
        "Revenue Growth": _round_or_none(info.get("revenueGrowth")),
        "Free Cash Flow": _round_or_none(info.get("freeCashflow")),
        COL_OPERATING_CASH_FLOW: _round_or_none(info.get("operatingCashflow")),
        "P/B": _round_or_none(info.get("priceToBook")),
        "P/S": _round_or_none(_safe_float(bundle.info.get("priceToSalesTrailing12Months"))),
        "Beta": _round_or_none(info.get("beta"), 3),
        "Asset Growth (%)": _round_or_none(growth_metrics["asset_growth"]),
        "Net Income Growth (Annual, %)": _round_or_none(growth_metrics["net_income_growth"]),
        COL_NET_INCOME: _round_or_none(growth_metrics["net_income"]),
        COL_OPERATING_INCOME: _round_or_none(growth_metrics["operating_income"]),
        "Shareholders' Equity": _round_or_none(balance_metrics["shareholders_equity"]),
        "Debt-to-Assets Ratio": _round_or_none(balance_metrics["debt_to_assets_ratio"]),
        "Paid-in Capital": _round_or_none(balance_metrics["paid_in_capital"]),
        "Net Working Capital": _round_or_none(balance_metrics["net_working_capital"]),
        "Net Debt/EBITDA(Annual, %)": _round_or_none(balance_metrics["net_debt_to_ebitda"]),
    }


def _expected_dcf_columns(years: list[int]) -> list[str]:
    columns = [DCF_CODE_COLUMN]
    for metric_name, _ in DCF_METRICS:
        for year in years:
            columns.append(f"{metric_name} {year}")
    return columns


def _dcf_row_from_bundle(ticker: str, bundle: TickerBundle, years: list[int]) -> dict[str, Any]:
    annual_income = bundle.financials
    annual_balance = bundle.balance_sheet
    annual_cashflow = bundle.cashflow

    row: dict[str, Any] = {DCF_CODE_COLUMN: _clean_ticker(ticker)}
    for year in years:
        row[f"Net Faaliyet Kârı {year}"] = _round_or_none(_value_for_year(annual_income, OPERATING_INCOME_FIELDS, year))
        row[f"Vergi {year}"] = _round_or_none(_value_for_year(annual_income, TAX_FIELDS, year))
        row[f"Amortisman {year}"] = _round_or_none(_value_for_year(annual_cashflow, DEPRECIATION_FIELDS, year))
        row[f"Sabit Sermaye {year}"] = _round_or_none(_value_for_year(annual_cashflow, CAPEX_FIELDS, year))
        row[f"Toplam Alacak {year}"] = _round_or_none(_value_for_year(annual_balance, RECEIVABLE_FIELDS, year))
        row[f"Stok {year}"] = _round_or_none(_value_for_year(annual_balance, INVENTORY_FIELDS, year))
        row[f"Toplam Borç {year}"] = _round_or_none(_value_for_year(annual_balance, LIABILITY_FIELDS, year))
    return row


def _build_rows_for_ticker(ticker: str, years: list[int]) -> tuple[dict[str, Any], dict[str, Any]]:
    bundle = fetch_ticker_bundle(ticker, include_last_close=False)
    return _financials_row_from_bundle(ticker, bundle), _dcf_row_from_bundle(ticker, bundle, years)


def _empty_rows_for_ticker(ticker: str, years: list[int]) -> tuple[dict[str, Any], dict[str, Any]]:
    dcf_row: dict[str, Any] = dict.fromkeys(_expected_dcf_columns(years))
    dcf_row[DCF_CODE_COLUMN] = _clean_ticker(ticker)
    return {"Symbol": _clean_ticker(ticker)}, dcf_row


def _build_rows_sequential(
    tickers: list[str],
    years: list[int],
    show_progress: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    financial_rows: list[dict[str, Any]] = [{} for _ in tickers]
    dcf_rows: list[dict[str, Any]] = [{} for _ in tickers]
    for index, ticker in enumerate(tickers):
        try:
            financial_row, dcf_row = _build_rows_for_ticker(ticker, years)
        except FETCH_ERRORS:
            financial_row, dcf_row = _empty_rows_for_ticker(ticker, years)
        financial_rows[index] = financial_row
        dcf_rows[index] = dcf_row
        if show_progress:
            print(f"DCF hazırlanıyor: {index + 1}/{len(tickers)}")
    return financial_rows, dcf_rows


def _build_rows_parallel(
    tickers: list[str],
    years: list[int],
    parallel_workers: int,
    show_progress: bool,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    financial_rows: list[dict[str, Any]] = [{} for _ in tickers]
    dcf_rows: list[dict[str, Any]] = [{} for _ in tickers]

    max_workers = max(1, min(parallel_workers, len(tickers)))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_build_rows_for_ticker, ticker, years): idx for idx, ticker in enumerate(tickers)}
        completed = 0
        for future in as_completed(futures):
            index = futures[future]
            ticker = tickers[index]
            try:
                financial_row, dcf_row = future.result()
            except FETCH_ERRORS:
                financial_row, dcf_row = _empty_rows_for_ticker(ticker, years)
            financial_rows[index] = financial_row
            dcf_rows[index] = dcf_row
            completed += 1
            if show_progress and (completed % 10 == 0 or completed == len(tickers)):
                print(f"DCF hazırlanıyor: {completed}/{len(tickers)}")
    return financial_rows, dcf_rows


def order_dcf_columns(frame: pd.DataFrame, years: list[int]) -> pd.DataFrame:
    ordered = _expected_dcf_columns(years)
    if frame.empty:
        return frame.reindex(columns=ordered)
    extras = [column for column in frame.columns if column not in ordered]
    return frame.reindex(columns=ordered + extras)


def build_financials_and_dcf_frames(
    tickers: list[str],
    end_year: Optional[int] = None,
    rolling_year_count: int = 6,
    parallel_workers: int = 8,
    show_progress: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    final_year = end_year if end_year is not None else date.today().year
    years = [final_year - offset for offset in range(rolling_year_count)]
    if not tickers:
        return pd.DataFrame(), pd.DataFrame()

    if parallel_workers <= 1 or len(tickers) == 1:
        financial_rows, dcf_rows = _build_rows_sequential(tickers, years, show_progress)
    else:
        financial_rows, dcf_rows = _build_rows_parallel(
            tickers=tickers,
            years=years,
            parallel_workers=parallel_workers,
            show_progress=show_progress,
        )

    financial_frame = pd.DataFrame(financial_rows)
    dcf_frame = pd.DataFrame(dcf_rows)
    if not financial_frame.empty:
        ordered = [column for column in FINANCIAL_COLUMNS if column in financial_frame.columns]
        ordered.extend(column for column in financial_frame.columns if column not in ordered)
        financial_frame = financial_frame[ordered]
    dcf_frame = order_dcf_columns(dcf_frame, years)
    return financial_frame, dcf_frame
