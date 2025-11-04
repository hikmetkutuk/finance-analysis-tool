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

BOND_YIELD_2_TR = 0.398
BOND_YIELD_2_US = 0.0359

MAX_GROWTH_CAP = 0.50     # 50% ↑
MIN_GROWTH_CAP = -0.50    # -50%

SECTOR_OVERRIDES = {
    "AKBNK.IS": {'pe': 5.5},
    "ISCTR.IS": {'pe': 5.5},
    "YKBNK.IS": {'pe': 5.5},
    "VAKBN.IS": {'pe': 5.5},
    "HALKB.IS": {'pe': 5.5},
    "TSKB.IS": {'pe': 5.5},
    "GARAN.IS": {'pe': 5.5},
    "ALBRK.IS": {'pe': 5.5},
    "AKSEN.IS": {'pe': 41.02, 'ev_ebitda': 12.87},
    "ENJSA.IS": {'pe': 41.02, 'ev_ebitda': 12.87},
    "ASTOR.IS": {'pe': 41.02, 'ev_ebitda': 12.87},
    "ZOREN.IS": {'pe': 41.02, 'ev_ebitda': 12.87},
    "GWIND.IS": {'pe': 41.02, 'ev_ebitda': 12.87},
    "CWENE.IS": {'pe': 41.02, 'ev_ebitda': 12.87},
    "SMRTG.IS": {'pe': 41.02, 'ev_ebitda': 12.87},
    "TATEN.IS": {'pe': 41.02, 'ev_ebitda': 12.87},
    "PETKM.IS": {'pe': 19.03, 'ev_ebitda': 6.67},
    "TUPRS.IS": {'pe': 19.03, 'ev_ebitda': 6.67},
    "IPEKE.IS": {'pe': 19.03, 'ev_ebitda': 6.67},
    "BRSAN.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "EGEEN.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "KOZAA.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "KOZAL.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "ENKAI.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "AKSA.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "GUBRF.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "HEKTS.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "SASA.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "CEMTS.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "KCAER.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "KRDMD.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "ISDMR.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "EREGL.IS": {'pe': 49.82, 'ev_ebitda': 67.3},
    "ARCLK.IS": {'ev_ebitda': 15.87},
    "VESTL.IS": {'ev_ebitda': 15.87},
    "VESBE.IS": {'ev_ebitda': 15.87},
    "ASELS.IS": {'pe': 47.74, 'ev_ebitda': 16.42},
    "ALTNY.IS": {'pe': 47.74, 'ev_ebitda': 16.42},
    "FORTE.IS": {'pe': 47.74, 'ev_ebitda': 16.42},
    "ONRYT.IS": {'pe': 47.74, 'ev_ebitda': 16.42},
    "KAREL.IS": {'pe': 47.74, 'ev_ebitda': 16.42},
    "CIMSA.IS": {'pe': 41.47, 'ev_ebitda': 27.21},
    "GOLTS.IS": {'pe': 41.47, 'ev_ebitda': 27.21},
    "BOBET.IS": {'pe': 41.47, 'ev_ebitda': 27.21},
    "LMKDC.IS": {'pe': 41.47, 'ev_ebitda': 27.21},
    "OYAKC.IS": {'pe': 41.47, 'ev_ebitda': 27.21},
    "KONYA.IS": {'pe': 41.47, 'ev_ebitda': 27.21},
    "BUCIM.IS": {'pe': 41.47, 'ev_ebitda': 27.21},
    "AFYON.IS": {'pe': 41.47, 'ev_ebitda': 27.21},
    "NUHCM.IS": {'pe': 41.47, 'ev_ebitda': 27.21},
    "TOASO.IS": {'pe': 33.17, 'ev_ebitda': 0.76},
    "FROTO.IS": {'pe': 33.17, 'ev_ebitda': 0.76},
    "DOAS.IS": {'pe': 33.17, 'ev_ebitda': 0.76},
    "OTKAR.IS": {'pe': 33.17, 'ev_ebitda': 0.76},
    "TTRAK.IS": {'pe': 33.17, 'ev_ebitda': 0.76},
    "BIMAS.IS": {'pe': 20.74, 'ev_ebitda': 7.1},
    "MGROS.IS": {'pe': 20.74, 'ev_ebitda': 7.1},
    "TKNSA.IS": {'pe': 20.74, 'ev_ebitda': 7.1},
    "SOKM.IS": {'pe': 20.74, 'ev_ebitda': 7.1},
    "PGSUS.IS": {'pe': 11.9, 'ev_ebitda': 41.54},
    "THYAO.IS": {'pe': 11.9, 'ev_ebitda': 41.54},
    "TAVHL.IS": {'pe': 11.9, 'ev_ebitda': 41.54},
    "CLEBI.IS": {'pe': 11.9, 'ev_ebitda': 41.54},
    "ANSGR.IS": {'pe': 18.12, 'ev_ebitda': 1.72},
    "AGESA.IS": {'pe': 18.12, 'ev_ebitda': 1.72},
    "TURSG.IS": {'pe': 18.12, 'ev_ebitda': 1.72},
    "ANHYT.IS": {'pe': 18.12, 'ev_ebitda': 1.72},
    "ULUUN.IS": {'pe': 10.7, 'ev_ebitda': 8.33},
    "ULKER.IS": {'pe': 10.7, 'ev_ebitda': 8.33},
    "KRVGD.IS": {'pe': 10.7, 'ev_ebitda': 8.33},
    "YYLGD.IS": {'pe': 10.7, 'ev_ebitda': 8.33},
    "GOKNR.IS": {'pe': 10.7, 'ev_ebitda': 8.33},
    "OBAMS.IS": {'pe': 10.7, 'ev_ebitda': 8.33},
    "CCOLA.IS": {'pe': 12.46, 'ev_ebitda': 8.31},
    "AEFES.IS": {'pe': 12.46, 'ev_ebitda': 8.31},
    "TBORG.IS": {'pe': 12.46, 'ev_ebitda': 8.31},
    "ELITE.IS": {'pe': 12.46, 'ev_ebitda': 8.31},
    "ECILC.IS": {'pe': 20.92, 'ev_ebitda': -13.81},
    "LKMNH.IS": {'pe': 20.92, 'ev_ebitda': -13.81},
    "MPARK.IS": {'pe': 20.92, 'ev_ebitda': -13.81},
    "SELEC.IS": {'pe': 20.92, 'ev_ebitda': -13.81},
    "KCHOL.IS": {'pe': 364.17, 'ev_ebitda': 3.85},
    "SAHOL.IS": {'pe': 364.17, 'ev_ebitda': 3.85},
    "AGHOL.IS": {'pe': 364.17, 'ev_ebitda': 3.85},
    "ALARK.IS": {'pe': 364.17, 'ev_ebitda': 3.85},
    "DOHOL.IS": {'pe': 364.17, 'ev_ebitda': 3.85},
    "BINHO.IS": {'pe': 364.17, 'ev_ebitda': 3.85},
    "TKFEN.IS": {'pe': 364.17, 'ev_ebitda': 3.85},
    "BERA.IS": {'pe': 364.17, 'ev_ebitda': 3.85},
    "TCELL.IS": {'pe': 14.92, 'ev_ebitda': 4.51},
    "TTKOM.IS": {'pe': 14.92, 'ev_ebitda': 4.51},
    "AAPL": {'pe': 89.89, 'ev_ebitda': -55.65},
    "GOOG": {'pe': 89.89, 'ev_ebitda': -55.65},
    "GOOGL": {'pe': 89.89, 'ev_ebitda': -55.65},
    "MSFT": {'pe': 89.89, 'ev_ebitda': -55.65},
    "META": {'pe': 89.89, 'ev_ebitda': -55.65},
    "NET": {'pe': 89.89, 'ev_ebitda': -55.65},
    "PLTR": {'pe': 89.89, 'ev_ebitda': -55.65},
    "ORCL": {'pe': 89.89, 'ev_ebitda': -55.65},
    "ADBE": {'pe': 89.89, 'ev_ebitda': -55.65},
    "CRM": {'pe': 89.89, 'ev_ebitda': -55.65},
    "AMZN": {'pe': 89.89, 'ev_ebitda': -55.65},
    "CSCO": {'pe': 89.89, 'ev_ebitda': -55.65},
    "DELL": {'pe': 89.89, 'ev_ebitda': -55.65},
    "QCOM": {'pe': 60.23, 'ev_ebitda': 32.52},
    "AMD": {'pe': 60.23, 'ev_ebitda': 32.52},
    "NVDA": {'pe': 60.23, 'ev_ebitda': 32.52},
    "INTL": {'pe': 60.23, 'ev_ebitda': 32.52},
    "BABA": {'pe': 19.34, 'ev_ebitda': 15.97},
    "AVGO": {'pe': 60.23, 'ev_ebitda': 32.52},
    "DIS": {'pe': 31.72, 'ev_ebitda': 24.51},
    "NFLX": {'pe': 31.72, 'ev_ebitda': 24.51},
    "LLY": {'pe': 21.23, 'ev_ebitda': 13.7},
    "JNJ": {'pe': 21.23, 'ev_ebitda': 13.7},
    "MRK": {'pe': 21.23, 'ev_ebitda': 13.7},
    "UNH": {'pe': 21.23, 'ev_ebitda': 13.7},
    "PFE": {'pe': 21.23, 'ev_ebitda': 13.7},
    "NVO": {'pe': 21.23, 'ev_ebitda': 13.7},
    "TMO": {'pe': 21.23, 'ev_ebitda': 13.7},
    "JPM": {'pe': 24.39, 'ev_ebitda': 24.21},
    "WFC": {'pe': 24.39, 'ev_ebitda': 24.21},
    "MA": {'pe': 24.39, 'ev_ebitda': 24.21},
    "V": {'pe': 24.39, 'ev_ebitda': 24.21},
    "XOM": {'pe': 16.53, 'ev_ebitda': 8.38},
    "MCD": {'pe': 31.71, 'ev_ebitda': 22.77},
    "WMT": {'pe': 31.71, 'ev_ebitda': 22.77},
    "COST": {'pe': 31.71, 'ev_ebitda': 22.77},
    "HD": {'pe': 31.71, 'ev_ebitda': 22.77},
    "KO": {'pe': 31.71, 'ev_ebitda': 22.77},
    "PEP": {'pe': 31.71, 'ev_ebitda': 22.77},
    "BA": {'pe': 15.78, 'ev_ebitda': -10.9},
    "L": {'pe': 15.78, 'ev_ebitda': -10.9},
    "TSLA": {'pe': 323.01, 'ev_ebitda': 142.14},
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
            BOND_YIELD_2 = BOND_YIELD_2_TR
        )
    else:
        return dict(
            RISK_FREE_RATE=RISK_FREE_RATE_US,
            MARKET_PREMIUM=MARKET_PREMIUM_US,
            COST_OF_DEBT=COST_OF_DEBT_US,
            TAX_RATE=TAX_RATE_US,
            PE=SECTOR_OVERRIDES.get(ticker, {}).get("pe", SECTOR_PE_US),
            EV_EBITDA=SECTOR_OVERRIDES.get(ticker, {}).get("ev_ebitda", SECTOR_EV_EBITDA_US),
            BOND_YIELD_2 = BOND_YIELD_2_US
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
# Graham
# ------------------------------
def graham_valuation(eps, sector_pe, bond_yield):
    if not eps or not sector_pe or not bond_yield:
        return None
    return (eps * sector_pe) / (bond_yield * 100)


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
        
    
    # Ödenmiş Sermaye Yaklaşımı
    nominal_value = 1 if ticker.upper().endswith(".IS") else 1  # ABD için de 1$
    paid_up_capital = shares * nominal_value if shares else None

    operating_income = _annual_value_for_year(income_stmt, ["Operating Income", "Total Operating Income"], 2024)
    fv_efk = safe_div((operating_income * 10) if operating_income else None, paid_up_capital)

    net_income = _annual_value_for_year(income_stmt, ["Net Income", "Net Income Applicable to Common Shares"], 2023)
    fv_ndk = safe_div((net_income * 10) if net_income else None, paid_up_capital)
    
    #Graham
    fv_graham = graham_valuation(eps, pe_sector, params["BOND_YIELD_2"])
    
    # Ortalama Adil Fiyat
    vals = [v for v in [fv_dcf, fv_fk, fv_ev, fv_ddm, fv_efk, fv_ndk, fv_graham] if v is not None and v > 0]
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
        "EFK Değerlemesi": format_number_tr(fv_efk),
        "NDK Değerlemesi": format_number_tr(fv_ndk),
        "Graham Değerlemesi": format_number_tr(fv_graham),
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
