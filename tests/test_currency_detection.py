"""Tests for multi-currency BIST ticker detection and FX-cascade behaviour."""
from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pandas as pd
import pytest
import yfinance as yf

from valuation import (
    _FX_RATE_CACHE,
    _detect_reporting_currency,
    _fetch_fx_rate,
    calculate_wacc,
    get_country_params,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_info(**kwargs: Any) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "marketCap": 10_000.0,
        "totalDebt": 2_000.0,
        "beta": 1.0,
    }
    return {**defaults, **kwargs}


# ---------------------------------------------------------------------------
# 1. company_metadata.json exists and is loadable
# ---------------------------------------------------------------------------

def test_company_metadata_file_exists() -> None:
    """company_metadata.json must be present in the project root (= image root)."""
    meta_path = Path("company_metadata.json")
    assert meta_path.exists(), (
        "company_metadata.json not found — Dockerfile must COPY it into the image."
    )


def test_company_metadata_loadable() -> None:
    data = json.loads(Path("company_metadata.json").read_text(encoding="utf-8"))
    assert isinstance(data, dict), "company_metadata.json must be a JSON object."


# ---------------------------------------------------------------------------
# 2. Currency detection
# ---------------------------------------------------------------------------

def test_tavhl_detected_as_eur_via_metadata() -> None:
    """TAVHL.IS must be EUR regardless of yfinance info."""
    currency = _detect_reporting_currency("TAVHL.IS", {})
    assert currency == "EUR"


def test_dynamic_detection_from_yfinance_usd() -> None:
    """A ticker with financialCurrency=USD and no metadata override → USD."""
    currency = _detect_reporting_currency("THYAO.IS", {"financialCurrency": "USD"})
    assert currency == "USD"


def test_dynamic_detection_falls_back_to_try() -> None:
    """A ticker with no metadata and no financialCurrency → TRY."""
    currency = _detect_reporting_currency("AKBNK.IS", {})
    assert currency == "TRY"


def test_metadata_override_beats_yfinance() -> None:
    """Metadata override must win over yfinance financialCurrency."""
    currency = _detect_reporting_currency("TAVHL.IS", {"financialCurrency": "TRY"})
    assert currency == "EUR"


# ---------------------------------------------------------------------------
# 3. Parameter routing
# ---------------------------------------------------------------------------

def test_eur_bist_uses_eur_tr_params() -> None:
    params = get_country_params("TAVHL.IS", "EUR")
    assert math.isclose(params["risk_free_rate"], 0.028, rel_tol=1e-6)


def test_usd_bist_uses_usd_tr_params() -> None:
    params = get_country_params("THYAO.IS", "USD")
    assert math.isclose(params["risk_free_rate"], 0.0464, rel_tol=1e-6)


def test_try_bist_uses_tr_params() -> None:
    params = get_country_params("AKBNK.IS", "TRY")
    assert params["risk_free_rate"] > 0.30, "TR rf must be >30% (TCMB policy rate)"


# ---------------------------------------------------------------------------
# 4. WACC: marketCap and totalDebt normalized to reporting currency
# ---------------------------------------------------------------------------

def test_wacc_debt_and_equity_same_currency_eur() -> None:
    """When TAVHL marketCap is passed in EUR, totalDebt must also be in EUR."""
    fx_rate = 40.0  # 1 EUR = 40 TRY
    market_cap_try = 10_000.0
    total_debt_try = 2_000.0
    params = get_country_params("TAVHL.IS", "EUR")

    wacc_info = _make_info(
        marketCap=market_cap_try / fx_rate,   # EUR
        totalDebt=total_debt_try / fx_rate,   # EUR
    )
    wacc, _, _ = calculate_wacc(wacc_info, params)
    assert 0.05 < wacc < 0.25, f"WACC out of plausible range: {wacc:.4f}"


