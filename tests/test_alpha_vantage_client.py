from __future__ import annotations

import math

import pandas as pd

from data.alpha_vantage_client import alpha_vantage_enabled, frame_from_reports


def test_alpha_vantage_disabled_without_api_key(monkeypatch) -> None:
    monkeypatch.delenv("ALPHAVANTAGE_API_KEY", raising=False)
    assert alpha_vantage_enabled() is False


def test_frame_from_reports_normalizes_financial_rows() -> None:
    reports = [
        {
            "fiscalDateEnding": "2025-12-31",
            "totalRevenue": "1000",
            "netIncome": "120",
        },
        {
            "fiscalDateEnding": "2024-12-31",
            "totalRevenue": "900",
            "netIncome": "100",
        },
    ]
    frame = frame_from_reports(
        reports,
        {
            "totalRevenue": "Total Revenue",
            "netIncome": "Net Income",
        },
    )
    assert isinstance(frame, pd.DataFrame)
    assert list(frame.index) == ["Total Revenue", "Net Income"]
    assert math.isclose(frame.loc["Total Revenue"].iloc[0], 1000.0)
    assert math.isclose(frame.loc["Net Income"].iloc[1], 100.0)
