# -*- coding: utf-8 -*-

from __future__ import annotations

import time
from typing import Any, Dict, Optional, Tuple

import pandas as pd

from macro_config import load_macro_config
from market_data_provider import fetch_ticker_bundle, normalized_info, validate_bundle
from sector import TR_PROFILE, US_PROFILE, build_sector_maps
from sector_override_builder import load_sector_overrides


YEARS_PROJECTION = 5
MAX_GROWTH_CAP = 0.50
MIN_GROWTH_CAP = -0.50
EPSILON = 1e-9

NUMBER_FORMAT = "{:,.2f}"
AVERAGE_FAIR_PRICE_LABEL = "Ortalama Adil Fiyat"

OPERATING_INCOME_FIELDS = ["Operating Income", "Total Operating Income"]
TAX_FIELDS = ["Tax Provision", "Income Tax Expense"]
DEPRECIATION_FIELDS = ["Depreciation And Amortization", "Depreciation"]
CAPEX_FIELDS = ["Capital Expenditures"]
RECEIVABLE_FIELDS = ["Accounts Receivable", "Total Receivables"]
INVENTORY_FIELDS = ["Inventory", "Inventories"]
LIABILITY_FIELDS = ["Total Liabilities", "Total Liabilities Net Minority Interest"]
NET_INCOME_FIELDS = ["Net Income", "Net Income Applicable to Common Shares"]

TICKER_PROCESSING_ERRORS = (
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
    OSError,
    RuntimeError,
    ZeroDivisionError,
)

MACRO_CONFIG = load_macro_config()
SECTOR_OVERRIDES = load_sector_overrides()
TR_SECTOR_MAP, US_SECTOR_MAP = build_sector_maps(auto_classify=False)


def build_sector_lookup(sector_map: Dict[str, list[str]]) -> Dict[str, str]:
    lookup: Dict[str, str] = {}
    for sector_name, tickers in sector_map.items():
        for ticker in tickers:
            lookup[ticker] = sector_name
    return lookup


TR_LOOKUP = build_sector_lookup(TR_SECTOR_MAP)
US_LOOKUP = build_sector_lookup(US_SECTOR_MAP)


