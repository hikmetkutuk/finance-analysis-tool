from dataclasses import dataclass
from typing import Any

from .dependencies import NetworkRequestError, YFRateLimitError, pd, yf

FETCH_ERRORS = (
    RuntimeError,
    ValueError,
    TypeError,
    KeyError,
    AttributeError,
    OSError,
    NetworkRequestError,
    YFRateLimitError,
)


@dataclass
class StockDataset:
    info: dict
    quarterly_financials: Any
    quarterly_balance_sheet: Any
    annual_financials: Any
    annual_balance_sheet: Any


class YahooProvider:
    @staticmethod
    def get_frame(obj: Any) -> Any:
        return obj if isinstance(obj, pd.DataFrame) else pd.DataFrame()

    @staticmethod
    def get_info(stock: Any) -> dict:
        try:
            info = stock.info
        except FETCH_ERRORS:
            return {}
        return info if isinstance(info, dict) else {}

    @staticmethod
    def get_safe_frame(stock: Any, attr_name: str) -> Any:
        try:
            frame = getattr(stock, attr_name)
        except FETCH_ERRORS:
            return pd.DataFrame()
        return YahooProvider.get_frame(frame)

    def fetch(self, symbol: str) -> StockDataset:
        stock = yf.Ticker(symbol)
        info = self.get_info(stock)
        return StockDataset(
            info=info,
            quarterly_financials=self.get_safe_frame(stock, "quarterly_financials"),
            quarterly_balance_sheet=self.get_safe_frame(stock, "quarterly_balance_sheet"),
            annual_financials=self.get_safe_frame(stock, "financials"),
            annual_balance_sheet=self.get_safe_frame(stock, "balance_sheet"),
        )
