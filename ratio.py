import yfinance as yf
import pandas as pd

# Türkçe formatlama fonksiyonları (önceki kodunuzdan)
def format_number_tr(value):
    if value is None or pd.isna(value):
        return ""
    return "{:,.2f}".format(value).replace(",", "X").replace(".", ",").replace("X", ".")

def format_percent_tr(value):
    if value is None or pd.isna(value):
        return ""
    return "{:,.2f}".format(value).replace(",", "X").replace(".", ",").replace("X", "")

def get_first_available_index_value(df, keys):
    for key in keys:
        if key in df.index:
            value = df.loc[key].dropna()
            if not value.empty:
                return value.iloc[0]
    return None

def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    financials_annual = stock.financials
    balance_sheet_annual = stock.balance_sheet
    cashflow_annual = stock.cashflow

    data = {"Hisse": ticker}
    data['Şirket Adı'] = info.get('longName', '-')

    # Cari Oran (Current Ratio)
    current_assets = get_first_available_index_value(balance_sheet_annual, ['Current Assets', 'Total Current Assets'])
    current_liabilities = get_first_available_index_value(balance_sheet_annual, ['Current Liabilities', 'Total Current Liabilities'])
    current_ratio = current_assets / current_liabilities if current_assets and current_liabilities else None
    data['Cari Oran'] = format_percent_tr(current_ratio)

    # Likit Oran (Quick Ratio)
    inventory = get_first_available_index_value(balance_sheet_annual, ['Inventory', 'Inventories'])
    quick_assets = current_assets - inventory if current_assets and inventory else current_assets
    quick_ratio = quick_assets / current_liabilities if quick_assets and current_liabilities else None
    data['Likit Oran'] = format_percent_tr(quick_ratio)

    # Nakit Oran (Cash Ratio)
    cash = info.get('totalCash', get_first_available_index_value(balance_sheet_annual, ['Cash', 'Cash And Cash Equivalents']))
    cash_ratio = cash / current_liabilities if cash and current_liabilities else None
    data['Nakit Oran'] = format_percent_tr(cash_ratio)

    # Özsermaye Kârlılığı (ROE) (%) Yıllık
    equity_keys = ['Stockholders Equity', 'Common Stock Equity', 'Total Equity Gross Minority Interest']
    total_equity = get_first_available_index_value(balance_sheet_annual, equity_keys)
    ttm_net_income = info.get('trailingEps') * info.get('sharesOutstanding') if info.get('trailingEps') and info.get('sharesOutstanding') else None
    roe = (ttm_net_income / total_equity) * 100 if ttm_net_income and total_equity else None
    data['Özsermaye Kârlılığı (ROE) (%) Yıllık'] = format_percent_tr(roe)

    # F/K - Fiyat/Kazanç (Dönem Sonu)
    data['F/K'] = format_percent_tr(info.get('trailingPE'))

    # PD/DD (Fiyat/Defter Değeri)
    data['PD/DD'] = format_percent_tr(info.get('priceToBook'))

    # FAVÖK Büyüme (%) (Yıllık)
    if not financials_annual.empty and financials_annual.shape[1] >= 2:
        ebitda1 = get_first_available_index_value(financials_annual, ['EBITDA', 'Operating Income']) or 0
        ebitda2 = financials_annual.loc['EBITDA'].iloc[1] if 'EBITDA' in financials_annual.index and financials_annual.shape[1] >= 2 else None
        ebitda_growth = ((ebitda1 - ebitda2) / ebitda2) * 100 if ebitda2 and ebitda1 else None
    else:
        ebitda_growth = None
    data['FAVÖK Büyüme (%) (Yıllık)'] = format_percent_tr(ebitda_growth)

    # PEG Oranı (Fiyat/Kazanç Büyüme Oranı)
    pe_ratio = info.get('trailingPE')
    eps_growth = info.get('earningsGrowth')
    peg_ratio = pe_ratio / (eps_growth * 100) if pe_ratio and eps_growth and eps_growth != 0 else None
    data['PEG Oranı'] = format_percent_tr(peg_ratio)

    # ROIC (Yatırım Getirisi)
    nopat = get_first_available_index_value(financials_annual, ['Net Income', 'Net Income Common Stockholders'])
    invested_capital_keys = ['Total Assets', 'Total Capitalization']
    invested_capital = get_first_available_index_value(balance_sheet_annual, invested_capital_keys)
    current_liabilities = get_first_available_index_value(balance_sheet_annual, ['Current Liabilities', 'Total Current Liabilities'])
    invested_capital = invested_capital - current_liabilities if invested_capital and current_liabilities else None
    roic = (nopat / invested_capital) * 100 if nopat and invested_capital else None
    data['ROIC (%)'] = format_percent_tr(roic)

    # Aktif Devir Hızı (Asset Turnover)
    revenue = get_first_available_index_value(financials_annual, ['Total Revenue', 'Revenue'])
    total_assets = get_first_available_index_value(balance_sheet_annual, ['Total Assets'])
    asset_turnover = revenue / total_assets if revenue and total_assets else None
    data['Aktif Devir Hızı'] = format_percent_tr(asset_turnover)

    return data

# Hisse listesini dosyadan oku
with open("tickers.txt", "r") as f:
    tickers = [line.strip() for line in f if line.strip()]

all_data = []
for ticker in tickers:
    try:
        print(f"{ticker} is being processed..")
        data = get_stock_data(ticker)
        all_data.append(data)
    except Exception as e:
        print(f"Error occurred for {ticker}: {e}")

# DataFrame oluştur
df = pd.DataFrame(all_data)

# Excel'e aktar
df.to_excel("ratio.xlsx", index=False)
print("✅ Process completed: ratio.xlsx")
