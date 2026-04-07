# -*- coding: utf-8 -*-

import time

import pandas as pd
import yfinance as yf

from sector_override_builder import load_sector_overrides


# Türkiye (BIST)
RISK_FREE_RATE_TR = 0.36
MARKET_PREMIUM_TR = 0.08
COST_OF_DEBT_TR = 0.40
TAX_RATE_TR = 0.25

# ABD
RISK_FREE_RATE_US = 0.042
MARKET_PREMIUM_US = 0.050
COST_OF_DEBT_US = 0.055
TAX_RATE_US = 0.21

TERMINAL_GROWTH = 0.030
YEARS_PROJECTION = 5

SECTOR_PE_TR = 10.0
SECTOR_PE_US = 22.0

SECTOR_EV_EBITDA_TR = 7.0
SECTOR_EV_EBITDA_US = 11.0
DDM_GROWTH_DEFAULT = 0.025

BOND_YIELD_2_TR = 0.36
BOND_YIELD_2_US = 0.041

MAX_GROWTH_CAP = 0.50
MIN_GROWTH_CAP = -0.50

SECTOR_OVERRIDES = load_sector_overrides()

NUMBER_FORMAT = "{:,.2f}"
AVERAGE_FAIR_PRICE_LABEL = "Ortalama Adil Fiyat"

OPERATING_INCOME = "Operating Income"
TOTAL_OPERATING_INCOME = "Total Operating Income"
OPERATING_INCOME_FIELDS = [OPERATING_INCOME, TOTAL_OPERATING_INCOME]
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


def safe_div(numerator, denominator):
    try:
        if numerator is None or denominator in (None, 0):
            return None
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def format_number_tr(value):
    if value is None:
        return ""
    try:
        return NUMBER_FORMAT.format(float(value)).replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def format_percent_tr(value):
    if value is None:
        return ""
    try:
        return f"{value * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def get_currency_symbol(ticker_code):
    return "₺" if ticker_code.upper().endswith(".IS") else "$"


def clean_ticker(ticker_code):
    return ticker_code.replace(".IS", "") if ticker_code.upper().endswith(".IS") else ticker_code


def compute_avg_growth(series):
    values = [item for item in series if item is not None]
    if len(values) < 2:
        return 0.05

    growths = []
    for index in range(1, len(values)):
        previous = values[index - 1]
        current = values[index]
        if previous in (None, 0):
            continue
        growth = current / previous - 1
        growth = max(min(growth, MAX_GROWTH_CAP), MIN_GROWTH_CAP)
        growths.append(growth)

    return sum(growths) / len(growths) if growths else 0.05


def get_country_params(ticker):
    if ticker.upper().endswith(".IS"):
        return {
            "risk_free_rate": RISK_FREE_RATE_TR,
            "market_premium": MARKET_PREMIUM_TR,
            "cost_of_debt": COST_OF_DEBT_TR,
            "tax_rate": TAX_RATE_TR,
            "pe": SECTOR_OVERRIDES.get(ticker, {}).get("pe", SECTOR_PE_TR),
            "ev_ebitda": SECTOR_OVERRIDES.get(ticker, {}).get("ev_ebitda", SECTOR_EV_EBITDA_TR),
            "bond_yield_2": BOND_YIELD_2_TR,
        }
    return {
        "risk_free_rate": RISK_FREE_RATE_US,
        "market_premium": MARKET_PREMIUM_US,
        "cost_of_debt": COST_OF_DEBT_US,
        "tax_rate": TAX_RATE_US,
        "pe": SECTOR_OVERRIDES.get(ticker, {}).get("pe", SECTOR_PE_US),
        "ev_ebitda": SECTOR_OVERRIDES.get(ticker, {}).get("ev_ebitda", SECTOR_EV_EBITDA_US),
        "bond_yield_2": BOND_YIELD_2_US,
    }


