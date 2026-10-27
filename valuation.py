from __future__ import annotations

import json
import time
from statistics import median, pstdev
from typing import Any

import pandas as pd

from data.live_params import fetch_us_erp
from data.macro_config import load_macro_config
from data.market_data_provider import (
    fetch_ticker_bundle,
    normalized_info,
    validate_bundle,
)
from data.peer_multiples import get_live_sector_multiples
from data.sector import FETCH_ERRORS, TR_PROFILE, US_PROFILE, build_sector_maps
from data.sector_override_builder import load_sector_overrides

YEARS_PROJECTION = 5
MAX_GROWTH_CAP = 0.50
MIN_GROWTH_CAP = -0.50
EPSILON = 1e-9
TICKER_DELAY_SECONDS = 0.15

NUMBER_FORMAT = "{:,.2f}"
AVERAGE_FAIR_PRICE_LABEL = "Ortalama Adil Fiyat"

OPERATING_INCOME_FIELDS = ["Operating Income", "Total Operating Income"]
TAX_FIELDS = ["Tax Provision", "Income Tax Expense"]
DEPRECIATION_FIELDS = ["Depreciation And Amortization", "Depreciation"]
CAPEX_FIELDS = ["Capital Expenditure", "Capital Expenditures"]
DELTA_NWC_FIELDS = ["Change In Working Capital", "Changes In Working Capital"]
PRETAX_INCOME_FIELDS = ["Pretax Income", "Income Before Tax"]
SBC_FIELDS = ["Stock Based Compensation", "Share Based Compensation"]
NET_INCOME_FIELDS = ["Net Income", "Net Income Applicable to Common Shares"]
REVENUE_FIELDS = ["Total Revenue", "Revenue"]


TICKER_PROCESSING_ERRORS = (
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
    OSError,
    RuntimeError,
    ZeroDivisionError,
) + FETCH_ERRORS

MACRO_CONFIG = load_macro_config()
SECTOR_OVERRIDES = load_sector_overrides()


def load_company_metadata(path: str = "company_metadata.json") -> dict[str, dict[str, str]]:
    try:
        with open(path, encoding="utf-8") as _f:
            raw = json.load(_f)
        if isinstance(raw, dict):
            return {k: v for k, v in raw.items() if isinstance(k, str) and isinstance(v, dict)}
    except (OSError, json.JSONDecodeError):
        pass
    return {}


COMPANY_METADATA: dict[str, dict[str, str]] = load_company_metadata()
TR_SECTOR_MAP, US_SECTOR_MAP = build_sector_maps(auto_classify=False)


