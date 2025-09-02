import yfinance as yf
import pandas as pd
from typing import Iterable, Optional

# ------------------------------
# TR format
# ------------------------------
def format_number_tr(value):
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    try:
        return "{:,.2f}".format(float(value)).replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return ""

# ------------------------------
# Güvenli yardımcılar
# ------------------------------
def _is_df(df) -> bool:
    return isinstance(df, pd.DataFrame) and not df.empty

def _f(x) -> Optional[float]:
    try:
        return float(x)
    except Exception:
        return None

def _sum_quarterly_for_year(df: pd.DataFrame, row_names: Iterable[str], year: int) -> Optional[float]:
    """Verilen satır adlarından ilk bulunanı için ilgili yıldaki çeyreklerin toplamı."""
    if not _is_df(df):
        return None
    row = None
    for r in row_names:
        if r in df.index:
            row = r
            break
    if row is None:
        return None
    s = 0.0
    found = False
    for col in df.columns:
        try:
            if getattr(col, "year", None) == year:
                val = df.loc[row, col]
                if pd.notna(val):
                    s += float(val)
                    found = True
        except Exception:
            continue
    return s if found else None

def _last_quarter_value_in_year(df: pd.DataFrame, row_names: Iterable[str], year: int) -> Optional[float]:
    """
    İlgili yıl içindeki en SON çeyrek kolonundan değer. (Bilanço kalemleri için)
    """
    if not _is_df(df):
        return None
    row = None
    for r in row_names:
        if r in df.index:
            row = r
            break
    if row is None:
        return None
    # yıl sütunlarını tarihe göre sırala ve en sondakini al
    cols = [c for c in df.columns if getattr(c, "year", None) == year]
    if not cols:
        return None
    # Pandas DatetimeIndex soldan yeni gelebilir ama garantiye alalım:
    cols_sorted = sorted(cols)
    last_col = cols_sorted[-1]
    val = df.loc[row, last_col]
    return float(val) if pd.notna(val) else None

def _annual_value_for_year(df: pd.DataFrame, row_names: Iterable[str], target_year: int) -> Optional[float]:
    """
    Yıllık tabloda hedef yılın kolonu; yoksa en yakın yılın kolonu (fiscal kaymalar için).
    """
    if not _is_df(df):
        return None
    row = None
    for r in row_names:
        if r in df.index:
            row = r
            break
    if row is None:
        return None

    # Doğrudan aynı yıl
    for col in df.columns:
        if getattr(col, "year", None) == target_year:
            v = df.loc[row, col]
            return float(v) if pd.notna(v) else None

    # En yakın yıl fallback
    candidates = []
    for col in df.columns:
        y = getattr(col, "year", None)
        if y is not None:
            candidates.append((abs(y - target_year), y, col))
    if not candidates:
        return None
    candidates.sort(key=lambda x: x[0])  # en yakın yıl
    _, _, best_col = candidates[0]
    v = df.loc[row, best_col]
    return float(v) if pd.notna(v) else None

