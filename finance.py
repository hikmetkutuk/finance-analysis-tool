import yfinance as yf
import pandas as pd
from typing import Iterable, Optional

# ------------------------------
# Format yardımcıları (TR)
# ------------------------------
def format_number_tr(value: Optional[float]) -> str:
    """Para/büyüklük değerleri için (ör: Net Gelir, EBITDA) 2 ondalıklı TR biçim."""
    if value is None:
        return "-"
    try:
        return "{:,.2f}".format(float(value)).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"

def format_ratio_tr(value: Optional[float]) -> str:
    """Kat sayı/multiple oranları için (ör: EV/EBITDA, P/E, P/CF) 2 ondalıklı, % işareti YOK."""
    if value is None:
        return "-"
    try:
        return "{:,.2f}".format(float(value)).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"

def format_percent_tr(value: Optional[float]) -> str:
    """Yüzde oranları için (ör: ROE, Borç/Varlık) 2 ondalıklı, % işareti YOK (istersen ekleyebilirsin)."""
    if value is None:
        return "-"
    try:
        return "{:,.2f}".format(float(value)).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "-"

# ------------------------------
# DataFrame yardımcıları
# ------------------------------
def first_col(df: pd.DataFrame) -> Optional[str]:
    """Yahoo Finance tablolarında en güncel sütun genellikle soldadır (columns[0])."""
    if df is None or df.empty:
        return None
    return df.columns[0]

def latest_value(df: pd.DataFrame, keys: Iterable[str]) -> Optional[float]:
    """
    Verilen index anahtarlarından (keys) ilk bulunanın en güncel sütundaki değerini döndürür.
    df: quarterly_* veya annual DataFrame
    """
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
    """
    Quarterly bir tabloda ilgili satırın son 4 çeyreğini toplayarak TTM döndürür.
    df: quarterly_* DataFrame
    """
    if df is None or df.empty or row_name not in df.index:
        return None
    try:
        s = df.loc[row_name].dropna().iloc[:4]  # Yahoo'da en güncel solda
        return float(s.sum()) if not s.empty else None
    except Exception:
        return None

def two_period_growth_pct(df: pd.DataFrame, row_name: str) -> Optional[float]:
    """
    Aynı satırın (ör: 'Total Assets' veya 'Net Income') son iki dönemiyle büyüme % hesaplar.
    """
    if df is None or df.empty or row_name not in df.index:
        return None
    try:
        s = df.loc[row_name].dropna()
        # En güncel solda olduğu için 0 ve 1 indeksleri kullanıyoruz
        if s.shape[0] < 2:
            return None
        a1 = float(s.iloc[0])
        a2 = float(s.iloc[1])
        if a2 == 0:
            return None
        return (a1 - a2) / a2 * 100.0
    except Exception:
        return None