def safe_div(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    try:
        if numerator is None or is_near_zero(denominator):
            return None
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def safe_float(value: Any) -> Optional[float]:
    if isinstance(value, pd.DataFrame):
        stacked = value.stack(dropna=True)
        if stacked.empty:
            return None
        value = stacked.iloc[0]
    elif isinstance(value, pd.Series):
        non_na = value.dropna()
        if non_na.empty:
            return None
        value = non_na.iloc[0]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def is_near_zero(value: Optional[float], epsilon: float = EPSILON) -> bool:
    if value is None:
        return True
    try:
        return abs(float(value)) <= epsilon
    except (TypeError, ValueError):
        return True


def has_nonzero_value(value: Optional[float], epsilon: float = EPSILON) -> bool:
    return not is_near_zero(value, epsilon)


def format_number_tr(value: Optional[float]) -> str:
    if value is None:
        return ""
    try:
        return NUMBER_FORMAT.format(float(value)).replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def format_percent_tr(value: Optional[float]) -> str:
    if value is None:
        return ""
    try:
        return f"{value * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def get_currency_symbol(ticker_code: str) -> str:
    return "₺" if ticker_code.upper().endswith(".IS") else "$"


def clean_ticker(ticker_code: str) -> str:
    return ticker_code.replace(".IS", "") if ticker_code.upper().endswith(".IS") else ticker_code


def is_turkish_ticker(ticker: str) -> bool:
    return ticker.upper().endswith(".IS")


def resolve_sector(ticker: str) -> Tuple[str, bool]:
    if is_turkish_ticker(ticker):
        sector_name = TR_LOOKUP.get(ticker, TR_PROFILE.other_label)
        return sector_name, sector_name in TR_PROFILE.financial_sectors
    sector_name = US_LOOKUP.get(ticker, US_PROFILE.other_label)
    return sector_name, sector_name in US_PROFILE.financial_sectors


def compute_avg_growth(series: list[Optional[float]]) -> float:
    values = [item for item in series if item is not None]
    if len(values) < 2:
        return 0.05
    growths: list[float] = []
    for index in range(1, len(values)):
        previous = values[index - 1]
        current = values[index]
        if is_near_zero(previous):
            continue
        growth = current / previous - 1
        growth = max(min(growth, MAX_GROWTH_CAP), MIN_GROWTH_CAP)
        growths.append(growth)
    return sum(growths) / len(growths) if growths else 0.05


def get_country_params(ticker: str) -> Dict[str, float]:
    market_key = "tr" if is_turkish_ticker(ticker) else "us"
    market_config = MACRO_CONFIG[market_key]
    defaults = market_config["defaults"]
    override = SECTOR_OVERRIDES.get(ticker, {})
    return {
        "market_key": market_key,
        "risk_free_rate": float(market_config["risk_free_rate"]),
        "market_premium": float(market_config["market_premium"]),
        "cost_of_debt": float(market_config["cost_of_debt"]),
        "tax_rate": float(market_config["tax_rate"]),
        "terminal_growth": float(market_config["terminal_growth"]),
        "ddm_growth": float(market_config["ddm_growth"]),
        "bond_yield_2": float(market_config["bond_yield_2"]),
        "pe": float(override.get("pe", defaults["pe"])),
        "pb": float(override.get("pb", defaults["pb"])),
        "ev_ebitda": float(override.get("ev_ebitda", defaults["ev_ebitda"])),
    }


def calculate_wacc(info: Dict[str, Optional[float]], params: Dict[str, float]) -> float:
    beta = info.get("beta") or 1.0
    equity = info.get("marketCap") or 0.0
    debt = info.get("totalDebt") or 0.0
    total_capital = equity + debt if (equity + debt) > 0 else 1

    cost_of_equity = params["risk_free_rate"] + beta * params["market_premium"]
    cost_of_debt = info.get("interestRate") or params["cost_of_debt"]
    tax_rate = params["tax_rate"]
    return (equity / total_capital) * cost_of_equity + (debt / total_capital) * cost_of_debt * (1 - tax_rate)


def _is_dataframe(frame: Any) -> bool:
    return isinstance(frame, pd.DataFrame) and not frame.empty


def _annual_value_for_year(frame: pd.DataFrame, row_names: list[str], target_year: int) -> Optional[float]:
    if not _is_dataframe(frame):
        return None
    row_name = next((candidate for candidate in row_names if candidate in frame.index), None)
    if row_name is None:
        return None
    for column in frame.columns:
        if getattr(column, "year", None) == target_year:
            value = frame.loc[row_name, column]
            return extract_numeric_scalar(value)
    return None


def extract_numeric_scalar(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, pd.DataFrame):
        stacked = value.stack(dropna=True)
        if stacked.empty:
            return None
        return safe_float(stacked.iloc[0])
    if isinstance(value, pd.Series):
        non_na = value.dropna()
        if non_na.empty:
            return None
        return safe_float(non_na.iloc[0])
    return safe_float(value)


def get_ebitda_safely(info: Dict[str, Optional[float]], income_stmt: pd.DataFrame, cash_flow: pd.DataFrame, year_hint: int = 2024) -> Optional[float]:
    ebitda = info.get("ebitda")
    if has_nonzero_value(ebitda):
        return float(ebitda)
    operating_income = _annual_value_for_year(income_stmt, OPERATING_INCOME_FIELDS, year_hint) or 0
    depreciation = _annual_value_for_year(cash_flow, DEPRECIATION_FIELDS, year_hint) or 0
    derived_ebitda = operating_income + depreciation
    if derived_ebitda > 1e12:
        derived_ebitda /= 1_000_000
    return float(derived_ebitda) if derived_ebitda else None


def calculate_fcf(
    operating_income: Optional[float],
    tax: Optional[float],
    depreciation: Optional[float],
    capex: Optional[float],
    receivable: Optional[float],
    inventory: Optional[float],
    liability: Optional[float],
    prev_receivable: Optional[float],
    prev_inventory: Optional[float],
    prev_liability: Optional[float],
    tax_rate_fallback: float,
) -> Optional[float]:
    operating_income_value = safe_float(operating_income)
    tax_value = safe_float(tax)
    depreciation_value = safe_float(depreciation)
    capex_value = safe_float(capex)
    receivable_value = safe_float(receivable)
    inventory_value = safe_float(inventory)
    liability_value = safe_float(liability)
    prev_receivable_value = safe_float(prev_receivable)
    prev_inventory_value = safe_float(prev_inventory)
    prev_liability_value = safe_float(prev_liability)

    if operating_income_value is None or is_near_zero(operating_income_value):
        return None
    effective_tax = (
        abs(tax_value / operating_income_value)
        if tax_value is not None and has_nonzero_value(operating_income_value)
        else tax_rate_fallback
    )
    nopat = operating_income_value * (1 - effective_tax)
    delta_working_capital = (
        (receivable_value or 0) + (inventory_value or 0) - (liability_value or 0)
    ) - (
        (prev_receivable_value or 0) + (prev_inventory_value or 0) - (prev_liability_value or 0)
    )
    return nopat + (depreciation_value or 0) - (capex_value or 0) - delta_working_capital


def build_fcf_by_year(income_stmt: pd.DataFrame, balance_sheet: pd.DataFrame, cash_flow: pd.DataFrame, tax_rate: float) -> Dict[int, Optional[float]]:
    fcf_by_year: Dict[int, Optional[float]] = {}
    for year in range(2021, 2026):
        fcf_by_year[year] = calculate_fcf(
            _annual_value_for_year(income_stmt, OPERATING_INCOME_FIELDS, year),
            _annual_value_for_year(income_stmt, TAX_FIELDS, year),
            _annual_value_for_year(cash_flow, DEPRECIATION_FIELDS, year),
            _annual_value_for_year(cash_flow, CAPEX_FIELDS, year),
            _annual_value_for_year(balance_sheet, RECEIVABLE_FIELDS, year),
            _annual_value_for_year(balance_sheet, INVENTORY_FIELDS, year),
            _annual_value_for_year(balance_sheet, LIABILITY_FIELDS, year),
            _annual_value_for_year(balance_sheet, RECEIVABLE_FIELDS, year - 1),
            _annual_value_for_year(balance_sheet, INVENTORY_FIELDS, year - 1),
            _annual_value_for_year(balance_sheet, LIABILITY_FIELDS, year - 1),
            tax_rate_fallback=tax_rate,
        )
    return fcf_by_year


def clamp_growth(avg_growth: float, wacc: float) -> float:
    if avg_growth < wacc:
        return avg_growth
    clamped_growth = wacc - 0.01
    return max(min(clamped_growth, MAX_GROWTH_CAP), MIN_GROWTH_CAP)


def calculate_dcf_fair_value(
    fcf_by_year: Dict[int, Optional[float]],
    avg_growth: float,
    wacc: float,
    debt: float,
    cash: float,
    shares: float,
    terminal_growth: float,
) -> Optional[float]:
    past_fcfs = [value for value in fcf_by_year.values() if value is not None]
    if not past_fcfs:
        return None
    last_fcf = past_fcfs[-1]
    projected_fcfs = [last_fcf * ((1 + avg_growth) ** year) for year in range(1, YEARS_PROJECTION + 1)]
    discounted_fcfs = [fcf / ((1 + wacc) ** (year + 1)) for year, fcf in enumerate(projected_fcfs)]

    present_terminal_value = 0.0
    if projected_fcfs and wacc > terminal_growth:
        present_terminal_value = (
            projected_fcfs[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
        ) / ((1 + wacc) ** YEARS_PROJECTION)

    enterprise_value = sum(discounted_fcfs) + present_terminal_value
    return safe_div(enterprise_value - debt + cash, shares)


def calculate_fk_fair_value(eps: Optional[float], sector_pe: float) -> Optional[float]:
    if eps is None or eps <= 0 or sector_pe <= 0:
        return None
    return eps * sector_pe


def calculate_ev_ebitda_fair_value(ebitda: Optional[float], ev_multiple: float, debt: float, cash: float, shares: float) -> Optional[float]:
    if ebitda is None or ebitda <= 0 or ev_multiple <= 0:
        return None
    enterprise_value = ebitda * ev_multiple
    return safe_div(enterprise_value - debt + cash, shares)


def calculate_ddm_fair_value(dividend: Optional[float], wacc: float, ddm_growth: float) -> Optional[float]:
    if dividend is None or dividend <= EPSILON or wacc <= ddm_growth:
        return None
    return dividend * (1 + ddm_growth) / (wacc - ddm_growth)


def calculate_paid_capital_valuations(income_stmt: pd.DataFrame, shares: float) -> Tuple[Optional[float], Optional[float]]:
    paid_up_capital = shares if shares else None
    operating_income = _annual_value_for_year(income_stmt, OPERATING_INCOME_FIELDS, 2024)
    net_income = _annual_value_for_year(income_stmt, NET_INCOME_FIELDS, 2023)
    fair_value_efk = safe_div((operating_income * 10) if operating_income else None, paid_up_capital)
    fair_value_ndk = safe_div((net_income * 10) if net_income else None, paid_up_capital)
    return fair_value_efk, fair_value_ndk


def graham_valuation(eps: Optional[float], sector_pe: float, bond_yield: float) -> Optional[float]:
    if eps is None or eps <= EPSILON or sector_pe <= EPSILON or bond_yield <= EPSILON:
        return None
    return (eps * sector_pe) / (bond_yield * 100)


def calculate_financial_fair_value(info: Dict[str, Optional[float]], params: Dict[str, float], cost_of_equity: float) -> Optional[float]:
    book_value = info.get("bookValue")
    if book_value is None or book_value <= 0:
        return None

    values: list[float] = []
    sector_pb = params["pb"]
    if sector_pb > 0:
        values.append(book_value * sector_pb)

    roe = info.get("returnOnEquity")
    if roe is not None and roe > 0 and cost_of_equity > 0:
        implied_pb = max(0.4, min(4.0, roe / cost_of_equity))
        values.append(book_value * implied_pb)

    if not values:
        return None
    return sum(values) / len(values)


def build_output(
    ticker: str,
    sector_name: str,
    wacc: float,
    avg_growth: float,
    warnings: list[str],
    valuations: Dict[str, Optional[float]],
    fcf_by_year: Dict[int, Optional[float]],
) -> Dict[str, str]:
    fair_values = [value for value in valuations.values() if value is not None and value > 0]
    average_fair_value = sum(fair_values) / len(fair_values) if fair_values else None

    output: Dict[str, str] = {
        "Kod": clean_ticker(ticker),
        "Sektör": sector_name,
        "Para Birimi": get_currency_symbol(ticker),
        "WACC": format_percent_tr(wacc),
        "Ortalama Büyüme": format_percent_tr(avg_growth),
        "DCF Değerlemesi": format_number_tr(valuations["fv_dcf"]),
        "F/K Değerlemesi": format_number_tr(valuations["fv_fk"]),
        "PD/DD Finansal Model": format_number_tr(valuations["fv_financial"]),
        "EV/EBITDA Değerlemesi": format_number_tr(valuations["fv_ev"]),
        "DDM Değerlemesi": format_number_tr(valuations["fv_ddm"]),
        "EFK Değerlemesi": format_number_tr(valuations["fv_efk"]),
        "NDK Değerlemesi": format_number_tr(valuations["fv_ndk"]),
        "Graham Değerlemesi": format_number_tr(valuations["fv_graham"]),
        AVERAGE_FAIR_PRICE_LABEL: format_number_tr(average_fair_value),
        "Model Kalite Uyarıları": ",".join(sorted(set(warnings))),
    }
    for year in sorted(fcf_by_year.keys()):
        output[f"FCF {year}"] = format_number_tr(fcf_by_year[year])
    return output


def value_ticker(ticker: str) -> Dict[str, str]:
    bundle = fetch_ticker_bundle(ticker)
    info = normalized_info(bundle)
    warnings = validate_bundle(bundle, info)
    income_stmt = bundle.financials
    balance_sheet = bundle.balance_sheet
    cash_flow = bundle.cashflow

    params = get_country_params(ticker)
    sector_name, is_financial = resolve_sector(ticker)
    wacc = calculate_wacc(info, params)

    fcf_by_year = build_fcf_by_year(income_stmt, balance_sheet, cash_flow, params["tax_rate"])
    avg_growth = clamp_growth(compute_avg_growth(list(fcf_by_year.values())), wacc)

    shares = info.get("sharesOutstanding") or info.get("floatShares") or 1
    debt = info.get("totalDebt") or 0
    cash = info.get("totalCash") or 0
    eps = info.get("trailingEps")
    ebitda = get_ebitda_safely(info, income_stmt, cash_flow)
    dividend = info.get("dividendRate")
    fair_value_efk, fair_value_ndk = calculate_paid_capital_valuations(income_stmt, shares)
    cost_of_equity = params["risk_free_rate"] + (info.get("beta") or 1.0) * params["market_premium"]

    valuations = {
        "fv_dcf": None if is_financial else calculate_dcf_fair_value(
            fcf_by_year=fcf_by_year,
            avg_growth=avg_growth,
            wacc=wacc,
            debt=debt,
            cash=cash,
            shares=shares,
            terminal_growth=params["terminal_growth"],
        ),
        "fv_fk": calculate_fk_fair_value(eps, params["pe"]),
        "fv_financial": calculate_financial_fair_value(info, params, cost_of_equity) if is_financial else None,
        "fv_ev": None if is_financial else calculate_ev_ebitda_fair_value(ebitda, params["ev_ebitda"], debt, cash, shares),
        "fv_ddm": calculate_ddm_fair_value(dividend, wacc, params["ddm_growth"]),
        "fv_efk": fair_value_efk,
        "fv_ndk": fair_value_ndk,
        "fv_graham": graham_valuation(eps, params["pe"], params["bond_yield_2"]),
    }
    return build_output(
        ticker=ticker,
        sector_name=sector_name,
        wacc=wacc,
        avg_growth=avg_growth,
        warnings=warnings,
        valuations=valuations,
        fcf_by_year=fcf_by_year,
    )


def load_tickers(path: str) -> list[str]:
    try:
        with open(path, "r", encoding="utf-8") as source:
            tickers = [line.strip() for line in source if line.strip()]
        print("Kaynak:", path)
        return tickers
    except FileNotFoundError:
        print("❌ coverage.txt yok")
        return []


def run_valuation(tickers: list[str]) -> list[Dict[str, str]]:
    results: list[Dict[str, str]] = []
    for ticker_code in tickers:
        print("→", ticker_code, "analiz")
        try:
            result_row = value_ticker(ticker_code)
            if result_row:
                results.append(result_row)
        except TICKER_PROCESSING_ERRORS as error:
            print("  hata:", error)
        time.sleep(1)
    return results


def save_results(results: list[Dict[str, str]]) -> None:
    if not results:
        print("⚠️ sonuç yok")
        return
    result_frame = pd.DataFrame(results)
    ordered_columns = [column for column in result_frame.columns if column != AVERAGE_FAIR_PRICE_LABEL]
    ordered_columns.append(AVERAGE_FAIR_PRICE_LABEL)
    result_frame = result_frame[ordered_columns]
    result_frame.to_excel("valuation.xlsx", index=False, engine="openpyxl")
    print("✅ yazıldı → valuation.xlsx")


if __name__ == "__main__":
    coverage_file = "coverage.txt"
    ticker_list = load_tickers(coverage_file)
    valuation_results = run_valuation(ticker_list)
    save_results(valuation_results)
