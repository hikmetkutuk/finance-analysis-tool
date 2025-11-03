# -*- coding: utf-8 -*-

import yfinance as yf
import pandas as pd
from typing import Iterable, Optional, Dict, Any
import time


# ------------------------------
# SABITLER
# ------------------------------

# Türkiye (BIST)
RISK_FREE_RATE_TR = 0.25
MARKET_PREMIUM_TR = 0.07
COST_OF_DEBT_TR = 0.3
TAX_RATE_TR = 0.25

# ABD
RISK_FREE_RATE_US = 0.045
MARKET_PREMIUM_US = 0.055
COST_OF_DEBT_US = 0.06
TAX_RATE_US = 0.21

TERMINAL_GROWTH = 0.025
YEARS_PROJECTION = 5

SECTOR_PE_TR = 8.0
SECTOR_PE_US = 25.0

SECTOR_EV_EBITDA_TR = 6.0
SECTOR_EV_EBITDA_US = 10.0
DDM_GROWTH_DEFAULT = 0.025

MAX_GROWTH_CAP = 0.50     # 50% ↑
MIN_GROWTH_CAP = -0.50    # -50%

SECTOR_OVERRIDES = {
    "AKBNK.IS": {'pe': 5.95},
    "ISCTR.IS": {'pe': 5.95},
    "YKBNK.IS": {'pe': 5.95},
    "VAKBN.IS": {'pe': 5.95},
    "HALKB.IS": {'pe': 5.95},
    "TSKB.IS": {'pe': 5.95},
    "GARAN.IS": {'pe': 5.95},
    "AKSEN.IS": {'pe': 29.91, 'ev_ebitda': 3.73},
    "ENJSA.IS": {'pe': 29.91, 'ev_ebitda': 3.73},
    "PETKM.IS": {'pe': 29.91, 'ev_ebitda': 3.73},
    "TUPRS.IS": {'pe': 29.91, 'ev_ebitda': 3.73},
    "ASTOR.IS": {'pe': 29.91, 'ev_ebitda': 3.73},
    "ARCLK.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "ASELS.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "BRSAN.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "CIMSA.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "EGEEN.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "KOZAA.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "KOZAL.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "ENKAI.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "TKFEN.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "AKSA.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "OTKAR.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "GUBRF.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "HEKTS.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "SASA.IS": {'pe': 56.62, 'ev_ebitda': 71.54},
    "TOASO.IS": {'pe': 45.29, 'ev_ebitda': -12.47},
    "FROTO.IS": {'pe': 45.29, 'ev_ebitda': -12.47},
    "DOAS.IS": {'pe': 45.29, 'ev_ebitda': -12.47},
    "BIMAS.IS": {'pe': 20.88, 'ev_ebitda': 14.08},
    "MGROS.IS": {'pe': 20.88, 'ev_ebitda': 14.08},
    "PGSUS.IS": {'pe': 11.92, 'ev_ebitda': 51.69},
    "THYAO.IS": {'pe': 11.92, 'ev_ebitda': 51.69},
    "TAVHL.IS": {'pe': 11.92, 'ev_ebitda': 51.69},
    "ANSGR.IS": {'pe': 3.89, 'ev_ebitda': -2.3},
    "CCOLA.IS": {'pe': 12.25, 'ev_ebitda': 8.74},
    "AEFES.IS": {'pe': 12.25, 'ev_ebitda': 8.74},
    "KCHOL.IS": {'pe': 356.88, 'ev_ebitda': -14.19},
    "SAHOL.IS": {'pe': 356.88, 'ev_ebitda': -14.19},
    "AGHOL.IS": {'pe': 356.88, 'ev_ebitda': -14.19},
    "ALARK.IS": {'pe': 356.88, 'ev_ebitda': -14.19},
    "DOHOL.IS": {'pe': 356.88, 'ev_ebitda': -14.19},
    "BINHO.IS": {'pe': 356.88, 'ev_ebitda': -14.19},
    "ECILC.IS": {'pe': 356.88, 'ev_ebitda': -14.19},
    "TCELL.IS": {'pe': 15.05, 'ev_ebitda': 4.59},
    "TTKOM.IS": {'pe': 15.05, 'ev_ebitda': 4.59},
    "AAPL": {'pe': 86.01, 'ev_ebitda': -60.6},
    "GOOG": {'pe': 86.01, 'ev_ebitda': -60.6},
    "GOOGL": {'pe': 86.01, 'ev_ebitda': -60.6},
    "MSFT": {'pe': 86.01, 'ev_ebitda': -60.6},
    "META": {'pe': 86.01, 'ev_ebitda': -60.6},
    "NET": {'pe': 86.01, 'ev_ebitda': -60.6},
    "PLTR": {'pe': 86.01, 'ev_ebitda': -60.6},
    "ORCL": {'pe': 86.01, 'ev_ebitda': -60.6},
    "ADBE": {'pe': 86.01, 'ev_ebitda': -60.6},
    "CRM": {'pe': 86.01, 'ev_ebitda': -60.6},
    "AMZN": {'pe': 86.01, 'ev_ebitda': -60.6},
    "CSCO": {'pe': 86.01, 'ev_ebitda': -60.6},
    "DELL": {'pe': 86.01, 'ev_ebitda': -60.6},
    "QCOM": {'pe': 60.06, 'ev_ebitda': 32.17},
    "AMD": {'pe': 60.06, 'ev_ebitda': 32.17},
    "NVDA": {'pe': 60.06, 'ev_ebitda': 32.17},
    "INTL": {'pe': 60.06, 'ev_ebitda': 32.17},
    "BABA": {'pe': 19.61, 'ev_ebitda': 16.24},
    "AVGO": {'pe': 60.06, 'ev_ebitda': 32.17},
    "DIS": {'pe': 32.18, 'ev_ebitda': 24.84},
    "NFLX": {'pe': 32.18, 'ev_ebitda': 24.84},
    "LLY": {'pe': 21.17, 'ev_ebitda': 13.67},
    "JNJ": {'pe': 21.17, 'ev_ebitda': 13.67},
    "MRK": {'pe': 21.17, 'ev_ebitda': 13.67},
    "UNH": {'pe': 21.17, 'ev_ebitda': 13.67},
    "PFE": {'pe': 21.17, 'ev_ebitda': 13.67},
    "NVO": {'pe': 21.17, 'ev_ebitda': 13.67},
    "TMO": {'pe': 21.17, 'ev_ebitda': 13.67},
    "JPM": {'pe': 24.63, 'ev_ebitda': 24.52},
    "WFC": {'pe': 24.63, 'ev_ebitda': 24.52},
    "MA": {'pe': 24.63, 'ev_ebitda': 24.52},
    "V": {'pe': 24.63, 'ev_ebitda': 24.52},
    "XOM": {'pe': 16.62, 'ev_ebitda': 8.42},
    "MCD": {'pe': 31.68, 'ev_ebitda': 22.77},
    "WMT": {'pe': 31.68, 'ev_ebitda': 22.77},
    "COST": {'pe': 31.68, 'ev_ebitda': 22.77},
    "HD": {'pe': 31.68, 'ev_ebitda': 22.77},
    "KO": {'pe': 31.68, 'ev_ebitda': 22.77},
    "PEP": {'pe': 31.68, 'ev_ebitda': 22.77},
    "BA": {'pe': 15.8, 'ev_ebitda': -10.68},
    "L": {'pe': 15.8, 'ev_ebitda': -10.68},
    "TSLA": {'pe': 312.71, 'ev_ebitda': 138.5},
}


