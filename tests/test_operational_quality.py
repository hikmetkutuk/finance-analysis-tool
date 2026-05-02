from __future__ import annotations

import argparse
import math
from pathlib import Path

import pandas as pd

from data.sector_override_builder import sanitize_metrics
from main import build_run_metadata, finalize_run_metadata
from reporting.template_report import SECTION_COLUMN, TOPIC_COLUMN, build_notes_frame


def test_sanitize_metrics_drops_out_of_range_values() -> None:
    metrics = sanitize_metrics({"pe": 120.0, "pb": 5.0, "ev_ebitda": -8.0})
    assert metrics == {"pb": 5.0}


def test_build_notes_frame_includes_run_metadata_section() -> None:
    frame = build_notes_frame(
        {
            "started_at": "2026-05-01T12:00:00+00:00",
            "input_path": "coverage.txt",
            "output_path": "investment_report.xlsx",
            "tickers_total": 2,
        }
    )
    run_rows = frame[frame[SECTION_COLUMN] == "Çalıştırma"]
    assert not run_rows.empty
    assert "started_at" in set(run_rows[TOPIC_COLUMN])
    assert "Veri Sağlayıcı" in set(frame[TOPIC_COLUMN])


def test_finalize_run_metadata_adds_summary_fields() -> None:
    args = argparse.Namespace(
        input="coverage.txt",
        include_backtest=False,
        financials_workers=4,
    )
    metadata = build_run_metadata(
        args,
        ["AKBNK.IS", "AAPL"],
        "investment_report.xlsx",
        Path("logs/investment_report.log"),
        Path("investment_report.run.json"),
        "2026-05-01T12:00:00+00:00",
    )
    finalized = finalize_run_metadata(
        metadata,
        elapsed_seconds=12.34,
        valuation_frame=pd.DataFrame([{"x": 1}]),
        ratio_frame=pd.DataFrame([{"x": 1}, {"x": 2}]),
        financials_frame=pd.DataFrame(),
    )
    assert math.isclose(finalized["elapsed_seconds"], 12.34)
    assert finalized["valuation_rows"] == 1
    assert finalized["ratio_rows"] == 2
    assert finalized["market_counts"] == {"tr": 1, "us": 1}
