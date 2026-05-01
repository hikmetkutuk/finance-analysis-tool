from dataclasses import dataclass
import time
from typing import Any

from data.cache_store import load_fresh_cache, load_latest_cache, save_cache

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
MAX_FETCH_ATTEMPTS = 3
FETCH_RETRY_DELAY_SECONDS = 0.75
RATIO_DATASET_CACHE_NAMESPACE = "ratio_dataset_v1"
RATIO_DATASET_CACHE_MAX_AGE_SECONDS = 12 * 60 * 60


@dataclass
class StockDataset:
    info: dict
    quarterly_financials: Any
    quarterly_balance_sheet: Any
    annual_financials: Any
    annual_balance_sheet: Any


def call_with_retries(loader):
    last_error = None
    for attempt in range(1, MAX_FETCH_ATTEMPTS + 1):
        try:
            return loader()
        except FETCH_ERRORS as error:
            last_error = error
            if attempt >= MAX_FETCH_ATTEMPTS:
                raise
            time.sleep(FETCH_RETRY_DELAY_SECONDS * attempt)
    if last_error is not None:
        raise last_error
    raise RuntimeError("retry loader exited unexpectedly")


class YahooProvider:
    @staticmethod
    def get_frame(obj: Any) -> Any:
        return obj if isinstance(obj, pd.DataFrame) else pd.DataFrame()

    @staticmethod
    def get_info(stock: Any) -> dict:
        try:
            info = call_with_retries(lambda: stock.info)
        except FETCH_ERRORS:
            return {}
        return info if isinstance(info, dict) else {}

    @staticmethod
    def get_safe_frame(stock: Any, attr_name: str) -> Any:
        try:
            frame = call_with_retries(lambda: getattr(stock, attr_name))
        except FETCH_ERRORS:
            return pd.DataFrame()
        return YahooProvider.get_frame(frame)

    @staticmethod
    def _serialize_dataset(dataset: StockDataset) -> dict:
        return {
            "info": dict(dataset.info),
            "quarterly_financials": YahooProvider.get_frame(dataset.quarterly_financials).copy(),
            "quarterly_balance_sheet": YahooProvider.get_frame(dataset.quarterly_balance_sheet).copy(),
            "annual_financials": YahooProvider.get_frame(dataset.annual_financials).copy(),
            "annual_balance_sheet": YahooProvider.get_frame(dataset.annual_balance_sheet).copy(),
        }

    @staticmethod
    def _deserialize_dataset(payload: Any) -> Any:
        if not isinstance(payload, dict):
            return None
        return StockDataset(
            info=payload.get("info") if isinstance(payload.get("info"), dict) else {},
            quarterly_financials=YahooProvider.get_frame(payload.get("quarterly_financials")),
            quarterly_balance_sheet=YahooProvider.get_frame(payload.get("quarterly_balance_sheet")),
            annual_financials=YahooProvider.get_frame(payload.get("annual_financials")),
            annual_balance_sheet=YahooProvider.get_frame(payload.get("annual_balance_sheet")),
        )

    @staticmethod
    def _has_rows(frame: Any) -> bool:
        return isinstance(frame, pd.DataFrame) and not frame.empty

    @staticmethod
    def _dataset_has_substantive_data(dataset: StockDataset) -> bool:
        return bool(dataset.info) or any(
            (
                YahooProvider._has_rows(dataset.quarterly_financials),
                YahooProvider._has_rows(dataset.quarterly_balance_sheet),
                YahooProvider._has_rows(dataset.annual_financials),
                YahooProvider._has_rows(dataset.annual_balance_sheet),
            )
        )

    @staticmethod
    def _load_cached_dataset(symbol: str, max_age_seconds: int | None = None) -> Any:
        if max_age_seconds is None:
            cached = load_latest_cache(RATIO_DATASET_CACHE_NAMESPACE, symbol)
        else:
            cached = load_fresh_cache(RATIO_DATASET_CACHE_NAMESPACE, symbol, max_age_seconds)
        if cached is None:
            return None
        return YahooProvider._deserialize_dataset(cached.payload)

    @staticmethod
    def _merge_dataset_with_cache(dataset: StockDataset, cached_dataset: Any) -> StockDataset:
        if not isinstance(cached_dataset, StockDataset):
            return dataset
        info = dataset.info if dataset.info else dict(cached_dataset.info)
        quarterly_financials = (
            dataset.quarterly_financials
            if YahooProvider._has_rows(dataset.quarterly_financials)
            else YahooProvider.get_frame(cached_dataset.quarterly_financials).copy()
        )
        quarterly_balance_sheet = (
            dataset.quarterly_balance_sheet
            if YahooProvider._has_rows(dataset.quarterly_balance_sheet)
            else YahooProvider.get_frame(cached_dataset.quarterly_balance_sheet).copy()
        )
        annual_financials = (
            dataset.annual_financials
            if YahooProvider._has_rows(dataset.annual_financials)
            else YahooProvider.get_frame(cached_dataset.annual_financials).copy()
        )
        annual_balance_sheet = (
            dataset.annual_balance_sheet
            if YahooProvider._has_rows(dataset.annual_balance_sheet)
            else YahooProvider.get_frame(cached_dataset.annual_balance_sheet).copy()
        )
        return StockDataset(
            info=info,
            quarterly_financials=quarterly_financials,
            quarterly_balance_sheet=quarterly_balance_sheet,
            annual_financials=annual_financials,
            annual_balance_sheet=annual_balance_sheet,
        )

    def fetch(self, symbol: str) -> StockDataset:
        stock = yf.Ticker(symbol)
        return StockDataset(
            info=self.get_info(stock),
            quarterly_financials=self.get_safe_frame(stock, "quarterly_financials"),
            quarterly_balance_sheet=self.get_safe_frame(stock, "quarterly_balance_sheet"),
            annual_financials=self.get_safe_frame(stock, "financials"),
            annual_balance_sheet=self.get_safe_frame(stock, "balance_sheet"),
        )


class FreshCacheDatasetProvider:
    def fetch(self, symbol: str) -> Any:
        return YahooProvider._load_cached_dataset(symbol, RATIO_DATASET_CACHE_MAX_AGE_SECONDS)


class StaleCacheDatasetProvider:
    def fetch(self, symbol: str) -> Any:
        return YahooProvider._load_cached_dataset(symbol)


class DatasetProviderChain:
    def __init__(self) -> None:
        self.fresh_cache_provider = FreshCacheDatasetProvider()
        self.live_provider = YahooProvider()
        self.stale_cache_provider = StaleCacheDatasetProvider()

    def fetch(self, symbol: str) -> StockDataset:
        fresh_cached_dataset = self.fresh_cache_provider.fetch(symbol)
        if isinstance(fresh_cached_dataset, StockDataset):
            return fresh_cached_dataset

        stale_cached_dataset = self.stale_cache_provider.fetch(symbol)
        live_dataset = self.live_provider.fetch(symbol)
        merged_dataset = YahooProvider._merge_dataset_with_cache(live_dataset, stale_cached_dataset)
        if YahooProvider._dataset_has_substantive_data(merged_dataset):
            save_cache(RATIO_DATASET_CACHE_NAMESPACE, symbol, YahooProvider._serialize_dataset(merged_dataset))
            return merged_dataset
        if isinstance(stale_cached_dataset, StockDataset):
            return stale_cached_dataset
        return merged_dataset
