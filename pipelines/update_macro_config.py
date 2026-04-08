from __future__ import annotations

from datetime import date
from typing import Optional

import pandas as pd
import yfinance as yf

from data.macro_config import load_macro_config, save_macro_config


def fetch_last_close(ticker: str) -> Optional[float]:
    try:
        history = yf.Ticker(ticker).history(period="1mo", interval="1d")
    except (RuntimeError, ValueError, TypeError, KeyError, OSError):
        return None
    if history is None:
        return None
    if not isinstance(history, pd.DataFrame):
        return None
    if history.empty:
        return None
    if "Close" not in history.columns:
        return None
    close = history["Close"].dropna()
    if close.empty:
        return None
    try:
        return float(close.iloc[-1])
    except (TypeError, ValueError):
        return None


def first_available_close(candidates: list[str]) -> Optional[float]:
    for ticker in candidates:
        value = fetch_last_close(ticker)
        if value is not None and value > 0:
            return value
    return None


def update_us_block(config: dict) -> None:
    us = config["us"]
    us_10y = first_available_close(["^TNX"])
    us_2y = first_available_close(["^UST2Y", "US2YT=X", "^IRX"])
    if us_10y is not None:
        us["risk_free_rate"] = round(us_10y / 100.0, 4)
        us["cost_of_debt"] = round(us["risk_free_rate"] + 0.015, 4)
    if us_2y is not None:
        us["bond_yield_2"] = round(us_2y / 100.0, 4)
    us["source"] = "yfinance"


def update_tr_block(config: dict) -> None:
    tr = config["tr"]
    tr_2y = first_available_close(["TRY2YT=RR", "TR2YT=X", "^XU030"])
    if tr_2y is not None:
        inferred_rate = tr_2y / 100.0 if tr_2y > 2 else tr_2y
        tr["bond_yield_2"] = round(inferred_rate, 4)
        tr["risk_free_rate"] = round(inferred_rate, 4)
        tr["cost_of_debt"] = round(min(max(inferred_rate + 0.04, 0.20), 0.60), 4)
        tr["source"] = "yfinance_inferred"
    else:
        tr["source"] = "manual_fallback"


def main() -> None:
    config = load_macro_config()
    update_us_block(config)
    update_tr_block(config)
    config["as_of"] = date.today().isoformat()
    save_macro_config(config)
    print("Kaydedildi -> macro_config.json")
    print(f"US rf: {config['us']['risk_free_rate']}, TR rf: {config['tr']['risk_free_rate']}")


if __name__ == "__main__":
    main()
