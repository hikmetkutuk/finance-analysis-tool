from typing import Any, Iterable, Optional, Tuple

from .constants import (
    CASH_KEYS,
    COLUMN_CASH_RATIO,
    COLUMN_CURRENT_RATIO,
    COLUMN_QUICK_RATIO,
    CURRENT_ASSET_KEYS,
    CURRENT_LIABILITY_KEYS,
    EQUITY_KEYS,
    INVENTORY_KEYS,
    LONG_DEBT_KEYS,
    SHORT_DEBT_KEYS,
    TOTAL_ASSETS_KEY,
    TOTAL_DEBT_KEYS,
)
from .dependencies import pd
from .profiles import MarketProfile


def _f(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().lower()


def is_financial_company(info: dict, profile: MarketProfile) -> bool:
    fields = [
        info.get("sector"),
        info.get("sectorKey"),
        info.get("industry"),
        info.get("industryKey"),
        info.get("quoteType"),
    ]
    text = " ".join(normalize_text(item) for item in fields if item)
    return any(term in text for term in profile.financial_terms)


def first_col(frame: Any) -> Optional[Any]:
    if frame is None or frame.empty:
        return None
    return frame.columns[0]


def latest_value(frame: Any, keys: Iterable[str]) -> Optional[float]:
    if frame is None or frame.empty:
        return None
    latest_col = first_col(frame)
    if latest_col is None:
        return None
    for key in keys:
        if key not in frame.index:
            continue
        try:
            value = frame.loc[key, latest_col]
            if pd.notna(value):
                return float(value)
        except (KeyError, TypeError, ValueError):
            continue
    return None


def latest_value_with_fallback(primary_frame: Any, secondary_frame: Any, keys: Iterable[str]) -> Optional[float]:
    value = latest_value(primary_frame, keys)
    if value is not None:
        return value
    return latest_value(secondary_frame, keys)


def latest_two_values(frame: Any, keys: Iterable[str]) -> Tuple[Optional[float], Optional[float]]:
    if frame is None or frame.empty:
        return None, None
    row_key = next((key for key in keys if key in frame.index), None)
    if row_key is None:
        return None, None
    series = frame.loc[row_key].dropna()
    if series.empty:
        return None, None
    current_value = _f(series.iloc[0])
    previous_value = _f(series.iloc[1]) if series.shape[0] > 1 else None
    return current_value, previous_value


def latest_two_values_with_fallback(
    primary_frame: Any,
    secondary_frame: Any,
    keys: Iterable[str],
) -> Tuple[Optional[float], Optional[float]]:
    current_value, previous_value = latest_two_values(primary_frame, keys)
    if current_value is not None:
        return current_value, previous_value
    return latest_two_values(secondary_frame, keys)


def series_ttm(frame: Any, row_name: str) -> Optional[float]:
    if frame is None or frame.empty or row_name not in frame.index:
        return None
    try:
        values = frame.loc[row_name].dropna().iloc[:4]
        return float(values.sum()) if not values.empty else None
    except (KeyError, TypeError, ValueError, IndexError):
        return None


def yoy_growth_from_annual(annual_frame: Any, row_name: str) -> Optional[float]:
    if annual_frame is None or annual_frame.empty or row_name not in annual_frame.index:
        return None
    series = annual_frame.loc[row_name].dropna()
    if series.shape[0] < 2:
        return None
    current_value = _f(series.iloc[0])
    previous_value = _f(series.iloc[1])
    if current_value is None or previous_value in (None, 0):
        return None
    return (current_value - previous_value) / previous_value * 100.0


def yoy_growth_from_quarterly(quarterly_frame: Any, row_name: str) -> Optional[float]:
    if quarterly_frame is None or quarterly_frame.empty or row_name not in quarterly_frame.index:
        return None
    series = quarterly_frame.loc[row_name].dropna()
    if series.shape[0] < 8:
        return None
    ttm_now = _f(series.iloc[:4].sum())
    ttm_prev = _f(series.iloc[4:8].sum())
    if ttm_now is None or ttm_prev in (None, 0):
        return None
    return (ttm_now - ttm_prev) / ttm_prev * 100.0


def yoy_growth_from_annual_or_quarterly(annual_frame: Any, quarterly_frame: Any, row_name: str) -> Optional[float]:
    annual_value = yoy_growth_from_annual(annual_frame, row_name)
    if annual_value is not None:
        return annual_value
    return yoy_growth_from_quarterly(quarterly_frame, row_name)


def build_liquidity_metrics(
    current_assets: Optional[float],
    current_liabilities: Optional[float],
    inventory: Optional[float],
    cash_like: Optional[float],
) -> dict:
    assets = _f(current_assets)
    liabilities = _f(current_liabilities)
    inventory_value = _f(inventory) if inventory is not None else 0.0
    cash_value = _f(cash_like)
    current_ratio = (assets / liabilities) if assets is not None and liabilities not in (None, 0) else None
    quick_ratio = ((assets - (inventory_value or 0.0)) / liabilities) if assets is not None and liabilities not in (None, 0) else None
    cash_ratio = (cash_value / liabilities) if cash_value is not None and liabilities not in (None, 0) else None
    return {
        COLUMN_CURRENT_RATIO: current_ratio,
        COLUMN_QUICK_RATIO: quick_ratio,
        COLUMN_CASH_RATIO: cash_ratio,
    }


def calculate_roe(
    quarterly_financials: Any,
    info: dict,
    equity_current: Optional[float],
    equity_previous: Optional[float],
) -> Optional[float]:
    ttm_net_income = series_ttm(quarterly_financials, "Net Income")
    if ttm_net_income is None:
        trailing_eps = _f(info.get("trailingEps"))
        shares_outstanding = _f(info.get("sharesOutstanding"))
        if trailing_eps is not None and shares_outstanding is not None:
            ttm_net_income = trailing_eps * shares_outstanding
    net_income_value = _f(ttm_net_income)
    current_equity = _f(equity_current)
    previous_equity = _f(equity_previous)
    if net_income_value is None or current_equity in (None, 0):
        return None
    avg_equity = current_equity
    if previous_equity not in (None, 0):
        avg_equity = (current_equity + previous_equity) / 2.0
    if avg_equity == 0:
        return None
    return (net_income_value / avg_equity) * 100.0


def calculate_peg(info: dict) -> Optional[float]:
    pe_ratio = _f(info.get("trailingPE"))
    growth = _f(info.get("earningsGrowth"))
    if pe_ratio in (None, 0) or growth is None:
        return None
    growth_pct = growth * 100.0 if growth < 1 else growth
    if growth_pct == 0:
        return None
    return pe_ratio / growth_pct


def normalize_tax_rate(rate: Optional[float], default_tax_rate: float) -> float:
    if rate is None:
        return default_tax_rate
    return min(max(rate, 0.0), 1.0)


def read_total_debt_from_frame(balance_sheet: Any) -> Optional[float]:
    total_debt = latest_value(balance_sheet, TOTAL_DEBT_KEYS)
    if total_debt is not None:
        return total_debt
    short_debt = latest_value(balance_sheet, SHORT_DEBT_KEYS) or 0.0
    long_debt = latest_value(balance_sheet, LONG_DEBT_KEYS) or 0.0
    return (short_debt or 0.0) + (long_debt or 0.0)


def get_total_debt(quarterly_balance_sheet: Any, annual_balance_sheet: Any) -> Optional[float]:
    debt = read_total_debt_from_frame(quarterly_balance_sheet)
    if debt is not None:
        return debt
    return read_total_debt_from_frame(annual_balance_sheet)


def get_avg_assets(quarterly_balance_sheet: Any, annual_balance_sheet: Any) -> Optional[float]:
    if quarterly_balance_sheet is not None and not quarterly_balance_sheet.empty and TOTAL_ASSETS_KEY in quarterly_balance_sheet.index:
        values = quarterly_balance_sheet.loc[TOTAL_ASSETS_KEY].dropna()
        if values.shape[0] >= 2:
            return (float(values.iloc[0]) + float(values.iloc[1])) / 2.0
        if values.shape[0] >= 1:
            return float(values.iloc[0])
    return latest_value(annual_balance_sheet, [TOTAL_ASSETS_KEY])


def calculate_roic(
    info: dict,
    quarterly_financials: Any,
    quarterly_balance_sheet: Any,
    annual_balance_sheet: Any,
    equity_current: Optional[float],
    cash_like: Optional[float],
    default_tax_rate: float,
) -> Optional[float]:
    operating_income_ttm = series_ttm(quarterly_financials, "Operating Income")
    tax_rate = normalize_tax_rate(_f(info.get("effectiveTaxRate")), default_tax_rate)
    operating_income_value = _f(operating_income_ttm)
    if operating_income_value is None:
        return None
    nopat = operating_income_value * (1.0 - tax_rate)
    total_debt = get_total_debt(quarterly_balance_sheet, annual_balance_sheet)
    debt_value = _f(total_debt)
    equity_value = _f(equity_current)
    cash_value = _f(cash_like)
    invested_capital = (debt_value or 0.0) + (equity_value or 0.0) - (cash_value or 0.0)
    if nopat is None or invested_capital == 0:
        return None
    return nopat / invested_capital * 100.0


def calculate_asset_turnover(
    quarterly_financials: Any,
    quarterly_balance_sheet: Any,
    annual_balance_sheet: Any,
) -> Optional[float]:
    revenue_ttm = series_ttm(quarterly_financials, "Total Revenue") or series_ttm(quarterly_financials, "Revenue")
    avg_assets = get_avg_assets(quarterly_balance_sheet, annual_balance_sheet)
    revenue_value = _f(revenue_ttm)
    avg_assets_value = _f(avg_assets)
    if revenue_value is None or avg_assets_value in (None, 0):
        return None
    return revenue_value / avg_assets_value


def extract_balance_sheet_values(
    quarterly_balance_sheet: Any,
    annual_balance_sheet: Any,
) -> Tuple[Optional[float], Optional[float], Optional[float], Optional[float], Optional[float], Optional[float]]:
    current_assets = latest_value_with_fallback(quarterly_balance_sheet, annual_balance_sheet, CURRENT_ASSET_KEYS)
    current_liabilities = latest_value_with_fallback(quarterly_balance_sheet, annual_balance_sheet, CURRENT_LIABILITY_KEYS)
    inventory = latest_value_with_fallback(quarterly_balance_sheet, annual_balance_sheet, INVENTORY_KEYS)
    cash_like = latest_value_with_fallback(quarterly_balance_sheet, annual_balance_sheet, CASH_KEYS)
    equity_current, equity_previous = latest_two_values_with_fallback(quarterly_balance_sheet, annual_balance_sheet, EQUITY_KEYS)
    return current_assets, current_liabilities, inventory, cash_like, equity_current, equity_previous