def test_wacc_mixed_currencies_produces_wrong_result() -> None:
    """Passing TRY totalDebt with EUR marketCap gives distorted D/V ratio."""
    fx_rate = 40.0
    market_cap_try = 10_000.0
    total_debt_try = 2_000.0
    params = get_country_params("TAVHL.IS", "EUR")

    # Mixed: marketCap in EUR, totalDebt still in TRY (the bug scenario)
    wacc_mixed = _make_info(
        marketCap=market_cap_try / fx_rate,
        totalDebt=total_debt_try,  # TRY — 40× too large
    )
    # Correct: both in EUR
    wacc_correct = _make_info(
        marketCap=market_cap_try / fx_rate,
        totalDebt=total_debt_try / fx_rate,
    )

    wacc_bad, _, _ = calculate_wacc(wacc_mixed, params)
    wacc_good, _, _ = calculate_wacc(wacc_correct, params)
    # Mixed WACC must differ materially (debt weight inflated ~40×)
    assert abs(wacc_bad - wacc_good) > 0.01, "Mixed-currency WACC should differ from correct one"


# ---------------------------------------------------------------------------
# 5. FX rate cache and failure
# ---------------------------------------------------------------------------

def test_fx_cache_returns_stale_on_failure() -> None:
    """Cache must serve stale value when live fetch fails."""
    pair = "EURTRY=X"
    _FX_RATE_CACHE[pair] = {"ts": time.time() - 9999, "val": 38.5}

    with patch.object(yf, "Ticker", side_effect=OSError("network error")):
        warnings: list[str] = []
        rate = _fetch_fx_rate(pair, warnings)

    assert rate == pytest.approx(38.5)
    assert any("kuru alınamadı" in w for w in warnings)
    del _FX_RATE_CACHE[pair]


def test_fx_cache_returns_none_when_empty_and_fails() -> None:
    """With no cached value and a failing fetch, return None."""
    pair = "FAKECCY=X"
    _FX_RATE_CACHE.pop(pair, None)

    with patch.object(yf, "Ticker", side_effect=OSError("network error")):
        rate = _fetch_fx_rate(pair)

    assert rate is None


# ---------------------------------------------------------------------------
# 6. FX absent → invalid models disabled
# ---------------------------------------------------------------------------

def _run_valuations_with_no_fx(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Run value_ticker for TAVHL with FX fetch always returning None."""
    from valuation import value_ticker

    empty_df = MagicMock(spec=pd.DataFrame)
    empty_df.__bool__ = lambda self: False
    empty_df.empty = True

    fake_bundle = MagicMock()
    fake_bundle.financials = empty_df
    fake_bundle.cashflow = empty_df
    fake_bundle.balance_sheet = empty_df

    fake_info: dict[str, Any] = {
        "currentPrice": 265.0,
        "marketCap": 26_500_000_000,
        "totalDebt": 1_000_000_000,
        "totalCash": 500_000_000,
        "sharesOutstanding": 100_000_000,
        "beta": 0.9,
        "trailingEps": 21.0,
        "financialCurrency": "EUR",
        "dividendRate": None,
    }

    monkeypatch.setattr("valuation._fetch_fx_rate", lambda *a, **kw: None)

    with (
        patch("valuation.fetch_ticker_bundle", return_value=fake_bundle),
        patch("valuation.normalized_info", return_value=fake_info),
        patch("valuation.validate_bundle", return_value=[]),
        patch("valuation._fetch_consensus_y1", return_value=None),
    ):
        result = value_ticker("TAVHL.IS")

    return result


def test_dcf_disabled_when_fx_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_valuations_with_no_fx(monkeypatch)
    valuations = result.get("valuations", {})
    assert valuations.get("fv_dcf") is None, "DCF must be None when FX rate unavailable"


def test_ddm_disabled_when_fx_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_valuations_with_no_fx(monkeypatch)
    valuations = result.get("valuations", {})
    assert valuations.get("fv_ddm") is None, "DDM must be None when FX rate unavailable"


def test_efk_ndk_disabled_when_fx_unavailable(monkeypatch: pytest.MonkeyPatch) -> None:
    result = _run_valuations_with_no_fx(monkeypatch)
    valuations = result.get("valuations", {})
    assert valuations.get("fv_efk") is None, "EFK must be None when FX rate unavailable"
    assert valuations.get("fv_ndk") is None, "NDK must be None when FX rate unavailable"
