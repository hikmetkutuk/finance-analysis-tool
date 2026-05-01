from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


RATIO_PROFILE_CONFIG_PATH = Path(__file__).resolve().parent.parent / "ratio_profiles.json"
CATEGORY_LIQUIDITY = "Likidite"
CATEGORY_PROFITABILITY = "Karlılık"
CATEGORY_VALUATION = "Değerleme"
CATEGORY_GROWTH = "Büyüme"
CATEGORY_EFFICIENCY = "Verimlilik"

DEFAULT_RATIO_PROFILE_CONFIG: dict[str, Any] = {
    "profiles": {
        "Finansal": {
            "missing_penalty": 0.12,
            "metrics": {
                "roe": {"category": CATEGORY_PROFITABILITY, "kind": "band", "weight": 1.3, "soft_min": 4.0, "target_min": 12.0, "target_max": 24.0, "soft_max": 38.0},
                "pe": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 1.0, "soft_min": 1.0, "target_min": 4.0, "target_max": 12.0, "soft_max": 24.0},
                "pb": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.9, "soft_min": 0.2, "target_min": 0.7, "target_max": 2.2, "soft_max": 4.5},
                "peg": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.4, "soft_min": 0.2, "target_min": 0.6, "target_max": 1.8, "soft_max": 3.0}
            }
        },
        "Büyüme/Teknoloji": {
            "missing_penalty": 0.15,
            "metrics": {
                "current_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.4, "soft_min": 0.4, "target_min": 1.0, "target_max": 3.0, "soft_max": 6.0},
                "quick_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.4, "soft_min": 0.3, "target_min": 0.8, "target_max": 2.5, "soft_max": 5.0},
                "cash_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.2, "soft_min": 0.02, "target_min": 0.10, "target_max": 1.2, "soft_max": 2.0},
                "roe": {"category": CATEGORY_PROFITABILITY, "kind": "band", "weight": 0.8, "soft_min": 0.0, "target_min": 10.0, "target_max": 25.0, "soft_max": 40.0},
                "roic": {"category": CATEGORY_PROFITABILITY, "kind": "min", "weight": 0.9, "soft_min": 0.0, "target_min": 12.0},
                "pe": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.8, "soft_min": 4.0, "target_min": 10.0, "target_max": 30.0, "soft_max": 60.0},
                "pb": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.7, "soft_min": 0.8, "target_min": 2.0, "target_max": 8.0, "soft_max": 15.0},
                "peg": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.9, "soft_min": 0.3, "target_min": 0.8, "target_max": 1.8, "soft_max": 3.5},
                "ebitda_growth": {"category": CATEGORY_GROWTH, "kind": "min", "weight": 1.3, "soft_min": -5.0, "target_min": 25.0},
                "asset_turnover": {"category": CATEGORY_EFFICIENCY, "kind": "min", "weight": 0.6, "soft_min": 0.15, "target_min": 0.70}
            }
        },
        "Gayrimenkul": {
            "missing_penalty": 0.16,
            "metrics": {
                "current_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.5, "soft_min": 0.4, "target_min": 1.0, "target_max": 2.5, "soft_max": 4.0},
                "quick_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.3, "soft_min": 0.3, "target_min": 0.8, "target_max": 2.0, "soft_max": 3.5},
                "cash_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.2, "soft_min": 0.02, "target_min": 0.10, "target_max": 0.8, "soft_max": 1.5},
                "roe": {"category": CATEGORY_PROFITABILITY, "kind": "band", "weight": 0.9, "soft_min": 2.0, "target_min": 10.0, "target_max": 22.0, "soft_max": 35.0},
                "roic": {"category": CATEGORY_PROFITABILITY, "kind": "min", "weight": 0.4, "soft_min": 1.0, "target_min": 8.0},
                "pe": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.8, "soft_min": 1.0, "target_min": 5.0, "target_max": 16.0, "soft_max": 30.0},
                "pb": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 1.1, "soft_min": 0.2, "target_min": 0.6, "target_max": 1.8, "soft_max": 3.5},
                "peg": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.4, "soft_min": 0.2, "target_min": 0.6, "target_max": 1.6, "soft_max": 3.0},
                "ebitda_growth": {"category": CATEGORY_GROWTH, "kind": "min", "weight": 0.6, "soft_min": -10.0, "target_min": 12.0},
                "asset_turnover": {"category": CATEGORY_EFFICIENCY, "kind": "min", "weight": 0.4, "soft_min": 0.05, "target_min": 0.35}
            }
        },
        "Holding": {
            "missing_penalty": 0.16,
            "metrics": {
                "current_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.5, "soft_min": 0.4, "target_min": 1.0, "target_max": 2.5, "soft_max": 4.0},
                "quick_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.3, "soft_min": 0.3, "target_min": 0.8, "target_max": 2.0, "soft_max": 3.5},
                "cash_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.2, "soft_min": 0.02, "target_min": 0.10, "target_max": 0.8, "soft_max": 1.5},
                "roe": {"category": CATEGORY_PROFITABILITY, "kind": "band", "weight": 0.8, "soft_min": 2.0, "target_min": 10.0, "target_max": 20.0, "soft_max": 32.0},
                "pe": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.8, "soft_min": 1.0, "target_min": 4.0, "target_max": 14.0, "soft_max": 28.0},
                "pb": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 1.1, "soft_min": 0.2, "target_min": 0.6, "target_max": 1.6, "soft_max": 3.0},
                "peg": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.3, "soft_min": 0.2, "target_min": 0.6, "target_max": 1.5, "soft_max": 2.8},
                "ebitda_growth": {"category": CATEGORY_GROWTH, "kind": "min", "weight": 0.5, "soft_min": -10.0, "target_min": 10.0}
            }
        },
        "Enerji Utility/Altyapı": {
            "missing_penalty": 0.17,
            "metrics": {
                "current_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.4, "soft_min": 0.4, "target_min": 1.0, "target_max": 2.4, "soft_max": 4.5},
                "quick_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.3, "soft_min": 0.3, "target_min": 0.8, "target_max": 1.8, "soft_max": 3.5},
                "cash_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.2, "soft_min": 0.02, "target_min": 0.08, "target_max": 0.7, "soft_max": 1.4},
                "roe": {"category": CATEGORY_PROFITABILITY, "kind": "band", "weight": 0.9, "soft_min": 3.0, "target_min": 10.0, "target_max": 22.0, "soft_max": 35.0},
                "roic": {"category": CATEGORY_PROFITABILITY, "kind": "min", "weight": 0.6, "soft_min": 2.0, "target_min": 10.0},
                "pe": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.9, "soft_min": 2.0, "target_min": 6.0, "target_max": 16.0, "soft_max": 28.0},
                "pb": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.7, "soft_min": 0.3, "target_min": 0.8, "target_max": 2.8, "soft_max": 5.0},
                "peg": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.5, "soft_min": 0.2, "target_min": 0.7, "target_max": 1.6, "soft_max": 3.0},
                "ebitda_growth": {"category": CATEGORY_GROWTH, "kind": "min", "weight": 0.7, "soft_min": -8.0, "target_min": 10.0},
                "asset_turnover": {"category": CATEGORY_EFFICIENCY, "kind": "min", "weight": 0.5, "soft_min": 0.10, "target_min": 0.45}
            }
        },
        "Enerji Ekipman/Taahhüt": {
            "missing_penalty": 0.16,
            "metrics": {
                "current_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.5, "soft_min": 0.5, "target_min": 1.2, "target_max": 2.6, "soft_max": 4.5},
                "quick_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.3, "soft_min": 0.4, "target_min": 0.9, "target_max": 2.1, "soft_max": 3.5},
                "cash_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.2, "soft_min": 0.03, "target_min": 0.12, "target_max": 0.9, "soft_max": 1.8},
                "roe": {"category": CATEGORY_PROFITABILITY, "kind": "band", "weight": 1.0, "soft_min": 4.0, "target_min": 12.0, "target_max": 26.0, "soft_max": 40.0},
                "roic": {"category": CATEGORY_PROFITABILITY, "kind": "min", "weight": 0.8, "soft_min": 3.0, "target_min": 12.0},
                "pe": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.9, "soft_min": 2.0, "target_min": 6.0, "target_max": 18.0, "soft_max": 35.0},
                "pb": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.7, "soft_min": 0.4, "target_min": 1.0, "target_max": 3.0, "soft_max": 6.0},
                "peg": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.8, "soft_min": 0.2, "target_min": 0.7, "target_max": 1.6, "soft_max": 3.0},
                "ebitda_growth": {"category": CATEGORY_GROWTH, "kind": "min", "weight": 1.0, "soft_min": -10.0, "target_min": 18.0},
                "asset_turnover": {"category": CATEGORY_EFFICIENCY, "kind": "min", "weight": 0.7, "soft_min": 0.20, "target_min": 0.90}
            }
        },
        "Genel Sanayi": {
            "missing_penalty": 0.18,
            "metrics": {
                "current_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.5, "soft_min": 0.5, "target_min": 1.2, "target_max": 2.5, "soft_max": 4.5},
                "quick_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.3, "soft_min": 0.3, "target_min": 0.9, "target_max": 2.0, "soft_max": 3.5},
                "cash_ratio": {"category": CATEGORY_LIQUIDITY, "kind": "band", "weight": 0.2, "soft_min": 0.03, "target_min": 0.12, "target_max": 0.8, "soft_max": 1.6},
                "roe": {"category": CATEGORY_PROFITABILITY, "kind": "band", "weight": 0.9, "soft_min": 5.0, "target_min": 15.0, "target_max": 28.0, "soft_max": 42.0},
                "roic": {"category": CATEGORY_PROFITABILITY, "kind": "min", "weight": 0.8, "soft_min": 4.0, "target_min": 14.0},
                "pe": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.9, "soft_min": 2.0, "target_min": 6.0, "target_max": 18.0, "soft_max": 35.0},
                "pb": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.7, "soft_min": 0.4, "target_min": 0.9, "target_max": 2.5, "soft_max": 5.0},
                "peg": {"category": CATEGORY_VALUATION, "kind": "band", "weight": 0.7, "soft_min": 0.2, "target_min": 0.6, "target_max": 1.5, "soft_max": 3.0},
                "ebitda_growth": {"category": CATEGORY_GROWTH, "kind": "min", "weight": 0.9, "soft_min": -10.0, "target_min": 18.0},
                "asset_turnover": {"category": CATEGORY_EFFICIENCY, "kind": "min", "weight": 0.7, "soft_min": 0.20, "target_min": 0.90}
            }
        }
    }
}


def _deep_update(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in incoming.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_update(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_ratio_profile_config(path: Path = RATIO_PROFILE_CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return deepcopy(DEFAULT_RATIO_PROFILE_CONFIG)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_RATIO_PROFILE_CONFIG)
    if not isinstance(raw, dict):
        return deepcopy(DEFAULT_RATIO_PROFILE_CONFIG)
    return _deep_update(DEFAULT_RATIO_PROFILE_CONFIG, raw)


def build_ratio_profile_map(config: dict[str, Any]) -> dict[str, Any]:
    raw_profiles = config.get("profiles", {})
    if not isinstance(raw_profiles, dict):
        return deepcopy(DEFAULT_RATIO_PROFILE_CONFIG["profiles"])
    merged = _deep_update(DEFAULT_RATIO_PROFILE_CONFIG["profiles"], raw_profiles)
    return merged if isinstance(merged, dict) else deepcopy(DEFAULT_RATIO_PROFILE_CONFIG["profiles"])
