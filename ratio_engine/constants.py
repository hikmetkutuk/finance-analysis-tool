TOTAL_ASSETS_KEY = "Total Assets"

COLUMN_TICKER = "Hisse"
COLUMN_COMPANY_NAME = "Şirket Adı"
COLUMN_FINANCIAL_SECTOR = "Finansal Sektor"
COLUMN_CURRENT_RATIO = "Cari Oran"
COLUMN_QUICK_RATIO = "Likit Oran"
COLUMN_CASH_RATIO = "Nakit Oran"
COLUMN_ROE = "Özsermaye Kârlılığı (ROE) (%) Yıllık"
COLUMN_PE = "F/K"
COLUMN_PRICE_TO_BOOK = "PD/DD"
COLUMN_EBITDA_GROWTH = "FAVÖK Büyüme (%) (Yıllık)"
COLUMN_PEG = "PEG Oranı"
COLUMN_ROIC = "ROIC (%)"
COLUMN_ASSET_TURNOVER = "Aktif Devir Hızı"
COLUMN_ERROR = "Hata"

DEFAULT_INPUT_FILE = "tickers.txt"
DEFAULT_OUTPUT_FILE = "ratio.xlsx"
DEFAULT_ERROR_FILE = "ratio_errors.csv"

MARKET_AUTO = "auto"
MARKET_TR = "tr"
MARKET_US = "us"

COLUMNS_ORDER = [
    COLUMN_TICKER,
    COLUMN_CURRENT_RATIO,
    COLUMN_QUICK_RATIO,
    COLUMN_CASH_RATIO,
    COLUMN_ROE,
    COLUMN_PE,
    COLUMN_PRICE_TO_BOOK,
    COLUMN_EBITDA_GROWTH,
    COLUMN_PEG,
    COLUMN_ROIC,
    COLUMN_ASSET_TURNOVER,
    COLUMN_FINANCIAL_SECTOR,
]

NON_NUMERIC_COLUMNS = {COLUMN_TICKER, COLUMN_FINANCIAL_SECTOR}
NUMERIC_COLUMNS = [column for column in COLUMNS_ORDER if column not in NON_NUMERIC_COLUMNS]

CURRENT_ASSET_KEYS = ["Current Assets", "Total Current Assets"]
CURRENT_LIABILITY_KEYS = ["Current Liabilities", "Total Current Liabilities"]
INVENTORY_KEYS = ["Inventory", "Inventories"]
CASH_KEYS = ["Cash And Cash Equivalents", "Cash And Cash Equivalents And Short Term Investments", "Cash"]
EQUITY_KEYS = ["Common Stock Equity", "Stockholders Equity", "Total Equity Gross Minority Interest"]
TOTAL_DEBT_KEYS = ["Total Debt"]
SHORT_DEBT_KEYS = ["Current Debt", "Current Debt And Capital Lease Obligation"]
LONG_DEBT_KEYS = ["Long Term Debt"]
