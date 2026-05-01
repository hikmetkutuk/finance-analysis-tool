from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


VALUATION_PROFILE_CONFIG_PATH = Path(__file__).resolve().parent.parent / "valuation_profiles.json"

DEFAULT_VALUATION_PROFILE_CONFIG: dict[str, Any] = {
    "profile_notes": {
        "Finansal": "Banka, sigorta ve finansal hizmetler. Defter değeri, ROE ve özsermaye maliyeti modelleri daha yüksek ağırlıklıdır.",
        "Büyüme/Teknoloji": "Teknoloji, yarı iletken, e-ticaret ve büyüme karakteri yüksek sektörler. İleri HBK/FK, sektör FK, EV/EBITDA ve DCF/INA ağırlıklıdır; defter değeri ve trailing terminal modeller düşük uygunluk nedeniyle dışarıda bırakılır.",
        "Enerji Utility/Altyapı": "Elektrik üretim/dağıtım, utility ve altyapı karakteri baskın şirketler. EV/EBITDA, terminal gelir ve DCF ağırlığı yüksek tutulur; ancak çarpan ve karlılık modelleri artık düşük ama pozitif ağırlık alır.",
        "Enerji Ekipman/Taahhüt": "Enerji ekipman, EPC/taahhüt, kablo, inverter, trafo ve proje odaklı sanayi şirketleri. İleri FK, sektör FK ve EV/EBITDA daha görünür ağırlık alırken terminal ve defter modelleri destekleyici roldedir.",
        "Genel Sanayi": "Standart sanayi ve karma operasyonel şirketler. Çarpan, defter, EV/EBITDA ve gelir kapitalizasyonu dengeli kullanılır.",
        "Gayrimenkul": "Gayrimenkul şirketleri için defter değeri, özkaynak ve terminal gelir modelleri daha baskındır.",
        "Holding": "Holding ve karma yapıdaki şirketlerde net aktif değer, özkaynak ve terminal gelir yaklaşımı daha baskındır.",
    },
    "weights": {
        "Finansal": {"D1": 0.10, "D4": 0.20, "D5": 0.10, "D10": 0.15, "D11": 0.10, "D12": 0.35},
        "Büyüme/Teknoloji": {"D1": 0.25, "D6": 0.40, "D7": 0.20, "D11": 0.15},
        "Gayrimenkul": {"D4": 0.25, "D5": 0.25, "D10": 0.10, "D11": 0.20, "D12": 0.20},
        "Holding": {"D4": 0.20, "D5": 0.20, "D10": 0.10, "D11": 0.25, "D12": 0.25},
        "Enerji Utility/Altyapı": {"D1": 0.05, "D2": 0.03, "D3": 0.03, "D4": 0.10, "D5": 0.04, "D6": 0.05, "D7": 0.22, "D8": 0.03, "D9": 0.15, "D10": 0.10, "D11": 0.15, "D12": 0.05},
        "Enerji Ekipman/Taahhüt": {"D1": 0.12, "D2": 0.06, "D3": 0.05, "D4": 0.08, "D5": 0.04, "D6": 0.16, "D7": 0.18, "D8": 0.03, "D9": 0.08, "D10": 0.06, "D11": 0.10, "D12": 0.04},
        "Genel Sanayi": {"D1": 0.10, "D2": 0.05, "D3": 0.05, "D4": 0.10, "D6": 0.10, "D7": 0.20, "D9": 0.15, "D10": 0.10, "D11": 0.15},
    },
}


def _deep_update(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in incoming.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_update(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_valuation_profile_config(path: Path = VALUATION_PROFILE_CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return deepcopy(DEFAULT_VALUATION_PROFILE_CONFIG)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_VALUATION_PROFILE_CONFIG)
    if not isinstance(raw, dict):
        return deepcopy(DEFAULT_VALUATION_PROFILE_CONFIG)
    return _deep_update(DEFAULT_VALUATION_PROFILE_CONFIG, raw)


def _safe_weight(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    if number < 0:
        return 0.0
    return number


def _normalize_weights(model_map: dict[str, float]) -> dict[str, float]:
    positive_items = {model_name: weight for model_name, weight in model_map.items() if weight > 0}
    total = sum(positive_items.values())
    if total <= 0:
        return {}
    return {
        model_name: weight / total
        for model_name, weight in positive_items.items()
    }


def build_valuation_profile_maps(config: dict[str, Any]) -> tuple[dict[str, dict[str, float]], dict[str, str]]:
    raw_weights = config.get("weights", {})
    raw_notes = config.get("profile_notes", {})

    weights: dict[str, dict[str, float]] = {}
    if isinstance(raw_weights, dict):
        for profile_name, model_map in raw_weights.items():
            if not isinstance(profile_name, str) or not isinstance(model_map, dict):
                continue
            normalized_model_map = {
                str(model_name).strip(): _safe_weight(weight)
                for model_name, weight in model_map.items()
                if isinstance(model_name, str) and str(model_name).strip()
            }
            weights[profile_name.strip()] = _normalize_weights(normalized_model_map)

    notes: dict[str, str] = {}
    if isinstance(raw_notes, dict):
        for profile_name, note in raw_notes.items():
            if isinstance(profile_name, str) and isinstance(note, str) and profile_name.strip():
                notes[profile_name.strip()] = note.strip()

    return weights, notes