def calculate_wacc(info, ticker):
    params = get_country_params(ticker)
    beta = info.get("beta", 1.0) or 1.0
    equity = info.get("marketCap", 0.0) or 0.0
    debt = info.get("totalDebt", 0.0) or 0.0
    total_capital = equity + debt if (equity + debt) > 0 else 1

    cost_of_equity = params["risk_free_rate"] + beta * params["market_premium"]
    cost_of_debt = info.get("interestRate", params["cost_of_debt"]) or params["cost_of_debt"]
    tax_rate = params["tax_rate"]
    return (equity / total_capital) * cost_of_equity + (debt / total_capital) * cost_of_debt * (1 - tax_rate)


def _is_dataframe(frame):
    return isinstance(frame, pd.DataFrame) and not frame.empty


def _annual_value_for_year(frame, row_names, target_year):
    if not _is_dataframe(frame):
        return None
    row_name = next((candidate for candidate in row_names if candidate in frame.index), None)
    if row_name is None:
        return None
    for column in frame.columns:
        if getattr(column, "year", None) == target_year:
            value = frame.loc[row_name, column]
            return float(value) if pd.notna(value) else None
    return None


def get_ebitda_safely(info, income_stmt, cash_flow, year_hint=2024):
    ebitda = info.get("ebitda")
    if isinstance(ebitda, (int, float)) and ebitda != 0:
        return float(ebitda)

    operating_income = _annual_value_for_year(income_stmt, OPERATING_INCOME_FIELDS, year_hint) or 0
    depreciation = _annual_value_for_year(cash_flow, DEPRECIATION_FIELDS, year_hint) or 0
    derived_ebitda = operating_income + depreciation
    if derived_ebitda > 1e12:
        derived_ebitda /= 1_000_000
    return float(derived_ebitda)


def calculate_fcf(
    operating_income,
    tax,
    depreciation,
    capex,
    receivable,
    inventory,
    liability,
    prev_receivable,
    prev_inventory,
    prev_liability,
    tax_rate_fallback,
):
    if not operating_income:
        return None
    effective_tax = abs(tax / operating_income) if tax and operating_income != 0 else tax_rate_fallback
    nopat = operating_income * (1 - effective_tax)
    delta_working_capital = (
        (receivable or 0) + (inventory or 0) - (liability or 0)
    ) - (
        (prev_receivable or 0) + (prev_inventory or 0) - (prev_liability or 0)
    )
    return nopat + (depreciation or 0) - (capex or 0) - delta_working_capital


def build_fcf_by_year(income_stmt, balance_sheet, cash_flow, tax_rate):
    fcf_by_year = {}
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


def clamp_growth(avg_growth, wacc):
    if avg_growth < wacc:
        return avg_growth
    clamped_growth = wacc - 0.01
    return max(min(clamped_growth, MAX_GROWTH_CAP), MIN_GROWTH_CAP)


def calculate_dcf_fair_value(fcf_by_year, avg_growth, wacc, debt, cash, shares):
    past_fcfs = [value for value in fcf_by_year.values() if value is not None]
    if not past_fcfs:
        return None
    last_fcf = past_fcfs[-1]

    projected_fcfs = [last_fcf * ((1 + avg_growth) ** year) for year in range(1, YEARS_PROJECTION + 1)]
    discounted_fcfs = [fcf / ((1 + wacc) ** (year + 1)) for year, fcf in enumerate(projected_fcfs)]

    present_terminal_value = 0
    if projected_fcfs and wacc > TERMINAL_GROWTH:
        present_terminal_value = (
            projected_fcfs[-1] * (1 + TERMINAL_GROWTH) / (wacc - TERMINAL_GROWTH)
        ) / ((1 + wacc) ** YEARS_PROJECTION)

    enterprise_value = sum(discounted_fcfs) + present_terminal_value
    return safe_div(enterprise_value - debt + cash, shares)


def calculate_fk_fair_value(eps, sector_pe):
    if eps is None or eps <= 0 or sector_pe is None or sector_pe <= 0:
        return None
    return eps * sector_pe


def calculate_ev_ebitda_fair_value(ebitda, ev_multiple, debt, cash, shares):
    if ebitda is None or ebitda <= 0 or ev_multiple is None or ev_multiple <= 0:
        return None
    enterprise_value = ebitda * ev_multiple
    return safe_div(enterprise_value - debt + cash, shares)