# ------------------------------
# Helpers
# ------------------------------

def safe_div(a, b):
    try:
        if a is None or b in (None, 0): return None
        return float(a) / float(b)
    except:
        return None


def format_number_tr(v):
    if v is None: return ""
    try:
        return "{:,.2f}".format(float(v)).replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return ""


def format_percent_tr(v):
    if v is None: return ""
    try:
        return f"{v*100:,.2f}%".replace(",", "X").replace(".", ",").replace("X", ".")
    except:
        return ""


def get_currency_symbol(t):
    return "₺" if t.upper().endswith(".IS") else "$"


def clean_ticker(ticker: str) -> str:
    return ticker.replace(".IS", "") if ticker.upper().endswith(".IS") else ticker

# ------------------------------
# Growth Stabilizer ✅
# ------------------------------

def compute_avg_growth(series):
    """FCF büyüme ortalamasını hesaplarken aşırı uçları kırpıyoruz."""
    arr = [x for x in series if x is not None]
    if len(arr) < 2:
        return 0.05

    growths = []
    for i in range(1, len(arr)):
        if arr[i - 1] and arr[i - 1] != 0:
            g = arr[i] / arr[i - 1] - 1

            # Growth CAP ✅
            g = max(min(g, MAX_GROWTH_CAP), MIN_GROWTH_CAP)
            growths.append(g)

    return sum(growths) / len(growths) if growths else 0.05


# ------------------------------
# WACC
# ------------------------------

