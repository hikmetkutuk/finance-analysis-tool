from __future__ import annotations

from dataclasses import dataclass
import time
from typing import Any, Dict, Optional

import pandas as pd
import yfinance as yf
from yfinance.exceptions import YFRateLimitError

from .alpha_vantage_client import alpha_vantage_enabled, fetch_alpha_vantage_dataset
from .cache_store import load_fresh_cache, load_latest_cache, save_cache


FETCH_ERRORS = (YFRateLimitError, RuntimeError, ValueError, TypeError, KeyError, AttributeError, OSError)
FAST_INFO_KEYS = ("marketCap", "shares", "priceToBook", "lastPrice")
MAX_FETCH_ATTEMPTS = 3
FETCH_RETRY_DELAY_SECONDS = 0.75
TICKER_BUNDLE_CACHE_NAMESPACE = "ticker_bundle_v1"
TICKER_BUNDLE_CACHE_MAX_AGE_SECONDS = 6 * 60 * 60


@dataclass
class TickerBundle:
    ticker: str
    info: Dict[str, Any]
    fast_info: Dict[str, Any]
    financials: pd.DataFrame
    balance_sheet: pd.DataFrame
    cashflow: pd.DataFrame
    last_close: Optional[float]
    warnings: list[str]


def _dedupe_warnings(warnings: list[str]) -> list[str]:
    return list(dict.fromkeys(item for item in warnings if item))


def safe_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(number):
        return None
    return number


def as_dataframe(value: Any) -> pd.DataFrame:
    if isinstance(value, pd.DataFrame):
        return value
    return pd.DataFrame()