# ------------------------------
# Ana veri çekme
# ------------------------------
def get_stock_data(ticker: str) -> dict:
    # Küçük yardımcı: güvenli float çevirimi
    def _f(x):
        try:
            return float(x)
        except Exception:
            return None

    stock = yf.Ticker(ticker)

    # Info (bazı metriklerde yardımcı olur)
    info = stock.info if isinstance(stock.info, dict) else {}

    # DataFrame'leri güvenli şekilde al (None ise boş DataFrame olsun)
    q_fin = stock.quarterly_financials if isinstance(stock.quarterly_financials, pd.DataFrame) else pd.DataFrame()
    q_bs  = stock.quarterly_balance_sheet if isinstance(stock.quarterly_balance_sheet, pd.DataFrame) else pd.DataFrame()
    q_cf  = stock.quarterly_cashflow if isinstance(stock.quarterly_cashflow, pd.DataFrame) else pd.DataFrame()
    a_fin = stock.financials if isinstance(stock.financials, pd.DataFrame) else pd.DataFrame()
    a_bs  = stock.balance_sheet if isinstance(stock.balance_sheet, pd.DataFrame) else pd.DataFrame()

    data = {"Hisse": ticker}
    data["Name"] = info.get("longName") or info.get("shortName")

    # ------------------------------
    # EBITDA (TTM)
    # ------------------------------
    ebitda = series_ttm(q_fin, "EBITDA")
    if ebitda is None:
        ebitda = _f(info.get("ebitda"))
    data["EBITDA"] = format_number_tr(ebitda)

    # ------------------------------
    # Net Gelir (TTM)
    # ------------------------------
    ttm_net_income = series_ttm(q_fin, "Net Income")
    if ttm_net_income is None:
        teps, shares = _f(info.get("trailingEps")), _f(info.get("sharesOutstanding"))
        ttm_net_income = (teps * shares) if (teps is not None and shares is not None) else None
    data["Net Gelir"] = format_number_tr(ttm_net_income)

    # ------------------------------
    # Özkaynak (son bilanço -> quarterly > annual)
    # ------------------------------
    equity_keys = ["Common Stock Equity", "Stockholders Equity", "Total Equity Gross Minority Interest"]
    total_equity = latest_value(q_bs, equity_keys)
    if total_equity is None:
        total_equity = latest_value(a_bs, equity_keys)
    data["Özkaynak"] = format_number_tr(total_equity)

    # ------------------------------
    # ROE (%)
    # ------------------------------
    roe = None
    if ttm_net_income is not None and total_equity not in (None, 0):
        roe = (_f(ttm_net_income) / _f(total_equity)) * 100.0 if (_f(ttm_net_income) is not None and _f(total_equity) not in (None, 0)) else None
    data["ROE (%) Annual"] = format_percent_tr(roe)

    # ------------------------------
    # EV/EBITDA (kat sayı)
    # ------------------------------
    ev = _f(info.get("enterpriseValue"))
    ev_ebitda = (ev / _f(ebitda)) if (ev is not None and _f(ebitda) not in (None, 0)) else None
    data["EV/EBITDA"] = format_ratio_tr(ev_ebitda)

    # ------------------------------
    # P/CF (kat sayı) -> MarketCap / TTM Operating Cash Flow
    # ------------------------------
    ttm_ocf = series_ttm(q_cf, "Operating Cash Flow")
    market_cap = _f(info.get("marketCap"))
    if market_cap is None:
        cp, so = _f(info.get("currentPrice")), _f(info.get("sharesOutstanding"))
        market_cap = (cp * so) if (cp is not None and so is not None) else None
    p_cf = (market_cap / _f(ttm_ocf)) if (market_cap not in (None, 0) and _f(ttm_ocf) not in (None, 0)) else None
    data["P/CF"] = format_ratio_tr(p_cf)

    # ------------------------------
    # Diğer temel oranlar (kat sayı)
    # ------------------------------
    data["P/E"]  = format_ratio_tr(_f(info.get("trailingPE")))
    data["EPS"]  = format_ratio_tr(_f(info.get("trailingEps")))  # (biçim aynı, yüzde değil)
    data["P/B"]  = format_ratio_tr(_f(info.get("priceToBook")))
    data["P/S"]  = format_ratio_tr(_f(info.get("priceToSalesTrailing12Months")))
    data["Beta"] = format_ratio_tr(_f(info.get("beta")))

    # ------------------------------
    # Varlık Büyümesi (%) - öncelik quarterly
    # ------------------------------
    asset_growth = two_period_growth_pct(q_bs, "Total Assets")
    if asset_growth is None:
        asset_growth = two_period_growth_pct(a_bs, "Total Assets")
    data["Varlık Büyümesi (%)"] = format_percent_tr(asset_growth)

    # ------------------------------
    # Net Gelir Büyümesi (%) - öncelik quarterly
    # ------------------------------
    income_growth = two_period_growth_pct(q_fin, "Net Income")
    if income_growth is None:
        income_growth = two_period_growth_pct(a_fin, "Net Income")
    data["Net Gelir Büyümesi (%)"] = format_percent_tr(income_growth)

    # ------------------------------
    # Faaliyet Karı (TTM - Operating Income)
    # ------------------------------
    operating_income_ttm = series_ttm(q_fin, "Operating Income")
    if operating_income_ttm is None:
        operating_income_ttm = latest_value(a_fin, ["Operating Income"])
    data["Faaliyet Karı"] = format_number_tr(operating_income_ttm)

    # ------------------------------
    # Borç/Varlık (%)
    # ------------------------------
    # Toplam Borç
    total_debt = latest_value(q_bs, ["Total Debt"])
    if total_debt is None:
        short_d = latest_value(q_bs, ["Current Debt", "Current Debt And Capital Lease Obligation"]) or 0.0
        long_d  = latest_value(q_bs, ["Long Term Debt"]) or 0.0
        total_debt = short_d + long_d

    # Toplam Varlık
    total_assets = latest_value(q_bs, ["Total Assets"])
    if total_assets is None:
        total_assets = latest_value(a_bs, ["Total Assets"])

    debt_to_asset_pct = None
    td, ta = _f(total_debt), _f(total_assets)
    if td not in (None, 0) and ta not in (None, 0):
        debt_to_asset_pct = (td / ta) * 100.0
    data["Borç/Varlık (%)"] = format_percent_tr(debt_to_asset_pct)

    # ------------------------------
    # Ödenmiş Sermaye (Common Stock + Additional Paid In Capital)
    # ------------------------------
    common_stock = latest_value(q_bs, ["Common Stock"])
    if common_stock is None:
        common_stock = latest_value(a_bs, ["Common Stock"])
    add_paid_in_cap = latest_value(q_bs, ["Additional Paid In Capital"])
    if add_paid_in_cap is None:
        add_paid_in_cap = latest_value(a_bs, ["Additional Paid In Capital"])
    cs, apic = _f(common_stock), _f(add_paid_in_cap)
    paid_in_cap_total = (cs or 0.0) + (apic or 0.0) if (cs is not None or apic is not None) else None
    data["Ödenmiş Sermaye"] = format_number_tr(paid_in_cap_total)

    # ------------------------------
    # Net İşletme Sermayesi (NWC = CA - CL)
    # ------------------------------
    current_assets = latest_value(q_bs, ["Current Assets", "Total Current Assets"])
    if current_assets is None:
        current_assets = latest_value(a_bs, ["Current Assets", "Total Current Assets"])
    current_liab = latest_value(q_bs, ["Current Liabilities", "Total Current Liabilities"])
    if current_liab is None:
        current_liab = latest_value(a_bs, ["Current Liabilities", "Total Current Liabilities"])
    ca, cl = _f(current_assets), _f(current_liab)
    nwc = (ca - cl) if (ca is not None and cl is not None) else None
    data["Net İşletme Sermayesi"] = format_number_tr(nwc)

    # ------------------------------
    # Net Borç/EBITDA (kat sayı)
    # ------------------------------
    cash_like = latest_value(q_bs, ["Cash And Cash Equivalents", "Cash And Cash Equivalents And Short Term Investments"])
    if cash_like is None:
        cash_like = latest_value(a_bs, ["Cash And Cash Equivalents", "Cash And Cash Equivalents And Short Term Investments"])

    nd = None
    td_f, cash_f = _f(total_debt), _f(cash_like)
    if td_f is not None and cash_f is not None:
        nd = td_f - cash_f

    nd_ebitda = (nd / _f(ebitda)) if (nd is not None and _f(ebitda) not in (None, 0)) else None
    data["Net Borç/EBITDA"] = format_ratio_tr(nd_ebitda)

    return data

