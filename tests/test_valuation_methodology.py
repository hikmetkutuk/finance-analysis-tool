from __future__ import annotations

from math import sqrt

import pandas as pd
import pytest

import valuation
from data import sector_risk
from data.sector_risk import market_sector_peers
from valuation import (
    _calculate_dcf_scenarios,
    _compute_dcf_initial_growth,
    _fetch_consensus_y1,
    compute_margin_profile,
    compute_signal_quality_score,
    graham_valuation,
    resolve_market_beta,
)


def test_company_guidance_overrides_consensus(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(valuation.COMPANY_METADATA, "TEST.IS", {"revenue_growth_y1": 0.059})
    assert _fetch_consensus_y1("TEST.IS") == pytest.approx(0.059)
    assert _compute_dcf_initial_growth(0.059, 0.20, 0.15) == pytest.approx(0.059)


def test_missing_beta_uses_levered_sector_beta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        valuation,
        "SECTOR_RISK_CONFIG",
        {
            "sectors": {
                "tr:Havacılık": {"unlevered_beta": 0.70, "source": "live_sector_peer_median"}
            },
            "defaults": {},
        },
    )
    info = {"marketCap": 100.0, "totalDebt": 50.0, "beta": None}
    beta = resolve_market_beta(info, "Havacılık", 0.22, "tr")
    assert beta == pytest.approx(0.70 * (1 + 0.78 * 0.5))
    assert abs(beta - 1.0) > 1e-6


def test_reported_beta_takes_precedence() -> None:
    info = {"marketCap": 100.0, "totalDebt": 50.0, "beta": 1.12}
    assert resolve_market_beta(info, "Havacılık", 0.22, "tr") == pytest.approx(1.12)


def test_margin_profile_uses_latest_three_available_years() -> None:
    columns = pd.to_datetime(["2026-12-31", "2025-12-31", "2024-12-31", "2023-12-31"])
    income = pd.DataFrame(
        [
            [100.0, 100.0, 100.0, 100.0],
            [30.0, 20.0, 10.0, 90.0],
        ],
        index=["Total Revenue", "Operating Income"],
        columns=columns,
    )
    cashflow = pd.DataFrame(index=[], columns=columns)
    profile = compute_margin_profile(income, cashflow)
    assert profile["ebit_margin"] == pytest.approx(0.20)


def test_dcf_scenarios_use_configured_exit_multiple_and_are_ordered() -> None:
    params = {"terminal_growth": 0.025, "ev_ebitda": 8.0}
    inputs = {
        "latest_revenue": 1_000.0,
        "margin_profile": {"ebit_margin": 0.20, "da_pct": 0.05, "capex_pct": 0.06, "nwc_pct": 0.01},
        "initial_growth": 0.08,
        "wacc": 0.12,
        "debt": 300.0,
        "cash": 100.0,
        "shares": 10.0,
        "tax_rate": 0.22,
    }
    scenarios = _calculate_dcf_scenarios(params, inputs)
    assert scenarios["bear"] is not None
    assert scenarios["base"] is not None
    assert scenarios["bull"] is not None
    bear = scenarios["bear"]
    base = scenarios["base"]
    bull = scenarios["bull"]
    assert bear < base < bull

    higher_multiple = _calculate_dcf_scenarios({**params, "ev_ebitda": 15.0}, inputs)
    higher_base = higher_multiple["base"]
    assert higher_base is not None
    assert base < higher_base


def test_graham_valuation_uses_eps_and_book_value() -> None:
    assert graham_valuation(4.0, 10.0) == pytest.approx(sqrt(22.5 * 4.0 * 10.0))
    assert graham_valuation(4.0, None) is None


def test_dynamic_peer_pool_comes_from_sector_assignments() -> None:
    peers = market_sector_peers("tr", {"Havacılık"})
    assert "Havacılık" in peers
    assert len(peers["Havacılık"]) >= 3


def test_sector_beta_snapshot_is_generated_from_live_peers(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    assignments = {
        "tr": {
            "A.IS": "Test Sektör",
            "B.IS": "Test Sektör",
            "C.IS": "Test Sektör",
        }
    }
    infos = {
        ticker: {"beta": beta, "marketCap": 100.0, "totalDebt": 20.0, "effectiveTaxRate": 0.25}
        for ticker, beta in (("A.IS", 0.9), ("B.IS", 1.0), ("C.IS", 1.1))
    }
    monkeypatch.setattr(sector_risk, "load_sector_assignments", lambda: assignments)
    monkeypatch.setattr(sector_risk, "fetch_info", lambda ticker: infos[ticker])

    result = sector_risk.refresh_sector_risk_config(
        "tr", {"Test Sektör"}, tmp_path / "risk.json"
    )
    entry = result["sectors"]["tr:Test Sektör"]
    assert entry["sample_size"] == 3
    assert entry["source"] == "live_sector_peer_median"
    assert result["defaults"]["tr"]["source"] == "live_market_peer_median"


def test_quality_score_can_be_backtest_calibrated() -> None:
    valuations: dict[str, float | None] = {
        "fv_dcf": 100.0,
        "fv_relative": 102.0,
        "fv_ddm": 98.0,
        "fv_efk": 101.0,
        "fv_ndk": 99.0,
        "fv_graham": 97.0,
    }
    low_score, _ = compute_signal_quality_score(
        valuations, [], is_financial=False, historical_hit_rate=30.0
    )
    high_score, _ = compute_signal_quality_score(
        valuations, [], is_financial=False, historical_hit_rate=70.0
    )
    assert high_score > low_score
