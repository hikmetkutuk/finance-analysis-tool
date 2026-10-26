from pathlib import Path

import pandas as pd
import pytest

from pipelines import refresh_market_pipeline as pipeline
from pipelines import update_macro_config


def test_validate_universe_requires_30_unique_is_tickers(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    (tmp_path / "xu030.txt").write_text("\n".join(f"T{i:02}.IS" for i in range(30)), encoding="utf-8")
    assert len(pipeline._validate_universe()) == 30

    (tmp_path / "xu030.txt").write_text("AKBNK\n", encoding="utf-8")
    with pytest.raises(ValueError, match="30 benzersiz"):
        pipeline._validate_universe()


def test_validate_multiples_requires_full_universe(tmp_path: Path) -> None:
    path = tmp_path / "multiples.csv"
    pd.DataFrame([{"sector": "Banka", "ticker_count_total": 29}]).to_csv(path, index=False)
    with pytest.raises(ValueError, match="30 XU030"):
        pipeline._validate_multiples(path)


def test_live_tr_macro_uses_provider_and_credit_spread(monkeypatch: pytest.MonkeyPatch) -> None:
    config = {"tr": {"risk_free_rate": 0.30}}
    monkeypatch.setattr(update_macro_config, "fetch_bist_rf", lambda fallback: 0.36)
    update_macro_config.apply_live_tr_block(config)
    assert config["tr"]["risk_free_rate"] == pytest.approx(0.36)
    assert config["tr"]["bond_yield_2"] == pytest.approx(0.36)
    assert config["tr"]["cost_of_debt"] == pytest.approx(0.41)