# ------------------------------
# Çalıştırma
# ------------------------------
if __name__ == "__main__":
    with open("tickers.txt", "r", encoding="utf-8") as f:
        tickers = [line.strip() for line in f if line.strip()]

    all_data = []
    for ticker in tickers:
        try:
            print(f"{ticker} işleniyor...")
            data = get_stock_data(ticker)
            all_data.append(data)
        except Exception as e:
            print(f"{ticker} için hata oluştu: {e}")

    # 🔁 DataFrame (her satır hisse, sütunlar metrik)
    df = pd.DataFrame(all_data)

    # ✅ İstediğin sıralama
    columns_order = [
        "Hisse",                     # 1-Symbol
        "Name",                      # 2-Name
        "EBITDA",                    # 3
        "ROE (%) Annual",            # 4
        "EV/EBITDA",                 # 5
        "P/CF",                      # 6
        "P/E",                       # 7
        "EPS",                       # 8
        "P/B",                       # 9
        "P/S",                       # 10
        "Beta",                      # 11
        "Varlık Büyümesi (%)",       # 12-Asset Growth (%)
        "Net Gelir Büyümesi (%)",    # 13-Net Income Growth (Annual, %)
        "Net Gelir",                 # 14-Net Income
        "Faaliyet Karı",             # 15-Operating Income
        "Özkaynak",                  # 16-Shareholders’ Equity
        "Borç/Varlık (%)",           # 17-Debt-to-Assets Ratio
        "Ödenmiş Sermaye",           # 18-Paid-in Capital
        "Net İşletme Sermayesi",     # 19-Net Working Capital
        "Net Borç/EBITDA"            # 20-Net Debt/EBITDA (Annual, %)
    ]
    
    df = df[[col for col in columns_order if col in df.columns]]

    # 📤 Excel'e aktar
    out_name = "financial.xlsx"
    df.to_excel(out_name, index=False)
    print(f"✅ Tamamlandı: {out_name}")
