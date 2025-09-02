import yfinance as yf
import pandas as pd
from typing import Iterable, Optional

# ------------------------------
# Format yardımcıları (TR)
# ------------------------------
def format_number_tr(value: Optional[float]) -> str:
    """Büyüklükler (para vb.) için 2 ondalıklı TR biçimi."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        return "{:,.2f}".format(float(value)).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return ""

def format_ratio_tr(value: Optional[float]) -> str:
    """Kat sayı/oran (current ratio, P/E, P/B, PEG vb.) için 2 ondalık, % işareti yok."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        return "{:,.2f}".format(float(value)).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return ""

def format_percent_tr(value: Optional[float]) -> str:
    """Yüzde metrikleri (ROE, ROIC vb.) için 2 ondalık, % işareti yok (etikette % var)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        return "{:,.2f}".format(float(value)).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return ""

# ------------------------------
# DataFrame yardımcıları
# ------------------------------
def first_col(df: pd.DataFrame) -> Optional[str]:
    """Yahoo tablolarında en güncel sütun çoğunlukla soldadır."""
    if df is None or df.empty:
        return None
    return df.columns[0]

def latest_value(df: pd.DataFrame, keys: Iterable[str]) -> Optional[float]:
    """Verilen index anahtarlarından ilk bulunanın en güncel sütundaki değerini döndürür."""
    if df is None or df.empty:
        return None
    col = first_col(df)
    if col is None:
        return None
    for key in keys:
        if key in df.index:
            try:
                val = df.loc[key, col]
                if pd.notna(val):
                    return float(val)
            except Exception:
                pass
    return None

def series_ttm(df: pd.DataFrame, row_name: str) -> Optional[float]:
    """Quarterly tabloda ilgili satırın son 4 çeyreğini toplayarak TTM döndürür."""
    if df is None or df.empty or row_name not in df.index:
        return None
    try:
        s = df.loc[row_name].dropna().iloc[:4]  # en güncel solda varsayımı
        return float(s.sum()) if not s.empty else None
    except Exception:
        return None

def yoy_growth_from_annual_or_quarterly(fin_annual: pd.DataFrame, fin_quarterly: pd.DataFrame, row_name: str) -> Optional[float]:
    """
    Önce yıllıkta YoY büyüme (son iki yıllık değer) dener.
    Yıllık yoksa quarterly'den iki TTM (son 4 ve önceki 4 çeyrek) ile YoY büyüme hesaplar.
    """
    # Annual: iki kolon varsa
    if fin_annual is not None and not fin_annual.empty and row_name in fin_annual.index:
        s = fin_annual.loc[row_name].dropna()
        if s.shape[0] >= 2:
            a1 = float(s.iloc[0])
            a2 = float(s.iloc[1])
            if a2 != 0:
                return (a1 - a2) / a2 * 100.0

    # Quarterly: en az 8 değer varsa iki TTM kıyasla
    if fin_quarterly is not None and not fin_quarterly.empty and row_name in fin_quarterly.index:
        s = fin_quarterly.loc[row_name].dropna()
        if s.shape[0] >= 8:
            ttm_now = float(s.iloc[:4].sum())
            ttm_prev = float(s.iloc[4:8].sum())
            if ttm_prev != 0:
                return (ttm_now - ttm_prev) / ttm_prev * 100.0
    return None

# ------------------------------
# Sayı güvenli dönüştürücü
# ------------------------------
def _f(x):
    try:
        return float(x)
    except Exception:
        return None

# ------------------------------
# Ana veri çekme
# ------------------------------
def get_stock_data(ticker: str) -> dict:
    stock = yf.Ticker(ticker)

    # Info ve tablolar
    info = stock.info if isinstance(stock.info, dict) else {}

    q_fin = stock.quarterly_financials if isinstance(stock.quarterly_financials, pd.DataFrame) else pd.DataFrame()
    q_bs  = stock.quarterly_balance_sheet if isinstance(stock.quarterly_balance_sheet, pd.DataFrame) else pd.DataFrame()
    q_cf  = stock.quarterly_cashflow if isinstance(stock.quarterly_cashflow, pd.DataFrame) else pd.DataFrame()

    a_fin = stock.financials if isinstance(stock.financials, pd.DataFrame) else pd.DataFrame()
    a_bs  = stock.balance_sheet if isinstance(stock.balance_sheet, pd.DataFrame) else pd.DataFrame()

    data = {"Hisse": ticker}
    data['Şirket Adı'] = info.get('longName') or info.get('shortName') or ""

    # ----------- Likidite Oranları -----------
    current_assets = latest_value(q_bs, ['Current Assets', 'Total Current Assets'])
    if current_assets is None:
        current_assets = latest_value(a_bs, ['Current Assets', 'Total Current Assets'])

    current_liabilities = latest_value(q_bs, ['Current Liabilities', 'Total Current Liabilities'])
    if current_liabilities is None:
        current_liabilities = latest_value(a_bs, ['Current Liabilities', 'Total Current Liabilities'])

    inventory = latest_value(q_bs, ['Inventory', 'Inventories'])
    if inventory is None:
        inventory = latest_value(a_bs, ['Inventory', 'Inventories'])

    cash_like = latest_value(q_bs, ['Cash And Cash Equivalents', 'Cash And Cash Equivalents And Short Term Investments', 'Cash'])
    if cash_like is None:
        cash_like = latest_value(a_bs, ['Cash And Cash Equivalents', 'Cash And Cash Equivalents And Short Term Investments', 'Cash'])

    # Cari Oran
    current_ratio = None
    ca, cl = _f(current_assets), _f(current_liabilities)
    if ca not in (None, ) and cl not in (None, 0):
        current_ratio = ca / cl
    data['Cari Oran'] = format_ratio_tr(current_ratio)

    # Likit Oran (Quick Ratio)
    quick_ratio = None
    inv = _f(inventory) if inventory is not None else 0.0
    if ca not in (None,) and cl not in (None, 0):
        quick_ratio = (ca - (inv or 0.0)) / cl
    data['Likit Oran'] = format_ratio_tr(quick_ratio)

    # Nakit Oran (Cash Ratio)
    cash_ratio = None
    csh = _f(cash_like)
    if csh not in (None,) and cl not in (None, 0):
        cash_ratio = csh / cl
    data['Nakit Oran'] = format_ratio_tr(cash_ratio)

    # ----------- ROE (Yıllık, %) -----------
    # Net Income TTM
    ttm_net_income = series_ttm(q_fin, 'Net Income')
    if ttm_net_income is None:
        teps, shares = _f(info.get('trailingEps')), _f(info.get('sharesOutstanding'))
        ttm_net_income = (teps * shares) if (teps is not None and shares is not None) else None

    # Equity (son bilanço – quarterly > annual)
    equity_keys = ['Common Stock Equity', 'Stockholders Equity', 'Total Equity Gross Minority Interest']
    total_equity = latest_value(q_bs, equity_keys)
    if total_equity is None:
        total_equity = latest_value(a_bs, equity_keys)

    roe = None
    eq = _f(total_equity)
    if ttm_net_income not in (None,) and eq not in (None, 0):
        roe = (_f(ttm_net_income) / eq) * 100.0
    data['Özsermaye Kârlılığı (ROE) (%) Yıllık'] = format_percent_tr(roe)

    # ----------- F/K ve PD/DD (info’dan) -----------
    data['F/K'] = format_ratio_tr(_f(info.get('trailingPE')))
    data['PD/DD'] = format_ratio_tr(_f(info.get('priceToBook')))

    # ----------- FAVÖK Büyüme (%) (Yıllık) -----------
    # Yıllıkta EBITDA varsa YoY; yoksa quarterly iki TTM kıyas
    ebitda_growth = yoy_growth_from_annual_or_quarterly(a_fin, q_fin, 'EBITDA')
    # EBITDA bulunamazsa Operating Income ile yaklaşık
    if ebitda_growth is None:
        ebitda_growth = yoy_growth_from_annual_or_quarterly(a_fin, q_fin, 'Operating Income')
    data['FAVÖK Büyüme (%) (Yıllık)'] = format_percent_tr(ebitda_growth)

    # ----------- PEG Oranı -----------
    pe_ratio = _f(info.get('trailingPE'))
    eps_growth = info.get('earningsGrowth')  # genelde 0.12 gibi ondalık gelir
    eg = _f(eps_growth)
    growth_pct = None
    if eg is not None:
        # Eğer 1'den küçükse %'ye çevir (0.12 -> 12), yoksa olduğu gibi kullan
        growth_pct = eg * 100.0 if eg < 1 else eg
    peg_ratio = (pe_ratio / growth_pct) if (pe_ratio not in (None, 0) and growth_pct not in (None, 0)) else None
    data['PEG Oranı'] = format_ratio_tr(peg_ratio)

    # ----------- ROIC (%) -----------
    # NOPAT ≈ Operating Income (TTM) * (1 - tax_rate)
    operating_income_ttm = series_ttm(q_fin, 'Operating Income')
    tax_rate = info.get('effectiveTaxRate')
    tax_rate = _f(tax_rate) if tax_rate is not None else 0.21  # ABD varsayılan %21
    nopat = None
    if operating_income_ttm not in (None,) and tax_rate not in (None,):
        nopat = _f(operating_income_ttm) * (1.0 - tax_rate)

    # Invested Capital ≈ Total Debt + Equity - Cash
    # Total Debt
    total_debt = latest_value(q_bs, ['Total Debt'])
    if total_debt is None:
        short_d = latest_value(q_bs, ['Current Debt', 'Current Debt And Capital Lease Obligation']) or 0.0
        long_d  = latest_value(q_bs, ['Long Term Debt']) or 0.0
        total_debt = (short_d or 0.0) + (long_d or 0.0)

    td, eqv, csh2 = _f(total_debt), _f(total_equity), _f(cash_like)
    invested_capital = None
    if td is not None or eqv is not None or csh2 is not None:
        invested_capital = (td or 0.0) + (eqv or 0.0) - (csh2 or 0.0)

    roic = None
    if nopat not in (None,) and invested_capital not in (None, 0):
        roic = nopat / invested_capital * 100.0
    data['ROIC (%)'] = format_percent_tr(roic)

    # ----------- Aktif Devir Hızı -----------
    # Revenue TTM / Ortalama Toplam Varlık (son iki dönem ortalaması), yoksa son değer
    revenue_ttm = series_ttm(q_fin, 'Total Revenue') or series_ttm(q_fin, 'Revenue')
    asset_turnover = None
    if q_bs is not None and not q_bs.empty and 'Total Assets' in q_bs.index:
        s = q_bs.loc['Total Assets'].dropna()
        if s.shape[0] >= 2:
            avg_assets = (float(s.iloc[0]) + float(s.iloc[1])) / 2.0
        elif s.shape[0] >= 1:
            avg_assets = float(s.iloc[0])
        else:
            avg_assets = None
    else:
        avg_assets = latest_value(a_bs, ['Total Assets'])

    if revenue_ttm not in (None,) and avg_assets not in (None, 0):
        asset_turnover = _f(revenue_ttm) / _f(avg_assets)
    data['Aktif Devir Hızı'] = format_ratio_tr(asset_turnover)

    return data

# ------------------------------
# Çalıştırma (Excel yazımı)
# ------------------------------
if __name__ == "__main__":
    # Hisse listesini dosyadan oku
    with open("tickers.txt", "r", encoding="utf-8") as f:
        tickers = [line.strip() for line in f if line.strip()]

    all_data = []
    for ticker in tickers:
        try:
            print(f"{ticker} is being processed..")
            data = get_stock_data(ticker)
            all_data.append(data)
        except Exception as e:
            print(f"Error occurred for {ticker}: {e}")

    # DataFrame
    df = pd.DataFrame(all_data)

    columns_order = [
        "Hisse",                                # Symbol
        "Cari Oran",                            # Current Ratio
        "Likit Oran",                           # Quick Ratio
        "Nakit Oran",                           # Cash Ratio
        "Özsermaye Kârlılığı (ROE) (%) Yıllık", # ROE (%) Annual
        "F/K",                                  # P/E
        "PD/DD",                                # P/B
        "FAVÖK Büyüme (%) (Yıllık)",            # Ebitda Growth(%) (Annual)
        "PEG Oranı",                            # Peg
        "ROIC (%)",                             # Roic
        "Aktif Devir Hızı",                     # Asset Turnover
        # Ratio sütununu ayrıca hesaplayıp ekleyeceksen buraya ekle
    ]
    
    df = df[[col for col in columns_order if col in df.columns]]

    df = df[[c for c in columns_order if c in df.columns]]

    # Excel'e aktar
    df.to_excel("ratio.xlsx", index=False)
    print("✅ Process completed: ratio.xlsx")