def get_country_params(ticker: str):
    if ticker.upper().endswith(".IS"):
        return dict(
            RISK_FREE_RATE=RISK_FREE_RATE_TR,
            MARKET_PREMIUM=MARKET_PREMIUM_TR,
            COST_OF_DEBT=COST_OF_DEBT_TR,
            TAX_RATE=TAX_RATE_TR,
            PE=SECTOR_OVERRIDES.get(ticker, {}).get("pe", SECTOR_PE_TR),
            EV_EBITDA=SECTOR_OVERRIDES.get(ticker, {}).get("ev_ebitda", SECTOR_EV_EBITDA_TR),
        )
    else:
        return dict(
            RISK_FREE_RATE=RISK_FREE_RATE_US,
            MARKET_PREMIUM=MARKET_PREMIUM_US,
            COST_OF_DEBT=COST_OF_DEBT_US,
            TAX_RATE=TAX_RATE_US,
            PE=SECTOR_OVERRIDES.get(ticker, {}).get("pe", SECTOR_PE_US),
            EV_EBITDA=SECTOR_OVERRIDES.get(ticker, {}).get("ev_ebitda", SECTOR_EV_EBITDA_US),
        )


def calculate_wacc(info, ticker):
    p = get_country_params(ticker)
    beta = info.get("beta", 1.0) or 1.0
    equity = info.get("marketCap", 0.0) or 0.0
    debt   = info.get("totalDebt", 0.0) or 0.0
    total  = equity + debt if (equity + debt) > 0 else 1

    cost_of_equity = p["RISK_FREE_RATE"] + beta * p["MARKET_PREMIUM"]
    cost_of_debt   = info.get("interestRate", p["COST_OF_DEBT"]) or p["COST_OF_DEBT"]
    tax_rate       = p["TAX_RATE"]

    return (equity/total)*cost_of_equity + (debt/total)*cost_of_debt*(1 - tax_rate)


# ------------------------------
# Annual DS helper
# ------------------------------

def _is_df(df):
    return isinstance(df, pd.DataFrame) and not df.empty


def _annual_value_for_year(df, row_names, target_year):
    if not _is_df(df):
        return None
    row = next((r for r in row_names if r in df.index), None)
    if row is None: 
        return None
    for col in df.columns:
        if getattr(col, "year", None) == target_year:
            v=df.loc[row, col]
            return float(v) if pd.notna(v) else None
    return None


# ------------------------------
# EBITDA
# ------------------------------

def get_ebitda_safely(info, income_stmt, cash_flow, year_hint=2024):

    e = info.get("ebitda")
    if isinstance(e, (int,float)) and e != 0:
        return float(e)

    op = _annual_value_for_year(income_stmt, ["Operating Income","Total Operating Income"], year_hint) or 0
    da = _annual_value_for_year(cash_flow, ["Depreciation And Amortization","Depreciation"], year_hint) or 0
    e2 = op + da

    # scale safety
    if e2 > 1e12:
        e2 /= 1_000_000

    return float(e2)


# ------------------------------
# FCF
# ------------------------------

def calculate_fcf(op, tax, depr, capex, rec, inv, liab,
                  prec, pinv, pliab, *, tax_rate_fallback):
    if not op:
        return None
    eff = abs(tax/op) if tax and op!=0 else tax_rate_fallback
    nopat = op*(1-eff)
    dWC   = ((rec or 0)+(inv or 0)-(liab or 0)) - ((prec or 0)+(pinv or 0)-(pliab or 0))
    return nopat + (depr or 0) - (capex or 0) - dWC


# ------------------------------
# MAIN
# ------------------------------

