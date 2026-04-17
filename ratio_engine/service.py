import logging
from typing import Iterable, List, Optional, Tuple

from .constants import (
    COLUMN_ASSET_TURNOVER,
    COLUMN_CASH_RATIO,
    COLUMN_COMPANY_NAME,
    COLUMN_CURRENT_RATIO,
    COLUMN_EBITDA_GROWTH,
    COLUMN_ERROR,
    COLUMN_FINANCIAL_SECTOR,
    COLUMN_PEG,
    COLUMN_PE,
    COLUMN_PRICE_TO_BOOK,
    COLUMN_QUICK_RATIO,
    COLUMN_ROE,
    COLUMN_ROIC,
    COLUMN_TICKER,
    MARKET_AUTO,
)
from .dependencies import NetworkRequestError, YFRateLimitError
from .metrics import (
    _f,
    build_liquidity_metrics,
    calculate_asset_turnover,
    calculate_peg,
    calculate_roe,
    calculate_roic,
    extract_balance_sheet_values,
    is_financial_company,
    yoy_growth_from_annual_or_quarterly,
)
from .profiles import get_profile
from .provider import StockDataset, YahooProvider

logger = logging.getLogger("ratio")


def build_stock_row(symbol: str, dataset: StockDataset, market: str) -> dict:
    profile = get_profile(market, symbol)
    info = dataset.info
    financial_company = is_financial_company(info, profile)
    (
        current_assets,
        current_liabilities,
        inventory,
        cash_like,
        equity_current,
        equity_previous,
    ) = extract_balance_sheet_values(dataset.quarterly_balance_sheet, dataset.annual_balance_sheet)

    result_row = {
        COLUMN_TICKER: symbol,
        COLUMN_COMPANY_NAME: info.get("longName") or info.get("shortName") or "",
        COLUMN_FINANCIAL_SECTOR: financial_company,
        COLUMN_PE: _f(info.get("trailingPE")),
        COLUMN_PRICE_TO_BOOK: _f(info.get("priceToBook")),
    }

    liquidity_values = build_liquidity_metrics(current_assets, current_liabilities, inventory, cash_like)
    if financial_company:
        liquidity_values = {
            COLUMN_CURRENT_RATIO: None,
            COLUMN_QUICK_RATIO: None,
            COLUMN_CASH_RATIO: None,
        }
    result_row.update(liquidity_values)
    result_row[COLUMN_ROE] = calculate_roe(
        dataset.quarterly_financials,
        info,
        equity_current,
        equity_previous,
    )

    ebitda_growth = yoy_growth_from_annual_or_quarterly(dataset.annual_financials, dataset.quarterly_financials, "EBITDA")
    if ebitda_growth is None:
        ebitda_growth = yoy_growth_from_annual_or_quarterly(dataset.annual_financials, dataset.quarterly_financials, "Operating Income")
    result_row[COLUMN_EBITDA_GROWTH] = ebitda_growth
    result_row[COLUMN_PEG] = calculate_peg(info)
    result_row[COLUMN_ROIC] = None
    result_row[COLUMN_ASSET_TURNOVER] = None
    if not financial_company:
        result_row[COLUMN_ROIC] = calculate_roic(
            info,
            dataset.quarterly_financials,
            dataset.quarterly_balance_sheet,
            dataset.annual_balance_sheet,
            equity_current,
            cash_like,
            profile.default_tax_rate,
        )
        result_row[COLUMN_ASSET_TURNOVER] = calculate_asset_turnover(
            dataset.quarterly_financials,
            dataset.quarterly_balance_sheet,
            dataset.annual_balance_sheet,
        )
    return result_row


def get_stock_data(symbol: str, market: str = MARKET_AUTO, provider: Optional[YahooProvider] = None) -> dict:
    active_provider = provider or YahooProvider()
    dataset = active_provider.fetch(symbol)
    return build_stock_row(symbol, dataset, market)


def analyze_symbols(
    symbols: Iterable[str],
    market: str = MARKET_AUTO,
    provider: Optional[YahooProvider] = None,
) -> Tuple[List[dict], List[dict]]:
    active_provider = provider or YahooProvider()
    rows: List[dict] = []
    failed_symbols: List[dict] = []
    for symbol in symbols:
        try:
            logger.info("%s is being processed..", symbol)
            rows.append(get_stock_data(symbol, market=market, provider=active_provider))
        except (RuntimeError, ValueError, TypeError, KeyError, IndexError, OSError, NetworkRequestError, YFRateLimitError) as error:
            failed_symbols.append({COLUMN_TICKER: symbol, COLUMN_ERROR: str(error)})
            logger.warning("Error occurred for %s: %s", symbol, error)
    return rows, failed_symbols
