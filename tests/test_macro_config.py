from pathlib import Path

from data.macro_config import load_macro_config


def test_load_macro_config_defaults_when_missing(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing_macro.json"
    cfg = load_macro_config(missing_path)
    assert "tr" in cfg and "us" in cfg
    assert "defaults" in cfg["tr"]
    assert "defaults" in cfg["us"]
    assert cfg["tr"]["tax_rate"] > 0
    assert cfg["us"]["tax_rate"] > 0