def value_ticker(ticker):

    stock = yf.Ticker(ticker)
    info = stock.info or {}
    income_stmt = stock.financials
    balance_sheet = stock.balance_sheet
    cash_flow = stock.cashflow

    params = get_country_params(ticker)
    wacc   = calculate_wacc(info, ticker)

    fcf_by_year = {}
    for year in range(2021, 2026):
        fcf_by_year[year] = calculate_fcf(
            _annual_value_for_year(income_stmt, ["Operating Income","Total Operating Income"], year),
            _annual_value_for_year(income_stmt, ["Tax Provision","Income Tax Expense"], year),
            _annual_value_for_year(cash_flow, ["Depreciation And Amortization","Depreciation"], year),
            _annual_value_for_year(cash_flow, ["Capital Expenditures"], year),
            _annual_value_for_year(balance_sheet, ["Accounts Receivable","Total Receivables"], year),
            _annual_value_for_year(balance_sheet, ["Inventory","Inventories"], year),
            _annual_value_for_year(balance_sheet, ["Total Liabilities","Total Liabilities Net Minority Interest"], year),
            _annual_value_for_year(balance_sheet, ["Accounts Receivable","Total Receivables"], year-1),
            _annual_value_for_year(balance_sheet, ["Inventory","Inventories"], year-1),
            _annual_value_for_year(balance_sheet, ["Total Liabilities","Total Liabilities Net Minority Interest"], year-1),
            tax_rate_fallback = params["TAX_RATE"]
        )

    avg_growth = compute_avg_growth(list(fcf_by_year.values()))

    # growth must not exceed WACC
    if avg_growth >= wacc:
        avg_growth = wacc - 0.01
        avg_growth = max(min(avg_growth,MAX_GROWTH_CAP),MIN_GROWTH_CAP)


    # last valid fcf
    past_fcfs = [v for v in fcf_by_year.values() if v is not None]
    last_fcf  = past_fcfs[-1] if past_fcfs else None

    projected_fcfs = [last_fcf*((1+avg_growth)**i) for i in range(1,YEARS_PROJECTION+1)] if last_fcf else []
    pv_fcfs        = [fcf/((1+wacc)**(i+1)) for i,fcf in enumerate(projected_fcfs)] if projected_fcfs else []

    terminal_value = None
    pv_term        = None
    if projected_fcfs and wacc > TERMINAL_GROWTH:
        terminal_value = projected_fcfs[-1]*(1+TERMINAL_GROWTH)/(wacc-TERMINAL_GROWTH)
        pv_term        = terminal_value/((1+wacc)**YEARS_PROJECTION)

    enterprise_value = sum(pv_fcfs)+(pv_term or 0) if pv_fcfs else None
    shares = info.get("sharesOutstanding") or info.get("floatShares") or 1
    debt   = info.get("totalDebt",0) or 0
    cash   = info.get("totalCash",0) or 0

    fv_dcf = safe_div((enterprise_value - debt + cash) if enterprise_value is not None else None, shares)

    pe_sector = params["PE"]

    eps = info.get("trailingEps")
    fv_fk = None
    if eps is not None and eps > 0 and pe_sector is not None and pe_sector > 0:
        fv_fk = eps * pe_sector

    ev_mult = params["EV_EBITDA"]
    ebitda = get_ebitda_safely(info, income_stmt, cash_flow)

    fv_ev = None
    if ebitda is not None and ebitda > 0 and ev_mult is not None and ev_mult > 0:
        ent_ev = ebitda * ev_mult
        fv_ev = safe_div(ent_ev - debt + cash, shares)
    else:
        fv_ev = None

    dividend = info.get("dividendRate",0) or 0
    fv_ddm   = None
    if dividend>0 and wacc>DDM_GROWTH_DEFAULT:
        fv_ddm = dividend*(1+DDM_GROWTH_DEFAULT)/(wacc-DDM_GROWTH_DEFAULT)

    vals = [v for v in [fv_dcf, fv_fk, fv_ev, fv_ddm] if v is not None and v > 0]
    fv_avg = sum(vals)/len(vals) if vals else None

    out = {
        "Kod": clean_ticker(ticker),
        "Para Birimi": get_currency_symbol(ticker),
        "WACC": format_percent_tr(wacc),
        "Ortalama Büyüme": format_percent_tr(avg_growth),
        "DCF Değerlemesi": format_number_tr(fv_dcf),
        "F/K Değerlemesi": format_number_tr(fv_fk),
        "EV/EBITDA Değerlemesi": format_number_tr(fv_ev),
        "DDM Değerlemesi": format_number_tr(fv_ddm),
        "Ortalama Adil Fiyat": format_number_tr(fv_avg),
    }

    for y in sorted(fcf_by_year.keys()):
        out[f"FCF {y}"] = format_number_tr(fcf_by_year[y])

    return out


# ------------------------------
# RUN
# ------------------------------

if __name__=="__main__":
    tickers=[]
    fname="coverage.txt"

    try:
        with open(fname,"r",encoding="utf-8") as f:
            tickers=[x.strip() for x in f if x.strip()]
            print("Kaynak:",fname)
    except:
        print("❌ coverage.txt yok")

    results=[]
    for t in tickers:
        print("→",t,"analiz")
        try:
            r=value_ticker(t)
            if r: results.append(r)
        except Exception as e:
            print("  hata:",e)
        time.sleep(1)

    if results:
        df=pd.DataFrame(results)
        c=[c for c in df.columns if c!="Ortalama Adil Fiyat"]
        c.append("Ortalama Adil Fiyat")
        df=df[c]
        df.to_excel("valuation.xlsx",index=False,engine="openpyxl")
        print("✅ yazıldı → valuation.xlsx")
    else:
        print("⚠️ sonuç yok")