def calculate_ddm_fair_value(dividend, wacc):
    if dividend <= 0 or wacc <= DDM_GROWTH_DEFAULT:
        return None
    return dividend * (1 + DDM_GROWTH_DEFAULT) / (wacc - DDM_GROWTH_DEFAULT)


def calculate_paid_capital_valuations(income_stmt, shares):
    paid_up_capital = shares if shares else None
    operating_income = _annual_value_for_year(income_stmt, OPERATING_INCOME_FIELDS, 2024)
    net_income = _annual_value_for_year(income_stmt, NET_INCOME_FIELDS, 2023)
    fair_value_efk = safe_div((operating_income * 10) if operating_income else None, paid_up_capital)
    fair_value_ndk = safe_div((net_income * 10) if net_income else None, paid_up_capital)
    return fair_value_efk, fair_value_ndk


def graham_valuation(eps, sector_pe, bond_yield):
    if not eps or not sector_pe or not bond_yield:
        return None
    return (eps * sector_pe) / (bond_yield * 100)


def build_output(ticker, wacc, avg_growth, valuations, fcf_by_year):
    fair_values = [value for value in valuations.values() if value is not None and value > 0]
    average_fair_value = sum(fair_values) / len(fair_values) if fair_values else None

    output = {
        "Kod": clean_ticker(ticker),
        "Para Birimi": get_currency_symbol(ticker),
        "WACC": format_percent_tr(wacc),
        "Ortalama Büyüme": format_percent_tr(avg_growth),
        "DCF Değerlemesi": format_number_tr(valuations["fv_dcf"]),
        "F/K Değerlemesi": format_number_tr(valuations["fv_fk"]),
        "EV/EBITDA Değerlemesi": format_number_tr(valuations["fv_ev"]),
        "DDM Değerlemesi": format_number_tr(valuations["fv_ddm"]),
        "EFK Değerlemesi": format_number_tr(valuations["fv_efk"]),
        "NDK Değerlemesi": format_number_tr(valuations["fv_ndk"]),
        "Graham Değerlemesi": format_number_tr(valuations["fv_graham"]),
        AVERAGE_FAIR_PRICE_LABEL: format_number_tr(average_fair_value),
    }
    for year in sorted(fcf_by_year.keys()):
        output[f"FCF {year}"] = format_number_tr(fcf_by_year[year])
    return output


def value_ticker(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info or {}
    income_stmt = stock.financials
    balance_sheet = stock.balance_sheet
    cash_flow = stock.cashflow

    params = get_country_params(ticker)
    wacc = calculate_wacc(info, ticker)
    fcf_by_year = build_fcf_by_year(income_stmt, balance_sheet, cash_flow, params["tax_rate"])
    avg_growth = clamp_growth(compute_avg_growth(list(fcf_by_year.values())), wacc)

    shares = info.get("sharesOutstanding") or info.get("floatShares") or 1
    debt = info.get("totalDebt", 0) or 0
    cash = info.get("totalCash", 0) or 0

    eps = info.get("trailingEps")
    ebitda = get_ebitda_safely(info, income_stmt, cash_flow)
    dividend = info.get("dividendRate", 0) or 0
    fair_value_efk, fair_value_ndk = calculate_paid_capital_valuations(income_stmt, shares)

    valuations = {
        "fv_dcf": calculate_dcf_fair_value(fcf_by_year, avg_growth, wacc, debt, cash, shares),
        "fv_fk": calculate_fk_fair_value(eps, params["pe"]),
        "fv_ev": calculate_ev_ebitda_fair_value(ebitda, params["ev_ebitda"], debt, cash, shares),
        "fv_ddm": calculate_ddm_fair_value(dividend, wacc),
        "fv_efk": fair_value_efk,
        "fv_ndk": fair_value_ndk,
        "fv_graham": graham_valuation(eps, params["pe"], params["bond_yield_2"]),
    }
    return build_output(ticker, wacc, avg_growth, valuations, fcf_by_year)


def load_tickers(path):
    try:
        with open(path, "r", encoding="utf-8") as source:
            tickers = [line.strip() for line in source if line.strip()]
        print("Kaynak:", path)
        return tickers
    except FileNotFoundError:
        print("❌ coverage.txt yok")
        return []


def run_valuation(tickers):
    results = []
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


def save_results(results):
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
