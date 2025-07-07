import yfinance as yf
import pandas as pd

# Türkçe formatlama fonksiyonu
def format_number_tr(value):
    if value is None or pd.isna(value):
        return ""
    return "{:,.2f}".format(value).replace(",", "X").replace(".", ",").replace("X", ".")

def get_annual_data(ticker, years_back=5):
    stock = yf.Ticker(ticker)
    data = {"Kod": ticker}

    # Yıllık ve çeyreklik finansal tabloları al
    income_stmt = stock.financials
    balance_sheet = stock.balance_sheet
    cash_flow = stock.cashflow
    quarterly_income_stmt = stock.quarterly_financials
    quarterly_balance_sheet = stock.quarterly_balance_sheet
    quarterly_cash_flow = stock.quarterly_cashflow

    # 2025 için çeyreklik verileri topla
    target_year = 2025
    op_income_2025 = taxes_2025 = depr_2025 = ppe_2025 = receivables_2025 = inventory_2025 = liabilities_2025 = 0
    found_2025 = False
    for date in quarterly_income_stmt.columns:
        if date.year == 2025:
            found_2025 = True
            # Net Faaliyet Kârı
            op_income_keys = ["Operating Income", "Total Operating Income"]
            for key in op_income_keys:
                if key in quarterly_income_stmt.index:
                    op_income_2025 += quarterly_income_stmt.loc[key, date] if not pd.isna(quarterly_income_stmt.loc[key, date]) else 0
                    break
            # Vergi
            tax_keys = ["Tax Provision", "Income Tax Expense"]
            for key in tax_keys:
                if key in quarterly_income_stmt.index:
                    taxes_2025 += quarterly_income_stmt.loc[key, date] if not pd.isna(quarterly_income_stmt.loc[key, date]) else 0
                    break
            # Amortisman
            depr_keys = ["Depreciation And Amortization", "Depreciation"]
            for key in depr_keys:
                if key in quarterly_cash_flow.index:
                    depr_2025 += quarterly_cash_flow.loc[key, date] if not pd.isna(quarterly_cash_flow.loc[key, date]) else 0
                    break
    for date in quarterly_balance_sheet.columns:
        if date.year == 2025:
            # Sabit Sermaye
            ppe_keys = ["Net PPE", "Property Plant Equipment"]
            for key in ppe_keys:
                if key in quarterly_balance_sheet.index:
                    ppe_2025 = quarterly_balance_sheet.loc[key, date] if not pd.isna(quarterly_balance_sheet.loc[key, date]) else ppe_2025
                    break
            # Toplam Alacak
            receivable_keys = ["Accounts Receivable", "Total Receivables"]
            for key in receivable_keys:
                if key in quarterly_balance_sheet.index:
                    receivables_2025 = quarterly_balance_sheet.loc[key, date] if not pd.isna(quarterly_balance_sheet.loc[key, date]) else receivables_2025
                    break
            # Stok
            inventory_keys = ["Inventory", "Inventories"]
            for key in inventory_keys:
                if key in quarterly_balance_sheet.index:
                    inventory_2025 = quarterly_balance_sheet.loc[key, date] if not pd.isna(quarterly_balance_sheet.loc[key, date]) else inventory_2025
                    break
            # Toplam Borç
            liability_keys = ["Total Liabilities", "Total Liabilities Net Minority Interest"]
            for key in liability_keys:
                if key in quarterly_balance_sheet.index:
                    liabilities_2025 = quarterly_balance_sheet.loc[key, date] if not pd.isna(quarterly_balance_sheet.loc[key, date]) else liabilities_2025
                    break
    if found_2025:
        data[f"Net Faaliyet Kârı {target_year}"] = format_number_tr(op_income_2025)
        data[f"Vergi {target_year}"] = format_number_tr(taxes_2025)
        data[f"Amortisman {target_year}"] = format_number_tr(depr_2025)
        data[f"Sabit Sermaye {target_year}"] = format_number_tr(ppe_2025)
        data[f"Toplam Alacak {target_year}"] = format_number_tr(receivables_2025)
        data[f"Stok {target_year}"] = format_number_tr(0 if ticker == "GOOGL" and (inventory_2025 is None or pd.isna(inventory_2025)) else inventory_2025)
        data[f"Toplam Borç {target_year}"] = format_number_tr(liabilities_2025)
    else:
        print(f"{ticker}: No quarterly data found for {target_year}")
        data[f"Net Faaliyet Kârı {target_year}"] = ""
        data[f"Vergi {target_year}"] = ""
        data[f"Amortisman {target_year}"] = ""
        data[f"Sabit Sermaye {target_year}"] = ""
        data[f"Toplam Alacak {target_year}"] = ""
        data[f"Stok {target_year}"] = format_number_tr(0) if ticker == "GOOGL" else ""
        data[f"Toplam Borç {target_year}"] = ""

    # 2024-2021 için yıllık veriler
    for target_year in range(2024, 2020, -1):  # 2024, 2023, 2022, 2021
        found = False
        for date in income_stmt.columns:
            if date.year == target_year or (ticker == "AAPL" and date.year == target_year and date.month in [9, 10]):
                found = True
                try:
                    # Net Faaliyet Kârı
                    op_income_keys = ["Operating Income", "Total Operating Income"]
                    op_income = None
                    for key in op_income_keys:
                        if key in income_stmt.index:
                            op_income = income_stmt.loc[key, date]
                            break
                    data[f"Net Faaliyet Kârı {target_year}"] = format_number_tr(op_income)

                    # Vergi
                    tax_keys = ["Tax Provision", "Income Tax Expense"]
                    taxes = None
                    for key in tax_keys:
                        if key in income_stmt.index:
                            taxes = income_stmt.loc[key, date]
                            break
                    data[f"Vergi {target_year}"] = format_number_tr(taxes)

                    # Amortisman
                    depr_keys = ["Depreciation And Amortization", "Depreciation"]
                    depr = None
                    for key in depr_keys:
                        if key in cash_flow.index:
                            depr = cash_flow.loc[key, date]
                            break
                    data[f"Amortisman {target_year}"] = format_number_tr(depr)

                    # Sabit Sermaye
                    ppe_keys = ["Net PPE", "Property Plant Equipment"]
                    ppe = None
                    for key in ppe_keys:
                        if key in balance_sheet.index:
                            ppe = balance_sheet.loc[key, date]
                            break
                    data[f"Sabit Sermaye {target_year}"] = format_number_tr(ppe)

                    # Toplam Alacak
                    receivable_keys = ["Accounts Receivable", "Total Receivables"]
                    receivables = None
                    for key in receivable_keys:
                        if key in balance_sheet.index:
                            receivables = balance_sheet.loc[key, date]
                            break
                    data[f"Toplam Alacak {target_year}"] = format_number_tr(receivables)

                    # Stok
                    inventory_keys = ["Inventory", "Inventories"]
                    inventory = None
                    for key in inventory_keys:
                        if key in balance_sheet.index:
                            inventory = balance_sheet.loc[key, date]
                            break
                    if inventory is None or pd.isna(inventory):
                        inventory = 0 if ticker == "GOOGL" else None
                    data[f"Stok {target_year}"] = format_number_tr(inventory)

                    # Toplam Borç
                    liability_keys = ["Total Liabilities", "Total Liabilities Net Minority Interest"]
                    liabilities = None
                    for key in liability_keys:
                        if key in balance_sheet.index:
                            liabilities = balance_sheet.loc[key, date]
                            break
                    data[f"Toplam Borç {target_year}"] = format_number_tr(liabilities)

                except Exception as e:
                    print(f"Error for {ticker}: {target_year}: {e}")
                    data[f"Net Faaliyet Kârı {target_year}"] = ""
                    data[f"Vergi {target_year}"] = ""
                    data[f"Amortisman {target_year}"] = ""
                    data[f"Sabit Sermaye {target_year}"] = ""
                    data[f"Toplam Alacak {target_year}"] = ""
                    data[f"Stok {target_year}"] = format_number_tr(0) if ticker == "GOOGL" else ""
                    data[f"Toplam Borç {target_year}"] = ""
                break

        if not found:
            print(f"{ticker}: No data found for {target_year}")
            data[f"Net Faaliyet Kârı {target_year}"] = ""
            data[f"Vergi {target_year}"] = ""
            data[f"Amortisman {target_year}"] = ""
            data[f"Sabit Sermaye {target_year}"] = ""
            data[f"Toplam Alacak {target_year}"] = ""
            data[f"Stok {target_year}"] = format_number_tr(0) if ticker == "GOOGL" else ""
            data[f"Toplam Borç {target_year}"] = ""

    return data

with open("tickers.txt", "r") as f:
    tickers = [line.strip() for line in f if line.strip()]

# Tüm verileri topla
all_data = []
for ticker in tickers:
    try:
        print(f"{ticker} is being processed..")
        data = get_annual_data(ticker)
        all_data.append(data)
    except Exception as e:
        print(f"Error occurred for {ticker}: {e}")

# DataFrame oluştur
df = pd.DataFrame(all_data)

# Sütun sırasını düzenle
columns = ["Kod"]
metrics = [
    "Net Faaliyet Kârı",
    "Vergi",
    "Amortisman",
    "Sabit Sermaye",
    "Toplam Alacak",
    "Stok",
    "Toplam Borç"
]
for metric in metrics:
    for year in range(2025, 2020, -1):  # 2025, 2024, 2023, 2022, 2021
        columns.append(f"{metric} {year}")
df = df[columns]

# Excel'e kaydet
df.to_excel("dcf.xlsx", index=False, engine="openpyxl")
print("✅ Data saved in dcf.xlsx file")