def build_sector_lookup(sector_map: dict[str, list[str]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for sector_name, tickers in sector_map.items():
        for ticker in tickers:
            lookup[ticker] = sector_name
    return lookup


TR_LOOKUP = build_sector_lookup(TR_SECTOR_MAP)
US_LOOKUP = build_sector_lookup(US_SECTOR_MAP)


def reload_runtime_config() -> None:
    """Diskteki son doğrulanmış yapılandırmayı çalışan sürece yükler."""
    global MACRO_CONFIG, SECTOR_OVERRIDES, COMPANY_METADATA, TR_SECTOR_MAP, US_SECTOR_MAP, TR_LOOKUP, US_LOOKUP
    MACRO_CONFIG = load_macro_config()
    SECTOR_OVERRIDES = load_sector_overrides()
    COMPANY_METADATA = load_company_metadata()
    TR_SECTOR_MAP, US_SECTOR_MAP = build_sector_maps(auto_classify=False)
    TR_LOOKUP = build_sector_lookup(TR_SECTOR_MAP)
    US_LOOKUP = build_sector_lookup(US_SECTOR_MAP)


def safe_div(numerator: float | None, denominator: float | None) -> float | None:
    try:
        if numerator is None or is_near_zero(denominator):
            return None
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def safe_float(value: Any) -> float | None:
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


def is_near_zero(value: float | None, epsilon: float = EPSILON) -> bool:
    if value is None:
        return True
    try:
        return abs(float(value)) <= epsilon
    except (TypeError, ValueError):
        return True


def has_nonzero_value(value: float | None, epsilon: float = EPSILON) -> bool:
    return not is_near_zero(value, epsilon)


def format_number_tr(value: float | None) -> str:
    if value is None:
        return ""
    try:
        return NUMBER_FORMAT.format(float(value)).replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def format_percent_tr(value: float | None) -> str:
    if value is None:
        return ""
    try:
        return f"{value * 100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return ""


def round_or_none(value: float | None, digits: int = 2) -> float | None:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except (TypeError, ValueError):
        return None


def get_currency_symbol(ticker_code: str) -> str:
    return "₺" if ticker_code.upper().endswith(".IS") else "$"


def clean_ticker(ticker_code: str) -> str:
    return ticker_code.removesuffix(".IS")


def is_turkish_ticker(ticker: str) -> bool:
    return ticker.upper().endswith(".IS")


def resolve_sector(ticker: str) -> tuple[str, bool]:
    if is_turkish_ticker(ticker):
        sector_name = TR_LOOKUP.get(ticker, TR_PROFILE.other_label)
        return sector_name, sector_name in TR_PROFILE.financial_sectors
    sector_name = US_LOOKUP.get(ticker, US_PROFILE.other_label)
    return sector_name, sector_name in US_PROFILE.financial_sectors


def compute_avg_growth(series: list[float | None]) -> float:
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


_LIVE_RF_CACHE: dict[str, float] = {}


def _fetch_live_us_rf() -> float:
    """Skill metodolojisi: ^TNX'ten live 10Y UST yield çeker, başarısız olursa config fallback."""
    if "us" in _LIVE_RF_CACHE:
        return _LIVE_RF_CACHE["us"]
    try:
        import yfinance as yf
        tnx = yf.Ticker("^TNX")
        price = tnx.info.get("regularMarketPrice") or tnx.info.get("currentPrice")
        if price and price > 0:
            rf = float(price) / 100.0
            _LIVE_RF_CACHE["us"] = rf
            return rf
    except TICKER_PROCESSING_ERRORS:
        pass
    fallback = float(MACRO_CONFIG["us"]["risk_free_rate"])
    _LIVE_RF_CACHE["us"] = fallback
    return fallback


_FX_RATE_CACHE: dict[str, dict[str, float]] = {}
_FX_CACHE_TTL = 300  # 5 minutes


def _fetch_fx_rate(pair: str, warnings: list[str] | None = None) -> float | None:
    """FX kuru çeker; çift bazlı TTL önbellek, stale fallback, None döner yalnızca önbelleksiz hata durumunda."""
    now = time.time()
    entry = _FX_RATE_CACHE.get(pair, {})
    cached_ts = entry.get("ts")
    cached_val = entry.get("val")
    if cached_val and cached_ts and (now - cached_ts) < _FX_CACHE_TTL:
        return cached_val
    try:
        import yfinance as _yf
        _fx = _yf.Ticker(pair)
        rate = float(_fx.fast_info.last_price or _fx.info.get("regularMarketPrice") or 0) or None
        if rate and rate > 1:
            _FX_RATE_CACHE[pair] = {"ts": now, "val": rate}
            return rate
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    if cached_val:
        if warnings is not None:
            currency = pair.replace("TRY=X", "")
            warnings.append(f"{currency}/TRY kuru alınamadı; eski önbellek değeri kullanılıyor.")
        return cached_val
    return None


def _detect_reporting_currency(ticker: str, info: dict[str, Any]) -> str:
    """Ticker'ın raporlama para birimini tespit eder.

    company_metadata.json override önceliklidir; yoksa yfinance financialCurrency kullanılır.
    """
    override = COMPANY_METADATA.get(ticker, {}).get("reporting_currency")
    if override:
        return override.upper()
    financial_currency = info.get("financialCurrency")
    if isinstance(financial_currency, str) and financial_currency.upper() in ("EUR", "USD", "TRY"):
        return financial_currency.upper()
    return "TRY"


def get_country_params(ticker: str, financial_currency: str = "TRY") -> dict[str, float]:
    override = SECTOR_OVERRIDES.get(ticker, {})
    if is_turkish_ticker(ticker):
        if financial_currency == "EUR":
            market_key = "eur_tr"
        elif financial_currency == "USD":
            market_key = "usd_tr"
        else:
            market_key = "tr"
    else:
        market_key = "us"
    market_config = MACRO_CONFIG[market_key]
    defaults = market_config["defaults"]
    if market_key == "us":
        rf = _fetch_live_us_rf()
        erp = fetch_us_erp(fallback=float(market_config["market_premium"]))
    else:
        rf = float(market_config["risk_free_rate"])
        erp = float(market_config["market_premium"])
    return {
        "market_key": market_key,
        "risk_free_rate": rf,
        "market_premium": erp,
        "cost_of_debt": float(market_config["cost_of_debt"]),
        "tax_rate": float(market_config["tax_rate"]),
        "terminal_growth": float(market_config["terminal_growth"]),
        "ddm_growth": float(market_config["ddm_growth"]),
        "bond_yield_2": float(market_config["bond_yield_2"]),
        "pe": float(override.get("pe", defaults["pe"])),
        "pb": float(override.get("pb", defaults["pb"])),
        "ev_ebitda": float(override.get("ev_ebitda", defaults["ev_ebitda"])),
        "ev_rev": 0.0,
    }


def _bs_field(balance_sheet: pd.DataFrame, fields: list[str]) -> float | None:
    for field in fields:
        if field in balance_sheet.index:
            return safe_float(balance_sheet.loc[field].iloc[0])
    return None


def _current_fin_debt(curr_debt_total: float | None, curr_lease: float | None) -> float:
    if curr_debt_total is not None and curr_lease is not None:
        return max(0.0, curr_debt_total - curr_lease)
    return curr_debt_total if curr_debt_total is not None else 0.0


def _get_financial_debt(balance_sheet: pd.DataFrame | None, info_total_debt: float) -> float:
    """Balance sheet'ten finansal borcu çeker (işletme kiraları hariç)."""
    if not _is_dataframe(balance_sheet):
        return info_total_debt
    lt_debt = _bs_field(balance_sheet, ["Long Term Debt", "LongTermDebt"])
    curr_debt_total = _bs_field(balance_sheet, ["Current Debt And Capital Lease Obligation", "Current Debt"])
    curr_lease = _bs_field(balance_sheet, ["Current Capital Lease Obligation", "Current Portion Of Capital Lease"])
    curr_fin_debt = _current_fin_debt(curr_debt_total, curr_lease)
    if lt_debt is not None and lt_debt > 0:
        return lt_debt + curr_fin_debt
    return info_total_debt


def _compute_effective_kd(income_stmt: pd.DataFrame, total_debt: float) -> float:
    """Skill: kd = interest_expense / total_debt, fallback 5.5%."""
    interest_fields = ["Interest Expense", "Interest Expense Non Operating"]
    for year in range(2024, 2021, -1):
        for field in interest_fields:
            val = _annual_value_for_year(income_stmt, [field], year)
            if val is not None and abs(val) > 0:
                kd = abs(val) / total_debt
                return max(0.02, min(kd, 0.15))
    return 0.055


def _compute_effective_tax_rate(income_stmt: pd.DataFrame) -> float:
    """Skill: 3-yr median effective tax rate, floored 15%, capped 30%."""
    rates = []
    for year in range(2022, 2025):
        tax = _annual_value_for_year(income_stmt, TAX_FIELDS, year)
        pretax = _annual_value_for_year(income_stmt, PRETAX_INCOME_FIELDS, year)
        if tax is not None and pretax is not None and pretax > 0:
            rate = abs(tax) / pretax
            if 0.05 <= rate <= 0.50:
                rates.append(max(0.15, min(rate, 0.30)))
    return median(rates) if rates else 0.21


def calculate_wacc(
    info: dict[str, float | None],
    params: dict[str, float],
    income_stmt: pd.DataFrame | None = None,
    balance_sheet: pd.DataFrame | None = None,
) -> tuple[float, float, float]:
    """Skill metodolojisi: (wacc, effective_tax_rate, effective_kd) döndürür."""
    beta = info.get("beta") or 1.0
    equity = info.get("marketCap") or 0.0
    info_debt = info.get("totalDebt") or 0.0
    # Skill: finansal borcu kullan (işletme kiraları hariç — E/V ve kd için)
    fin_debt = _get_financial_debt(balance_sheet, info_debt)
    total_capital = equity + fin_debt if (equity + fin_debt) > 0 else 1

    # ke = rf + beta * ERP (ERP = 5.5% skill hardcoded)
    cost_of_equity = params["risk_free_rate"] + beta * params["market_premium"]

    # Effective kd from financials (skill: interest_expense / financial_debt)
    if _is_dataframe(income_stmt) and fin_debt > 0:
        cost_of_debt = _compute_effective_kd(income_stmt, fin_debt)
    else:
        cost_of_debt = params["cost_of_debt"]

    # Effective tax rate from financials (skill: 3-yr median, floor 15%, cap 30%)
    if _is_dataframe(income_stmt):
        tax_rate = _compute_effective_tax_rate(income_stmt)
    else:
        tax_rate = params["tax_rate"]

    wacc = (equity / total_capital) * cost_of_equity + (fin_debt / total_capital) * cost_of_debt * (1 - tax_rate)
    return wacc, tax_rate, cost_of_debt


def _is_dataframe(frame: Any) -> bool:
    return isinstance(frame, pd.DataFrame) and not frame.empty


def _annual_value_for_year(frame: pd.DataFrame, row_names: list[str], target_year: int) -> float | None:
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


def extract_numeric_scalar(value: Any) -> float | None:
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


def get_ebitda_safely(info: dict[str, float | None], income_stmt: pd.DataFrame, cash_flow: pd.DataFrame, year_hint: int = 2024) -> float | None:
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
    operating_income: float | None,
    pretax_income: float | None,
    tax: float | None,
    depreciation: float | None,
    capex: float | None,
    delta_nwc: float | None,
    sbc: float | None,
    tax_rate_fallback: float,
) -> float | None:
    operating_income_value = safe_float(operating_income)
    if operating_income_value is None or is_near_zero(operating_income_value):
        return None
    tax_value = safe_float(tax)
    # Use pretax income as tax base (correct denominator); fall back to operating income if unavailable
    pretax_value = safe_float(pretax_income)
    tax_base = pretax_value if has_nonzero_value(pretax_value) else operating_income_value
    effective_tax = (
        max(0.0, min(abs(tax_value / tax_base), 0.50))
        if tax_value is not None and has_nonzero_value(tax_base)
        else tax_rate_fallback
    )
    nopat = operating_income_value * (1 - effective_tax)
    # capex from yfinance cashflow is negative (outflow), so adding it subtracts correctly
    # delta_nwc from "Change In Working Capital" is sign-adjusted: negative = WC increase (uses cash)
    # sbc from yfinance cashflow is positive (non-cash add-back); subtract for cash FCF
    return (
        nopat
        + (safe_float(depreciation) or 0)
        + (safe_float(capex) or 0)
        + (safe_float(delta_nwc) or 0)
        - (safe_float(sbc) or 0)
    )


def build_fcf_by_year(income_stmt: pd.DataFrame, cash_flow: pd.DataFrame, tax_rate: float) -> dict[int, float | None]:
    """Görüntüleme ve büyüme hesabı için geçmiş FCF verilerini döndürür."""
    fcf_by_year: dict[int, float | None] = {}
    for year in range(2021, 2026):
        fcf_by_year[year] = calculate_fcf(
            _annual_value_for_year(income_stmt, OPERATING_INCOME_FIELDS, year),
            _annual_value_for_year(income_stmt, PRETAX_INCOME_FIELDS, year),
            _annual_value_for_year(income_stmt, TAX_FIELDS, year),
            _annual_value_for_year(cash_flow, DEPRECIATION_FIELDS, year),
            _annual_value_for_year(cash_flow, CAPEX_FIELDS, year),
            _annual_value_for_year(cash_flow, DELTA_NWC_FIELDS, year),
            _annual_value_for_year(cash_flow, SBC_FIELDS, year),
            tax_rate_fallback=tax_rate,
        )
    return fcf_by_year


def _get_latest_revenue(income_stmt: pd.DataFrame) -> float | None:
    """En güncel yıllık geliri döndürür."""
    for year in range(2025, 2020, -1):
        rev = _annual_value_for_year(income_stmt, REVENUE_FIELDS, year)
        if rev and rev > 0:
            return rev
    return None


def _collect_year_margin_ratios(
    income_stmt: pd.DataFrame,
    cash_flow: pd.DataFrame,
    year: int,
    revenue: float,
) -> tuple[float | None, float | None, float | None, float | None]:
    ebit = _annual_value_for_year(income_stmt, OPERATING_INCOME_FIELDS, year)
    da = _annual_value_for_year(cash_flow, DEPRECIATION_FIELDS, year)
    capex = _annual_value_for_year(cash_flow, CAPEX_FIELDS, year)
    nwc = _annual_value_for_year(cash_flow, DELTA_NWC_FIELDS, year)
    return (
        ebit / revenue if ebit is not None else None,
        da / revenue if (da is not None and da >= 0) else None,
        abs(capex) / revenue if capex is not None else None,
        abs(nwc) / revenue if nwc is not None else None,
    )


def _append_optional(lst: list, val: float | None) -> None:
    if val is not None:
        lst.append(val)


def compute_margin_profile(income_stmt: pd.DataFrame, cash_flow: pd.DataFrame) -> dict[str, float]:
    """Skill: son 3 yılın medyan EBIT%, D&A%, CapEx%, NWC% değerlerini hesaplar."""
    ebit_margins: list[float] = []
    da_pcts: list[float] = []
    capex_pcts: list[float] = []
    nwc_pcts: list[float] = []
    for year in range(2023, 2026):
        revenue = _annual_value_for_year(income_stmt, REVENUE_FIELDS, year)
        if not revenue or revenue <= 0:
            continue
        em, dp, cp, np_ = _collect_year_margin_ratios(income_stmt, cash_flow, year, revenue)
        _append_optional(ebit_margins, em)
        _append_optional(da_pcts, dp)
        _append_optional(capex_pcts, cp)
        _append_optional(nwc_pcts, np_)
    return {
        "ebit_margin": median(ebit_margins) if ebit_margins else 0.15,
        "da_pct": median(da_pcts) if da_pcts else 0.05,
        "capex_pct": median(capex_pcts) if capex_pcts else 0.05,
        "nwc_pct": median(nwc_pcts) if nwc_pcts else 0.01,
    }


def compute_revenue_cagr(income_stmt: pd.DataFrame) -> float | None:
    """Gelir büyümesini FCF yerine doğrudan gelirden hesaplar (daha istikrarlı)."""
    revenues: list[float] = []
    for year in range(2021, 2026):
        rev = _annual_value_for_year(income_stmt, REVENUE_FIELDS, year)
        if rev and rev > 0:
            revenues.append(rev)
    if len(revenues) < 2:
        return None
    n = len(revenues) - 1
    cagr = (revenues[-1] / revenues[0]) ** (1 / n) - 1
    return max(min(cagr, MAX_GROWTH_CAP), MIN_GROWTH_CAP)


def clamp_growth(avg_growth: float, wacc: float) -> float:
    if avg_growth < wacc:
        return avg_growth
    clamped_growth = wacc - 0.01
    return max(min(clamped_growth, MAX_GROWTH_CAP), MIN_GROWTH_CAP)


def calculate_dcf_fair_value(
    latest_revenue: float | None,
    margin_profile: dict[str, float],
    initial_growth: float,
    wacc: float,
    debt: float,
    cash: float,
    shares: float,
    terminal_growth: float,
    tax_rate: float,
    ev_ebitda_multiple: float = 15.0,
) -> float | None:
    """
    Skill metodolojisi: gelir × marj oranlarından FCFF üretir (SBC çıkartılmaz).
    Büyüme oranı y1'den (terminal+1%)'ye doğrusal azalır.
    Terminal value: %50 Gordon + %50 EV/EBITDA çıkış (skill ile aynı).
    """
    if not latest_revenue or latest_revenue <= 0:
        return None
    if wacc <= terminal_growth:
        return None

    ebit_margin = margin_profile.get("ebit_margin", 0.15)
    da_pct = margin_profile.get("da_pct", 0.05)
    capex_pct = margin_profile.get("capex_pct", 0.05)
    nwc_pct = margin_profile.get("nwc_pct", 0.01)

    # Skill: y1 → (terminal+1%) arası doğrusal büyüme yolu
    end_growth = terminal_growth + 0.01
    n = YEARS_PROJECTION
    step = (end_growth - initial_growth) / (n - 1) if n > 1 else 0.0
    growth_path = [initial_growth + step * i for i in range(n)]

    revenue = latest_revenue
    fcffs: list[float] = []
    for g in growth_path:
        revenue = revenue * (1 + g)
        nopat = revenue * ebit_margin * (1 - tax_rate)
        fcff = nopat + revenue * da_pct - revenue * capex_pct - revenue * nwc_pct
        fcffs.append(fcff)

    discounted = [f / (1 + wacc) ** (i + 1) for i, f in enumerate(fcffs)]

    # Terminal value: %50 Gordon + %50 EV/EBITDA çıkış (skill metodolojisi)
    tv_gordon = fcffs[-1] * (1 + terminal_growth) / (wacc - terminal_growth)
    ebitda_year5 = revenue * (ebit_margin + da_pct)
    tv_exit = ebitda_year5 * ev_ebitda_multiple
    tv_blended = 0.5 * tv_gordon + 0.5 * tv_exit

    pv_tv = tv_blended / (1 + wacc) ** YEARS_PROJECTION
    enterprise_value = sum(discounted) + pv_tv
    return safe_div(enterprise_value - debt + cash, shares)


def calculate_fk_fair_value(eps: float | None, sector_pe: float) -> float | None:
    if eps is None or eps <= 0 or sector_pe <= 0:
        return None
    return eps * sector_pe


def calculate_ev_ebitda_fair_value(ebitda: float | None, ev_multiple: float, debt: float, cash: float, shares: float) -> float | None:
    if ebitda is None or ebitda <= 0 or ev_multiple <= 0:
        return None
    enterprise_value = ebitda * ev_multiple
    return safe_div(enterprise_value - debt + cash, shares)


def calculate_ddm_fair_value(dividend: float | None, wacc: float, ddm_growth: float) -> float | None:
    if dividend is None or dividend <= EPSILON or wacc <= ddm_growth:
        return None
    return dividend * (1 + ddm_growth) / (wacc - ddm_growth)


def calculate_paid_capital_valuations(income_stmt: pd.DataFrame, shares: float) -> tuple[float | None, float | None]:
    paid_up_capital = shares if shares else None
    operating_income = _annual_value_for_year(income_stmt, OPERATING_INCOME_FIELDS, 2024)
    net_income = _annual_value_for_year(income_stmt, NET_INCOME_FIELDS, 2023)
    fair_value_efk = safe_div((operating_income * 10) if operating_income else None, paid_up_capital)
    fair_value_ndk = safe_div((net_income * 10) if net_income else None, paid_up_capital)
    return fair_value_efk, fair_value_ndk


def graham_valuation(eps: float | None, sector_pe: float, bond_yield: float) -> float | None:
    if eps is None or eps <= EPSILON or sector_pe <= EPSILON or bond_yield <= EPSILON:
        return None
    return (eps * sector_pe) / (bond_yield * 100)


def calculate_financial_fair_value(info: dict[str, float | None], params: dict[str, float], cost_of_equity: float) -> float | None:
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


def applicable_valuation_keys(is_financial: bool, is_turkish: bool = True) -> list[str]:
    tr_only = ["fv_efk", "fv_ndk", "fv_graham"]
    if is_financial:
        base = ["fv_fk", "fv_financial", "fv_ddm"]
    else:
        base = ["fv_dcf", "fv_relative", "fv_ddm"]
    return base + tr_only if is_turkish else base


def compute_signal_quality_score(
    valuations: dict[str, float | None],
    warnings: list[str],
    is_financial: bool,
    is_turkish: bool = True,
) -> tuple[int, str]:
    keys = applicable_valuation_keys(is_financial, is_turkish)
    present_values = [valuations[key] for key in keys if valuations.get(key) is not None and valuations.get(key) > 0]
    expected_count = len(keys)
    coverage = (len(present_values) / expected_count) if expected_count else 0

    warning_penalty = min(len(set(warnings)) * 8, 40)
    dispersion_penalty = 0
    if len(present_values) >= 3:
        mean_value = sum(present_values) / len(present_values)
        if mean_value > 0:
            variation = pstdev(present_values) / mean_value
            if variation > 1.0:
                dispersion_penalty = 12
            elif variation > 0.6:
                dispersion_penalty = 6

    score = round(max(0, min(100, 45 + coverage * 55 - warning_penalty - dispersion_penalty)))
    if score >= 80:
        quality = "High"
    elif score >= 60:
        quality = "Medium"
    else:
        quality = "Low"
    return score, quality


def _blend_fair_values(valuations: dict[str, float | None]) -> float | None:
    fv_dcf = valuations.get("fv_dcf")
    fv_relative = valuations.get("fv_relative")
    if fv_dcf and fv_relative and fv_dcf > 0 and fv_relative > 0:
        return 0.5 * fv_dcf + 0.5 * fv_relative
    if fv_dcf and fv_dcf > 0:
        return fv_dcf
    if fv_relative and fv_relative > 0:
        return fv_relative
    excluded = ("fv_efk", "fv_ndk", "fv_graham", "fv_ddm", "fv_relative")
    fair_values = [v for k, v in valuations.items() if v is not None and v > 0 and k not in excluded]
    return sum(fair_values) / len(fair_values) if fair_values else None


def _build_detail_fields(extra: dict[str, Any]) -> dict[str, Any]:
    def _pct(key: str) -> float | None:
        v = extra.get(key)
        return v * 100 if v is not None else None

    return {
        "Trailing P/E": round_or_none(extra.get("trailing_pe")),
        "Forward P/E": round_or_none(extra.get("forward_pe")),
        "Market Cap": round_or_none(extra.get("market_cap")),
        "Enterprise Value": round_or_none(extra.get("enterprise_value")),
        "TTM Revenue": round_or_none(extra.get("ttm_revenue")),
        "EBIT Margin": round_or_none(_pct("ebit_margin")),
        "TTM EBITDA": round_or_none(extra.get("ttm_ebitda")),
        "Net Debt": round_or_none(extra.get("net_debt")),
        "Revenue Growth": round_or_none(_pct("revenue_growth")),
        "WACC rf": round_or_none(_pct("wacc_rf")),
        "WACC beta": round_or_none(extra.get("wacc_beta"), 3),
        "WACC ke": round_or_none(_pct("wacc_ke")),
        "WACC kd": round_or_none(_pct("wacc_kd")),
        "WACC tax": round_or_none(_pct("wacc_tax")),
        "WACC E/V": round_or_none(_pct("wacc_ev_ratio")),
        "Peer P/E": round_or_none(extra.get("peer_pe"), 1),
        "Peer EV/Rev": round_or_none(extra.get("peer_ev_rev"), 1),
        "Peer EV/EBITDA": round_or_none(extra.get("peer_ev_ebitda"), 1),
        "Impl Price P/E": round_or_none(extra.get("impl_price_pe")),
        "Impl Price EV/Rev": round_or_none(extra.get("impl_price_ev_rev")),
        "Impl Price EV/EBITDA": round_or_none(extra.get("impl_price_ev_ebitda")),
    }


def build_output(
    ticker: str,
    sector_name: str,
    wacc: float,
    avg_growth: float,
    warnings: list[str],
    signal_quality_score: int,
    signal_quality_label: str,
    current_price: float | None,
    valuations: dict[str, float | None],
    fcf_by_year: dict[int, float | None],
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    average_fair_value = _blend_fair_values(valuations)
    expected_return = None
    if average_fair_value is not None and current_price is not None and current_price > EPSILON:
        expected_return = average_fair_value / current_price - 1

    output: dict[str, Any] = {
        "Kod": clean_ticker(ticker),
        "Sektör": sector_name,
        "Para Birimi": get_currency_symbol(ticker),
        "Sinyal Kalite Skoru": signal_quality_score,
        "Sinyal Güven Seviyesi": signal_quality_label,
        "Güncel Fiyat": round_or_none(current_price),
        "Beklenen Getiri (%)": round_or_none(expected_return * 100 if expected_return is not None else None),
        "WACC": round_or_none(wacc * 100 if wacc is not None else None),
        "Ortalama Büyüme": round_or_none(avg_growth * 100 if avg_growth is not None else None),
        "DCF Değerlemesi": round_or_none(valuations["fv_dcf"]),
        "F/K Değerlemesi": round_or_none(valuations["fv_fk"]),
        "PD/DD Finansal Model": round_or_none(valuations["fv_financial"]),
        "EV/EBITDA Değerlemesi": round_or_none(valuations["fv_ev"]),
        "Rölatif Değerleme": round_or_none(valuations["fv_relative"]),
        "DDM Değerlemesi": round_or_none(valuations["fv_ddm"]),
        "EFK Değerlemesi": round_or_none(valuations["fv_efk"]),
        "NDK Değerlemesi": round_or_none(valuations["fv_ndk"]),
        "Graham Değerlemesi": round_or_none(valuations["fv_graham"]),
        AVERAGE_FAIR_PRICE_LABEL: round_or_none(average_fair_value),
        "Model Kalite Uyarı Sayısı": len(sorted(set(warnings))),
        "Model Kalite Uyarıları": ",".join(sorted(set(warnings))),
    }
    if extra:
        output.update({k: v for k, v in _build_detail_fields(extra).items() if v is not None})
    for year in sorted(fcf_by_year):
        output[f"FCF {year}"] = round_or_none(fcf_by_year[year])
    return output


def _apply_live_multiples(
    params: dict[str, float],
    sector_name: str,
    live_multiples: dict[str, dict[str, float]] | None,
    ticker: str = "",
) -> None:
    from data.peer_multiples import get_ticker_multiples
    ticker_live = get_ticker_multiples(ticker) if ticker else None
    if ticker_live:
        live = ticker_live
    elif live_multiples:
        live = live_multiples.get(sector_name)
    else:
        return
    if live is None:
        return
    if "pe" in live:
        params["pe"] = live["pe"]
    if "ev_ebitda" in live:
        params["ev_ebitda"] = live["ev_ebitda"]
    if "ev_rev" in live:
        params["ev_rev"] = live["ev_rev"]


def _blend_analyst_growth(is_turkish: bool, info: dict[str, Any], hist_growth: float) -> float:
    if is_turkish:
        return hist_growth
    analyst_growth = info.get("earningsGrowth") or info.get("revenueGrowth")
    if analyst_growth is None:
        return hist_growth
    analyst_clamped = max(min(float(analyst_growth), MAX_GROWTH_CAP), MIN_GROWTH_CAP)
    return 0.5 * hist_growth + 0.5 * analyst_clamped


def _filter_dividend(is_turkish: bool, dividend: float | None, current_price: float | None) -> float | None:
    if is_turkish or dividend is None or not current_price or current_price <= EPSILON:
        return dividend
    return dividend if dividend / current_price >= 0.015 else None


def _fetch_consensus_y1(ticker: str) -> float | None:
    try:
        import yfinance as yf
        rev_est = yf.Ticker(ticker).revenue_estimate
        if rev_est is not None and not rev_est.empty and "+1y" in rev_est.index:
            growth_val = rev_est.loc["+1y", "growth"]
            if growth_val is not None and not pd.isna(growth_val):
                return float(growth_val)
    except TICKER_PROCESSING_ERRORS:
        pass
    return None


def _compute_dcf_initial_growth(
    is_turkish: bool,
    consensus_y1: float | None,
    rev_cagr: float | None,
    avg_growth: float,
) -> float:
    if not is_turkish and consensus_y1 is not None:
        return max(min(consensus_y1, MAX_GROWTH_CAP), MIN_GROWTH_CAP)
    return rev_cagr if (not is_turkish and rev_cagr is not None) else avg_growth


def _compute_fv_ev_rev(
    is_financial: bool,
    params: dict[str, float],
    latest_revenue: float | None,
    net_debt: float,
    shares: float,
) -> float | None:
    if is_financial:
        return None
    ev_rev_multiple = params.get("ev_rev", 0.0)
    if not ev_rev_multiple or ev_rev_multiple <= 0:
        return None
    if not latest_revenue or latest_revenue <= 0 or shares <= 0:
        return None
    implied = (ev_rev_multiple * latest_revenue - net_debt) / shares
    return implied if implied > 0 else None


def _build_extra_dict(
    info: dict[str, Any],
    params: dict[str, float],
    margin_profile: dict[str, float],
    is_turkish: bool,
    balance_sheet: pd.DataFrame | None,
    ebitda: float | None,
    net_debt: float,
    rev_cagr: float | None,
    latest_revenue: float | None,
    wacc_components: dict[str, float],
    implied_prices: dict[str, float | None],
) -> dict[str, Any]:
    _equity = info.get("marketCap") or 0.0
    _info_debt = info.get("totalDebt") or 0.0
    _fin_debt = _get_financial_debt(balance_sheet, _info_debt) if not is_turkish else _info_debt
    _total_cap = _equity + _fin_debt
    _ev_ratio = _equity / _total_cap if _total_cap > 0 else None
    return {
        "trailing_pe": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "market_cap": info.get("marketCap"),
        "enterprise_value": info.get("enterpriseValue"),
        "ttm_revenue": latest_revenue,
        "ebit_margin": margin_profile.get("ebit_margin"),
        "ttm_ebitda": ebitda,
        "net_debt": net_debt if not is_turkish else None,
        "revenue_growth": rev_cagr,
        "wacc_rf": params.get("risk_free_rate"),
        "wacc_beta": info.get("beta") or 1.0,
        "wacc_ke": wacc_components["ke"],
        "wacc_kd": wacc_components["kd"],
        "wacc_tax": wacc_components["tax"],
        "wacc_ev_ratio": _ev_ratio,
        "peer_pe": params.get("pe"),
        "peer_ev_rev": params.get("ev_rev"),
        "peer_ev_ebitda": params.get("ev_ebitda"),
        "impl_price_pe": implied_prices["pe"],
        "impl_price_ev_rev": implied_prices["ev_rev"],
        "impl_price_ev_ebitda": implied_prices["ev"],
    }


def _resolve_avg_growth(
    is_turkish: bool,
    rev_cagr: float | None,
    fcf_by_year: dict[int, float | None],
    info: dict[str, Any],
    wacc: float,
) -> float:
    if not is_turkish and rev_cagr is not None:
        return clamp_growth(rev_cagr, wacc)
    hist_growth = rev_cagr if rev_cagr is not None else compute_avg_growth(list(fcf_by_year.values()))
    return clamp_growth(_blend_analyst_growth(is_turkish, info, hist_growth), wacc)


def _build_valuations(
    is_financial: bool,
    is_turkish: bool,
    params: dict[str, float],
    info: dict[str, Any],
    cost_of_equity: float,
    dcf_inputs: dict[str, Any],
    precomputed: dict[str, Any],
) -> dict[str, float | None]:
    fv_dcf = None if is_financial else calculate_dcf_fair_value(
        latest_revenue=dcf_inputs["latest_revenue"],
        margin_profile=dcf_inputs["margin_profile"],
        initial_growth=dcf_inputs["initial_growth"],
        wacc=dcf_inputs["wacc"],
        debt=dcf_inputs["debt"],
        cash=dcf_inputs["cash"],
        shares=dcf_inputs["shares"],
        terminal_growth=params["terminal_growth"],
        tax_rate=dcf_inputs["tax_rate"],
    )
    return {
        "fv_dcf": fv_dcf,
        "fv_fk": precomputed["fv_fk"],
        "fv_financial": calculate_financial_fair_value(info, params, cost_of_equity) if is_financial else None,
        "fv_ev": precomputed["fv_ev"],
        "fv_relative": round_or_none(precomputed["fv_relative"]),
        "fv_ddm": calculate_ddm_fair_value(precomputed["dividend"], dcf_inputs["wacc"], params["ddm_growth"]),
        "fv_efk": precomputed["fv_efk"] if is_turkish else None,
        "fv_ndk": precomputed["fv_ndk"] if is_turkish else None,
        "fv_graham": graham_valuation(precomputed["eps"], params["pe"], params["bond_yield_2"]) if is_turkish else None,
    }


def _prepare_currency_context(
    ticker: str,
    info: dict[str, Any],
    warnings: list[str],
    sector_name: str,
    live_multiples: dict[str, dict[str, float]] | None,
) -> tuple[bool, bool, float | None, dict[str, float], dict[str, Any]]:
    is_turkish = is_turkish_ticker(ticker)
    financial_currency = _detect_reporting_currency(ticker, info) if is_turkish else "USD"
    is_foreign_reporter = is_turkish and financial_currency in ("EUR", "USD")
    params = get_country_params(ticker, financial_currency)
    _apply_live_multiples(params, sector_name, live_multiples, ticker=ticker)

    fx_rate = _fetch_fx_rate(f"{financial_currency}TRY=X", warnings) if is_foreign_reporter else None
    if is_foreign_reporter and fx_rate is None:
        warnings.append(
            f"{financial_currency}/TRY kuru alınamadı; "
            "DCF/EFK/NDK/DDM hesaplanamıyor — TL parametreleri kullanılıyor."
        )
        params = get_country_params(ticker, "TRY")
        _apply_live_multiples(params, sector_name, live_multiples, ticker=ticker)

    wacc_info = _normalize_wacc_info(info, fx_rate) if is_foreign_reporter else info
    return is_turkish, is_foreign_reporter, fx_rate, params, wacc_info


def _normalize_wacc_info(info: dict[str, Any], fx_rate: float | None) -> dict[str, Any]:
    if fx_rate is None or fx_rate <= 1:
        return info
    return {
        **info,
        "marketCap": (info.get("marketCap") or 0.0) / fx_rate,
        "totalDebt": (info.get("totalDebt") or 0.0) / fx_rate,
    }


def _normalize_paid_capital_values(
    fair_value_efk: float | None,
    fair_value_ndk: float | None,
    is_foreign_reporter: bool,
    fx_rate: float | None,
) -> tuple[float | None, float | None]:
    if not is_foreign_reporter:
        return fair_value_efk, fair_value_ndk
    if fx_rate is None or fx_rate <= 1:
        return None, None
    converted_efk = fair_value_efk * fx_rate if fair_value_efk is not None else None
    converted_ndk = fair_value_ndk * fx_rate if fair_value_ndk is not None else None
    return converted_efk, converted_ndk


def _normalize_dcf_balance(
    debt: float,
    cash: float,
    is_foreign_reporter: bool,
    fx_rate: float | None,
) -> tuple[float, float]:
    if not is_foreign_reporter or fx_rate is None or fx_rate <= 1:
        return debt, cash
    return debt / fx_rate, cash / fx_rate


def _finalize_currency_valuations(
    valuations: dict[str, float | None],
    is_foreign_reporter: bool,
    fx_rate: float | None,
) -> None:
    if not is_foreign_reporter:
        return
    if fx_rate is None or fx_rate <= 1:
        valuations["fv_dcf"] = None
        valuations["fv_ddm"] = None
        return
    dcf_value = valuations.get("fv_dcf")
    if dcf_value is not None:
        valuations["fv_dcf"] = dcf_value * fx_rate


def value_ticker(
    ticker: str,
    live_multiples: dict[str, dict[str, float]] | None = None,
) -> dict[str, Any]:
    bundle = fetch_ticker_bundle(ticker)
    info = normalized_info(bundle)
    warnings = validate_bundle(bundle, info)
    income_stmt = bundle.financials
    cash_flow = bundle.cashflow
    balance_sheet = bundle.balance_sheet

    sector_name, is_financial = resolve_sector(ticker)
    is_turkish, is_foreign_reporter, fx_rate, params, wacc_info = _prepare_currency_context(
        ticker, info, warnings, sector_name, live_multiples
    )

    # Foreign-currency BIST tickers: pass financials so WACC uses effective kd/tax.
    wacc, effective_tax_rate, effective_kd = calculate_wacc(
        wacc_info, params,
        income_stmt=income_stmt if (not is_turkish or is_foreign_reporter) else None,
        balance_sheet=balance_sheet if (not is_turkish or is_foreign_reporter) else None,
    )

    fcf_by_year = build_fcf_by_year(income_stmt, cash_flow, effective_tax_rate)
    latest_revenue = _get_latest_revenue(income_stmt)
    margin_profile = compute_margin_profile(income_stmt, cash_flow)
    rev_cagr = compute_revenue_cagr(income_stmt)
    avg_growth = _resolve_avg_growth(is_turkish, rev_cagr, fcf_by_year, info, wacc)

    shares = info.get("sharesOutstanding") or info.get("floatShares") or 1
    # debt/cash from yfinance info are TRY for all BIST tickers — used as-is for
    # relative valuation (ebitda from info is also TRY).
    debt = info.get("totalDebt") or 0
    cash = info.get("totalCash") or 0
    eps = info.get("trailingEps")
    ebitda = get_ebitda_safely(info, income_stmt, cash_flow)
    dividend = _filter_dividend(is_turkish, info.get("dividendRate"), info.get("currentPrice"))
    fair_value_efk, fair_value_ndk = calculate_paid_capital_valuations(income_stmt, shares)
    fair_value_efk, fair_value_ndk = _normalize_paid_capital_values(
        fair_value_efk, fair_value_ndk, is_foreign_reporter, fx_rate
    )
    cost_of_equity = params["risk_free_rate"] + (info.get("beta") or 1.0) * params["market_premium"]

    consensus_y1 = _fetch_consensus_y1(ticker) if not is_turkish else None
    dcf_initial_growth = _compute_dcf_initial_growth(is_turkish, consensus_y1, rev_cagr, avg_growth)

    import numpy as _np
    net_debt = debt - cash
    fv_fk_val = calculate_fk_fair_value(eps, params["pe"])
    fv_ev_val = None if is_financial else calculate_ev_ebitda_fair_value(ebitda, params["ev_ebitda"], debt, cash, shares)
    fv_ev_rev_val = _compute_fv_ev_rev(is_financial, params, latest_revenue, net_debt, shares)

    rel_candidates = [v for v in [fv_fk_val, fv_ev_rev_val, fv_ev_val] if v is not None and v > 0]
    fv_relative_val = float(_np.nanmedian(rel_candidates)) if rel_candidates else None

    dcf_debt, dcf_cash = _normalize_dcf_balance(debt, cash, is_foreign_reporter, fx_rate)

    valuations = _build_valuations(
        is_financial=is_financial,
        is_turkish=is_turkish,
        params=params,
        info=info,
        cost_of_equity=cost_of_equity,
        dcf_inputs={
            "latest_revenue": latest_revenue,
            "margin_profile": margin_profile,
            "initial_growth": dcf_initial_growth,
            "wacc": wacc,
            "debt": dcf_debt,
            "cash": dcf_cash,
            "shares": shares,
            "tax_rate": effective_tax_rate,
        },
        precomputed={
            "fv_fk": fv_fk_val,
            "fv_ev": fv_ev_val,
            "fv_relative": fv_relative_val,
            "dividend": dividend,
            "fv_efk": fair_value_efk,
            "fv_ndk": fair_value_ndk,
            "eps": eps,
        },
    )
    _finalize_currency_valuations(valuations, is_foreign_reporter, fx_rate)
    signal_quality_score, signal_quality_label = compute_signal_quality_score(
        valuations=valuations,
        warnings=warnings,
        is_financial=is_financial,
        is_turkish=is_turkish,
    )
    extra = _build_extra_dict(
        info=info, params=params, margin_profile=margin_profile,
        is_turkish=is_turkish, balance_sheet=balance_sheet,
        ebitda=ebitda, net_debt=net_debt, rev_cagr=rev_cagr,
        latest_revenue=latest_revenue,
        wacc_components={"ke": cost_of_equity, "kd": effective_kd, "tax": effective_tax_rate},
        implied_prices={"pe": fv_fk_val, "ev_rev": fv_ev_rev_val, "ev": fv_ev_val},
    )
    return build_output(
        ticker=ticker,
        sector_name=sector_name,
        wacc=wacc,
        avg_growth=avg_growth,
        warnings=warnings,
        signal_quality_score=signal_quality_score,
        signal_quality_label=signal_quality_label,
        current_price=info.get("currentPrice"),
        valuations=valuations,
        fcf_by_year=fcf_by_year,
        extra=extra,
    )


def load_tickers(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as source:
            tickers = [line.strip() for line in source if line.strip()]
        print("Kaynak:", path)
        return tickers
    except FileNotFoundError:
        print("❌ coverage.txt yok")
        return []


def run_valuation(tickers: list[str]) -> list[dict[str, Any]]:
    # Fetch live peer multiples once for US runs to replace static sector defaults
    has_us = any(not is_turkish_ticker(t) for t in tickers)
    live_multiples: dict[str, dict[str, float]] = {}
    if has_us:
        print("[peer_multiples] Canlı sektör katları çekiliyor…")
        try:
            live_multiples = get_live_sector_multiples()
            print(f"[peer_multiples] {len(live_multiples)} sektör verisi alındı.")
        except TICKER_PROCESSING_ERRORS as exc:
            print(f"[peer_multiples] Hata — statik değerlere dönülüyor: {exc}")

    results: list[dict[str, Any]] = []
    for ticker_code in tickers:
        print("→", ticker_code, "analiz")
        try:
            result_row = value_ticker(ticker_code, live_multiples=live_multiples)
            if result_row:
                results.append(result_row)
        except TICKER_PROCESSING_ERRORS as error:
            print("  hata:", error)
        if TICKER_DELAY_SECONDS > 0:
            time.sleep(TICKER_DELAY_SECONDS)
    return results