# ------------------------------
# Ana fonksiyon
# ------------------------------
def get_annual_data(ticker, years_back=5):
    stock = yf.Ticker(ticker)

    # Tablolar
    income_stmt = stock.financials if isinstance(stock.financials, pd.DataFrame) else pd.DataFrame()
    balance_sheet = stock.balance_sheet if isinstance(stock.balance_sheet, pd.DataFrame) else pd.DataFrame()
    cash_flow = stock.cashflow if isinstance(stock.cashflow, pd.DataFrame) else pd.DataFrame()

    q_income = stock.quarterly_financials if isinstance(stock.quarterly_financials, pd.DataFrame) else pd.DataFrame()
    q_balance = stock.quarterly_balance_sheet if isinstance(stock.quarterly_balance_sheet, pd.DataFrame) else pd.DataFrame()
    q_cash = stock.quarterly_cashflow if isinstance(stock.quarterly_cashflow, pd.DataFrame) else pd.DataFrame()

    data = {"Kod": ticker}

    # ---------- 2025: Quarterly-first ----------
    year_q = 2025

    op_income_2025 = _sum_quarterly_for_year(q_income, ["Operating Income", "Total Operating Income"], year_q)
    taxes_2025 = _sum_quarterly_for_year(q_income, ["Tax Provision", "Income Tax Expense"], year_q)
    depr_2025 = _sum_quarterly_for_year(q_cash, ["Depreciation And Amortization", "Depreciation"], year_q)

    ppe_2025 = _last_quarter_value_in_year(q_balance, ["Net PPE", "Property Plant Equipment"], year_q)
    receivables_2025 = _last_quarter_value_in_year(q_balance, ["Accounts Receivable", "Total Receivables"], year_q)
    inventory_2025 = _last_quarter_value_in_year(q_balance, ["Inventory", "Inventories"], year_q)
    liabilities_2025 = _last_quarter_value_in_year(q_balance, ["Total Liabilities", "Total Liabilities Net Minority Interest"], year_q)

    found_2025 = any(v is not None for v in [op_income_2025, taxes_2025, depr_2025, ppe_2025, receivables_2025, inventory_2025, liabilities_2025])

    if found_2025:
        data[f"Net Faaliyet Kârı {year_q}"] = format_number_tr(op_income_2025)
        data[f"Vergi {year_q}"] = format_number_tr(taxes_2025)
        data[f"Amortisman {year_q}"] = format_number_tr(depr_2025)
        data[f"Sabit Sermaye {year_q}"] = format_number_tr(ppe_2025)
        data[f"Toplam Alacak {year_q}"] = format_number_tr(receivables_2025)
        # GOOGL için stok yoksa 0 yaz
        inv_2025_out = 0 if ticker.upper() == "GOOGL" and (inventory_2025 is None) else inventory_2025
        data[f"Stok {year_q}"] = format_number_tr(inv_2025_out)
        data[f"Toplam Borç {year_q}"] = format_number_tr(liabilities_2025)
    else:
        # hiç çeyreklik yoksa boş bırak (GOOGL stok = 0 kuralını koru)
        data[f"Net Faaliyet Kârı {year_q}"] = ""
        data[f"Vergi {year_q}"] = ""
        data[f"Amortisman {year_q}"] = ""
        data[f"Sabit Sermaye {year_q}"] = ""
        data[f"Toplam Alacak {year_q}"] = ""
        data[f"Stok {year_q}"] = format_number_tr(0) if ticker.upper() == "GOOGL" else ""
        data[f"Toplam Borç {year_q}"] = ""

    # ---------- 2024–2021: Annual-first (fallback nearest year) ----------
    for target_year in range(2024, 2020, -1):  # 2024, 2023, 2022, 2021
        try:
            op_inc = _annual_value_for_year(income_stmt, ["Operating Income", "Total Operating Income"], target_year)
            taxes = _annual_value_for_year(income_stmt, ["Tax Provision", "Income Tax Expense"], target_year)
            depr = _annual_value_for_year(cash_flow, ["Depreciation And Amortization", "Depreciation"], target_year)
            ppe = _annual_value_for_year(balance_sheet, ["Net PPE", "Property Plant Equipment"], target_year)
            recv = _annual_value_for_year(balance_sheet, ["Accounts Receivable", "Total Receivables"], target_year)
            inv = _annual_value_for_year(balance_sheet, ["Inventory", "Inventories"], target_year)
            if inv is None and ticker.upper() == "GOOGL":
                inv = 0
            liab = _annual_value_for_year(balance_sheet, ["Total Liabilities", "Total Liabilities Net Minority Interest"], target_year)

            data[f"Net Faaliyet Kârı {target_year}"] = format_number_tr(op_inc)
            data[f"Vergi {target_year}"] = format_number_tr(taxes)
            data[f"Amortisman {target_year}"] = format_number_tr(depr)
            data[f"Sabit Sermaye {target_year}"] = format_number_tr(ppe)
            data[f"Toplam Alacak {target_year}"] = format_number_tr(recv)
            data[f"Stok {target_year}"] = format_number_tr(inv)
            data[f"Toplam Borç {target_year}"] = format_number_tr(liab)

        except Exception as e:
            # herhangi bir beklenmedik durumda boş bırak
            data[f"Net Faaliyet Kârı {target_year}"] = ""
            data[f"Vergi {target_year}"] = ""
            data[f"Amortisman {target_year}"] = ""
            data[f"Sabit Sermaye {target_year}"] = ""
            data[f"Toplam Alacak {target_year}"] = ""
            data[f"Stok {target_year}"] = format_number_tr(0) if ticker.upper() == "GOOGL" else ""
            data[f"Toplam Borç {target_year}"] = ""

    return data

# ------------------------------
# Koşum
# ------------------------------
if __name__ == "__main__":
    with open("tickers.txt", "r", encoding="utf-8") as f:
        tickers = [line.strip() for line in f if line.strip()]

    all_data = []
    for ticker in tickers:
        try:
            print(f"{ticker} is being processed..")
            data = get_annual_data(ticker)
            all_data.append(data)
        except Exception as e:
            print(f"Error occurred for {ticker}: {e}")

    df = pd.DataFrame(all_data)

    # Sütun sırası (2025 -> 2024 -> 2023 -> 2022 -> 2021)
    columns = ["Kod"]
    metrics = ["Net Faaliyet Kârı", "Vergi", "Amortisman", "Sabit Sermaye", "Toplam Alacak", "Stok", "Toplam Borç"]
    for metric in metrics:
        for year in range(2025, 2020, -1):
            columns.append(f"{metric} {year}")

    # Mevcut olanları al (bazı sembollerde eksik olabilir)
    columns_present = [c for c in columns if c in df.columns]
    df = df.reindex(columns=columns_present)

    df.to_excel("dcf.xlsx", index=False, engine="openpyxl")
    print("✅ Data saved in dcf.xlsx file")