def as_string_dict(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    return {str(key): item for key, item in value.items()}


def _frame_has_rows(frame: pd.DataFrame) -> bool:
    return isinstance(frame, pd.DataFrame) and not frame.empty


def _serialize_bundle(bundle: TickerBundle) -> dict[str, Any]:
    return {
        "ticker": bundle.ticker,
        "info": dict(bundle.info),
        "fast_info": dict(bundle.fast_info),
        "financials": bundle.financials.copy(),
        "balance_sheet": bundle.balance_sheet.copy(),
        "cashflow": bundle.cashflow.copy(),
        "last_close": bundle.last_close,
        "warnings": list(bundle.warnings),
    }


def _deserialize_bundle(payload: Any) -> Optional[TickerBundle]:
    if not isinstance(payload, dict):
        return None
    ticker = payload.get("ticker")
    if not isinstance(ticker, str) or not ticker.strip():
        return None
    return TickerBundle(
        ticker=ticker.strip(),
        info=as_string_dict(payload.get("info")),
        fast_info=as_string_dict(payload.get("fast_info")),
        financials=as_dataframe(payload.get("financials")),
        balance_sheet=as_dataframe(payload.get("balance_sheet")),
        cashflow=as_dataframe(payload.get("cashflow")),
        last_close=safe_float(payload.get("last_close")),
        warnings=[str(item) for item in payload.get("warnings", []) if isinstance(item, str)],
    )


def _bundle_has_substantive_data(bundle: TickerBundle) -> bool:
    return bool(bundle.info) or bool(bundle.fast_info) or any(
        (
            _frame_has_rows(bundle.financials),
            _frame_has_rows(bundle.balance_sheet),
            _frame_has_rows(bundle.cashflow),
            bundle.last_close is not None,
        )
    )


def _load_cached_bundle(namespace: str, key: str, max_age_seconds: Optional[int] = None) -> Optional[TickerBundle]:
    if max_age_seconds is None:
        cached = load_latest_cache(namespace, key)
    else:
        cached = load_fresh_cache(namespace, key, max_age_seconds)
    if cached is None:
        return None
    return _deserialize_bundle(cached.payload)


def _merge_bundle_with_fallback(
    bundle: TickerBundle,
    fallback_bundle: Optional[TickerBundle],
    warning_label: str,
) -> TickerBundle:
    if fallback_bundle is None:
        return bundle

    used_fallback = False
    info = bundle.info
    if not info and fallback_bundle.info:
        info = dict(fallback_bundle.info)
        used_fallback = True

    fast_info = bundle.fast_info
    if not fast_info and fallback_bundle.fast_info:
        fast_info = dict(fallback_bundle.fast_info)
        used_fallback = True

    financials = bundle.financials
    if not _frame_has_rows(financials) and _frame_has_rows(fallback_bundle.financials):
        financials = fallback_bundle.financials.copy()
        used_fallback = True

    balance_sheet = bundle.balance_sheet
    if not _frame_has_rows(balance_sheet) and _frame_has_rows(fallback_bundle.balance_sheet):
        balance_sheet = fallback_bundle.balance_sheet.copy()
        used_fallback = True

    cashflow = bundle.cashflow
    if not _frame_has_rows(cashflow) and _frame_has_rows(fallback_bundle.cashflow):
        cashflow = fallback_bundle.cashflow.copy()
        used_fallback = True

    last_close = bundle.last_close
    if last_close is None and fallback_bundle.last_close is not None:
        last_close = fallback_bundle.last_close
        used_fallback = True

    warnings = list(bundle.warnings) + list(fallback_bundle.warnings)
    if used_fallback:
        warnings.append(warning_label)
    return TickerBundle(
        ticker=bundle.ticker,
        info=info,
        fast_info=fast_info,
        financials=financials,
        balance_sheet=balance_sheet,
        cashflow=cashflow,
        last_close=last_close,
        warnings=_dedupe_warnings(warnings),
    )


def _merge_bundle_with_cache(bundle: TickerBundle, cached_bundle: Optional[TickerBundle]) -> TickerBundle:
    return _merge_bundle_with_fallback(bundle, cached_bundle, "cache_backfill_used")


def _bundle_with_last_close_option(bundle: Optional[TickerBundle], include_last_close: bool) -> Optional[TickerBundle]:
    if bundle is None or include_last_close:
        return bundle
    return TickerBundle(
        ticker=bundle.ticker,
        info=dict(bundle.info),
        fast_info=dict(bundle.fast_info),
        financials=bundle.financials.copy(),
        balance_sheet=bundle.balance_sheet.copy(),
        cashflow=bundle.cashflow.copy(),
        last_close=None,
        warnings=list(bundle.warnings),
    )


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


def extract_fast_info(stock: yf.Ticker) -> tuple[Dict[str, Any], bool]:
    try:
        fast_info_obj = call_with_retries(lambda: stock.fast_info)
    except FETCH_ERRORS:
        return {}, True
    if fast_info_obj is None:
        return {}, True

    fast_info: Dict[str, Any] = {}
    had_error = False
    for key in FAST_INFO_KEYS:
        try:
            if hasattr(fast_info_obj, "get"):
                value = fast_info_obj.get(key)
            else:
                value = getattr(fast_info_obj, key, None)
        except FETCH_ERRORS:
            had_error = True
            continue
        if value is not None:
            fast_info[key] = value
    return fast_info, had_error


def get_last_close(stock: yf.Ticker) -> Optional[float]:
    try:
        history = call_with_retries(lambda: stock.history(period="5d", interval="1d"))
    except FETCH_ERRORS:
        return None
    if history is None:
        return None
    if not isinstance(history, pd.DataFrame):
        return None
    if history.empty:
        return None
    if "Close" not in history.columns:
        return None
    close_values = history["Close"].dropna()
    if close_values.empty:
        return None
    return safe_float(close_values.iloc[-1])


class FreshCacheTickerBundleProvider:
    @staticmethod
    def fetch(ticker: str, include_last_close: bool = True) -> Optional[TickerBundle]:
        cached_bundle = _load_cached_bundle(
            TICKER_BUNDLE_CACHE_NAMESPACE,
            ticker,
            max_age_seconds=TICKER_BUNDLE_CACHE_MAX_AGE_SECONDS,
        )
        return _bundle_with_last_close_option(cached_bundle, include_last_close)


class YahooLiveTickerBundleProvider:
    @staticmethod
    def fetch(ticker: str, include_last_close: bool = True) -> TickerBundle:
        stock = yf.Ticker(ticker)
        warnings: list[str] = []

        try:
            info = call_with_retries(lambda: stock.info)
            info = info if isinstance(info, dict) else {}
        except FETCH_ERRORS:
            info = {}
            warnings.append("info_unavailable")

        fast_info, fast_info_has_errors = extract_fast_info(stock)
        if fast_info_has_errors or not fast_info:
            warnings.append("fast_info_unavailable")

        try:
            financials = as_dataframe(call_with_retries(lambda: stock.financials))
        except FETCH_ERRORS:
            financials = pd.DataFrame()
            warnings.append("financials_unavailable")

        try:
            balance_sheet = as_dataframe(call_with_retries(lambda: stock.balance_sheet))
        except FETCH_ERRORS:
            balance_sheet = pd.DataFrame()
            warnings.append("balance_sheet_unavailable")

        try:
            cashflow = as_dataframe(call_with_retries(lambda: stock.cashflow))
        except FETCH_ERRORS:
            cashflow = pd.DataFrame()
            warnings.append("cashflow_unavailable")

        last_close = None
        if include_last_close:
            last_close = get_last_close(stock)
            if last_close is None:
                warnings.append("last_close_unavailable")

        return TickerBundle(
            ticker=ticker,
            info=info,
            fast_info=fast_info,
            financials=financials,
            balance_sheet=balance_sheet,
            cashflow=cashflow,
            last_close=last_close,
            warnings=_dedupe_warnings(warnings),
        )


class AlphaVantageTickerBundleProvider:
    @staticmethod
    def _fast_info_from_bundle(bundle: TickerBundle) -> Dict[str, Any]:
        info = bundle.info
        fast_info: Dict[str, Any] = {}
        if info.get("marketCap") is not None:
            fast_info["marketCap"] = info.get("marketCap")
        if info.get("sharesOutstanding") is not None:
            fast_info["shares"] = info.get("sharesOutstanding")
        if info.get("priceToBook") is not None:
            fast_info["priceToBook"] = info.get("priceToBook")
        if bundle.last_close is not None:
            fast_info["lastPrice"] = bundle.last_close
        return fast_info

    @staticmethod
    def fetch(ticker: str, include_last_close: bool = True) -> Optional[TickerBundle]:
        if not alpha_vantage_enabled():
            return None
        try:
            dataset = fetch_alpha_vantage_dataset(ticker)
        except FETCH_ERRORS:
            return None
        if dataset is None:
            return None
        last_close = dataset.last_close if include_last_close else None
        bundle = TickerBundle(
            ticker=ticker,
            info=as_string_dict(dataset.info),
            fast_info={},
            financials=dataset.annual_income.copy(),
            balance_sheet=dataset.annual_balance.copy(),
            cashflow=dataset.annual_cashflow.copy(),
            last_close=last_close,
            warnings=list(dataset.warnings),
        )
        return TickerBundle(
            ticker=bundle.ticker,
            info=bundle.info,
            fast_info=AlphaVantageTickerBundleProvider._fast_info_from_bundle(bundle),
            financials=bundle.financials,
            balance_sheet=bundle.balance_sheet,
            cashflow=bundle.cashflow,
            last_close=bundle.last_close,
            warnings=_dedupe_warnings(bundle.warnings),
        )


class StaleCacheTickerBundleProvider:
    @staticmethod
    def fetch(ticker: str, include_last_close: bool = True) -> Optional[TickerBundle]:
        cached_bundle = _load_cached_bundle(TICKER_BUNDLE_CACHE_NAMESPACE, ticker)
        return _bundle_with_last_close_option(cached_bundle, include_last_close)


class TickerBundleProviderChain:
    def __init__(self) -> None:
        self.fresh_cache_provider = FreshCacheTickerBundleProvider()
        self.live_provider = YahooLiveTickerBundleProvider()
        self.secondary_live_provider = AlphaVantageTickerBundleProvider()
        self.stale_cache_provider = StaleCacheTickerBundleProvider()

    def fetch(self, ticker: str, include_last_close: bool = True) -> TickerBundle:
        fresh_bundle = self.fresh_cache_provider.fetch(ticker, include_last_close=include_last_close)
        if fresh_bundle is not None:
            return fresh_bundle

        stale_bundle = self.stale_cache_provider.fetch(ticker, include_last_close=include_last_close)
        live_bundle = self.live_provider.fetch(ticker, include_last_close=include_last_close)
        secondary_live_bundle = self.secondary_live_provider.fetch(ticker, include_last_close=include_last_close)
        live_bundle = _merge_bundle_with_fallback(live_bundle, secondary_live_bundle, "secondary_provider_backfill_used")
        merged_bundle = _merge_bundle_with_cache(live_bundle, stale_bundle)
        if _bundle_has_substantive_data(merged_bundle):
            save_cache(TICKER_BUNDLE_CACHE_NAMESPACE, ticker, _serialize_bundle(merged_bundle))
            return merged_bundle
        if stale_bundle is not None:
            return TickerBundle(
                ticker=stale_bundle.ticker,
                info=dict(stale_bundle.info),
                fast_info=dict(stale_bundle.fast_info),
                financials=stale_bundle.financials.copy(),
                balance_sheet=stale_bundle.balance_sheet.copy(),
                cashflow=stale_bundle.cashflow.copy(),
                last_close=stale_bundle.last_close,
                warnings=_dedupe_warnings(list(stale_bundle.warnings) + merged_bundle.warnings + ["cache_fallback_stale"]),
            )
        return merged_bundle


def fetch_ticker_bundle(ticker: str, include_last_close: bool = True) -> TickerBundle:
    return TickerBundleProviderChain().fetch(ticker, include_last_close=include_last_close)


def coalesce_numeric(*values: Any) -> Optional[float]:
    for value in values:
        num = safe_float(value)
        if num is not None:
            return num
    return None


def normalized_info(bundle: TickerBundle) -> Dict[str, Optional[float]]:
    info = bundle.info
    fast = bundle.fast_info
    market_cap = coalesce_numeric(info.get("marketCap"), fast.get("marketCap"))
    current_price = coalesce_numeric(info.get("currentPrice"), fast.get("lastPrice"), bundle.last_close)
    implied_shares = market_cap / current_price if market_cap is not None and current_price not in (None, 0) else None
    normalized = {
        "beta": coalesce_numeric(info.get("beta"), 1.0),
        "marketCap": market_cap,
        "totalDebt": coalesce_numeric(info.get("totalDebt")),
        "interestRate": coalesce_numeric(info.get("interestRate")),
        "sharesOutstanding": coalesce_numeric(info.get("sharesOutstanding"), fast.get("shares")),
        "floatShares": coalesce_numeric(info.get("floatShares")),
        "impliedShares": implied_shares,
        "totalCash": coalesce_numeric(info.get("totalCash")),
        "trailingEps": coalesce_numeric(info.get("trailingEps")),
        "forwardEps": coalesce_numeric(info.get("forwardEps")),
        "trailingPE": coalesce_numeric(info.get("trailingPE")),
        "forwardPE": coalesce_numeric(info.get("forwardPE")),
        "enterpriseValue": coalesce_numeric(info.get("enterpriseValue")),
        "targetMeanPrice": coalesce_numeric(info.get("targetMeanPrice")),
        "targetMedianPrice": coalesce_numeric(info.get("targetMedianPrice")),
        "numberOfAnalystOpinions": coalesce_numeric(info.get("numberOfAnalystOpinions")),
        "earningsGrowth": coalesce_numeric(info.get("earningsGrowth")),
        "revenueGrowth": coalesce_numeric(info.get("revenueGrowth")),
        "dividendRate": coalesce_numeric(info.get("dividendRate"), 0.0),
        "ebitda": coalesce_numeric(info.get("ebitda")),
        "freeCashflow": coalesce_numeric(info.get("freeCashflow")),
        "operatingCashflow": coalesce_numeric(info.get("operatingCashflow")),
        "priceToBook": coalesce_numeric(info.get("priceToBook"), fast.get("priceToBook")),
        "bookValue": coalesce_numeric(info.get("bookValue")),
        "returnOnEquity": coalesce_numeric(info.get("returnOnEquity")),
        "currentPrice": current_price,
    }
    return normalized


def validate_bundle(bundle: TickerBundle, info: Dict[str, Optional[float]]) -> list[str]:
    warnings = list(bundle.warnings)
    if info.get("sharesOutstanding") is None and info.get("floatShares") is None:
        warnings.append("shares_missing")
    if info.get("marketCap") is None:
        warnings.append("market_cap_missing")
    if info.get("currentPrice") is None:
        warnings.append("price_missing")
    if info.get("trailingEps") is None:
        warnings.append("eps_missing")
    return warnings
