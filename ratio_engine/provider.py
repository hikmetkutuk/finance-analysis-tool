from dataclasses import dataclass
from typing import Any

from .dependencies import pd, yf


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

    def fetch(self, symbol: str) -> StockDataset:
        stock = yf.Ticker(symbol)
        info = stock.info if isinstance(stock.info, dict) else {}
        return StockDataset(
            info=info,
            quarterly_financials=self.get_frame(stock.quarterly_financials),
            quarterly_balance_sheet=self.get_frame(stock.quarterly_balance_sheet),
            annual_financials=self.get_frame(stock.financials),
            annual_balance_sheet=self.get_frame(stock.balance_sheet),
        )
