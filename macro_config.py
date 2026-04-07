from __future__ import annotations

import json
from copy import deepcopy
from datetime import date
from pathlib import Path
from typing import Any, Dict


MACRO_CONFIG_PATH = Path("macro_config.json")

DEFAULT_MACRO_CONFIG: Dict[str, Any] = {
    "as_of": date.today().isoformat(),
    "tr": {
        "risk_free_rate": 0.36,
        "market_premium": 0.08,
        "cost_of_debt": 0.40,
        "tax_rate": 0.25,
        "bond_yield_2": 0.36,
        "terminal_growth": 0.03,
        "ddm_growth": 0.025,
        "defaults": {"pe": 10.0, "pb": 1.2, "ev_ebitda": 7.0},
        "source": "manual_fallback",
    },
    "us": {
        "risk_free_rate": 0.042,
        "market_premium": 0.05,
        "cost_of_debt": 0.055,
        "tax_rate": 0.21,
        "bond_yield_2": 0.041,
        "terminal_growth": 0.03,
        "ddm_growth": 0.025,
        "defaults": {"pe": 22.0, "pb": 3.0, "ev_ebitda": 11.0},
        "source": "manual_fallback",
    },
}


def _deep_update(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    merged = deepcopy(base)
    for key, value in incoming.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_update(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_macro_config(path: Path = MACRO_CONFIG_PATH) -> Dict[str, Any]:
    if not path.exists():
        return deepcopy(DEFAULT_MACRO_CONFIG)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_MACRO_CONFIG)
    if not isinstance(raw, dict):
        return deepcopy(DEFAULT_MACRO_CONFIG)
    return _deep_update(DEFAULT_MACRO_CONFIG, raw)


def save_macro_config(config: Dict[str, Any], path: Path = MACRO_CONFIG_PATH) -> None:
    path.write_text(json.dumps(config, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
