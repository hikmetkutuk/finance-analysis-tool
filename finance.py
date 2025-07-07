import yfinance as yf
import pandas as pd

def format_number_tr(value):
    if value is None:
        return "-"
    return "{:,.2f}".format(value).replace(",", "X").replace(".", ",").replace("X", ".")

def format_percent_tr(value):
    if value is None:
        return "-"
    return "{:,.2f}".format(value).replace(",", "X").replace(".", ",").replace("X", "")

def get_first_available_index_value(df, keys):
    for key in keys:
        if key in df.index:
            value = df.loc[key].dropna()
            if not value.empty:
                return value.iloc[0]
    return 0

def get_stock_data(ticker):
    stock = yf.Ticker(ticker)
    info = stock.info
    financials_annual = stock.financials
    balance_sheet_annual = stock.balance_sheet
    cashflow = stock.quarterly_cashflow

    data = {"Hisse": ticker}
    data['Name'] = info.get('longName')

    # EBITDA
    if 'EBITDA' in stock.quarterly_financials.index:
        ebitda = stock.quarterly_financials.loc['EBITDA'].head(4).sum()
    else:
        ebitda = info.get('ebitda')

    data['EBITDA'] = format_number_tr(ebitda)

    # ROE
    equity_keys = ['Stockholders Equity', 'Common Stock Equity', 'Total Equity Gross Minority Interest']
    total_equity = next((balance_sheet_annual.loc[key].iloc[0] for key in equity_keys if key in balance_sheet_annual.index), None)
    ttm_net_income = info.get('trailingEps') * info.get('sharesOutstanding') if info.get('trailingEps') and info.get('sharesOutstanding') else None
    roe = (ttm_net_income / total_equity) * 100 if ttm_net_income and total_equity else None
    data['ROE (%) Annual'] = format_percent_tr(roe)

    # EV/EBITDA
    enterprise_value = info.get('enterpriseValue')
    evEbitda = enterprise_value / ebitda if enterprise_value and ebitda else None
    data['EV/EBITDA'] = format_percent_tr(evEbitda)

    # P/CF
    if 'Operating Cash Flow' in cashflow.index:
        ttm_cashflow = cashflow.loc['Operating Cash Flow'].iloc[:4].sum()
    else:
        ttm_cashflow = None
    market_price = info.get('currentPrice')
    shares_outstanding = info.get('sharesOutstanding')
    market_cap = market_price * shares_outstanding if market_price and shares_outstanding else None
    pcf_manual = market_cap / ttm_cashflow if market_cap and ttm_cashflow else None
    data['P/CF'] = format_percent_tr(pcf_manual)

    # Diğer temel oranlar
    data['P/E'] = format_percent_tr(info.get('trailingPE'))
    data['EPS'] = format_percent_tr(info.get('trailingEps'))
    data['P/B'] = format_percent_tr(info.get('priceToBook'))
    data['P/S'] = format_percent_tr(info.get('priceToSalesTrailing12Months'))
    data['Beta'] = format_percent_tr(info.get('beta'))

    # Varlık Büyümesi
    if not balance_sheet_annual.empty and balance_sheet_annual.shape[1] >= 2:
        a1 = balance_sheet_annual.loc['Total Assets'].iloc[0]
        a2 = balance_sheet_annual.loc['Total Assets'].iloc[1]
        asset_growth = ((a1 - a2) / a2) * 100 if a2 else None
    else:
        asset_growth = None
    data['Varlık Büyümesi (%)'] = format_percent_tr(asset_growth)

    # Net Gelir Büyümesi
    if not financials_annual.empty and financials_annual.shape[1] >= 2:
        ni1 = financials_annual.loc['Net Income'].iloc[0]
        ni2 = financials_annual.loc['Net Income'].iloc[1]
        income_growth = ((ni1 - ni2) / ni2) * 100 if ni2 else None
    else:
        income_growth = None
    data['Net Gelir Büyümesi (%)'] = format_percent_tr(income_growth)

    # Net Gelir
    data['Net Gelir'] = format_number_tr(ttm_net_income)

    # Faaliyet Karı
    if 'Operating Income' in financials_annual.index:
        data['Faaliyet Karı'] = format_number_tr(financials_annual.loc['Operating Income'].iloc[0])
    else:
        data['Faaliyet Karı'] = "-"

    # Özkaynaklar
    data['Özkaynak'] = format_number_tr(total_equity)

    # Borç/Varlık Oranı
    short_term = get_first_available_index_value(balance_sheet_annual, ['Current Debt', 'Current Debt And Capital Lease Obligation']) or 0
    long_term = get_first_available_index_value(balance_sheet_annual, ['Long Term Debt']) or 0
    total_debt_alt = short_term + long_term
    total_assets_alt = get_first_available_index_value(balance_sheet_annual, ['Total Assets'])
    debt_to_asset = (total_debt_alt / total_assets_alt) * 100 if total_debt_alt and total_assets_alt else None
    data['Borç/Varlık (%)'] = format_percent_tr(debt_to_asset)

    # Ödenmiş Sermaye
    common_stock = balance_sheet_annual.loc['Common Stock'].iloc[0] if 'Common Stock' in balance_sheet_annual.index else 0
    paid_in_cap = balance_sheet_annual.loc['Additional Paid In Capital'].iloc[0] if 'Additional Paid In Capital' in balance_sheet_annual.index else 0
    data['Ödenmiş Sermaye'] = format_number_tr(common_stock + paid_in_cap)

    # Net İşletme Sermayesi
    current_assets = get_first_available_index_value(balance_sheet_annual, ['Current Assets', 'Total Current Assets'])
    current_liabilities = get_first_available_index_value(balance_sheet_annual, ['Current Liabilities', 'Total Current Liabilities'])
    nwc = current_assets - current_liabilities if current_assets and current_liabilities else None
    data['Net İşletme Sermayesi'] = format_number_tr(nwc)

    # Net Borç/EBITDA
    cash = info.get('totalCash')
    if total_debt_alt and cash and ebitda:
        net_debt = total_debt_alt - cash
        net_debt_ebitda = (net_debt / ebitda) * 100 if ebitda else None
    else:
        net_debt_ebitda = None
    data['Net Borç/EBITDA (%)'] = format_percent_tr(net_debt_ebitda)

    return data

# 🧾 Hisse listesi
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

# 🔁 DataFrame (her satır hisse, sütunlar metrik)
df = pd.DataFrame(all_data)

# 📤 Excel'e aktar
df.to_excel("financial.xlsx", index=False)
print("✅ Process completed: financial.xlsx")
