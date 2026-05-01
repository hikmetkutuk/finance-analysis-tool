from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


SECTOR_PROFILE_CONFIG_PATH = Path(__file__).resolve().parent.parent / "sector_profiles.json"
PROFILE_FINANCIAL = "Finansal"
PROFILE_GROWTH = "Büyüme/Teknoloji"
PROFILE_REAL_ESTATE = "Gayrimenkul"
PROFILE_HOLDING = "Holding"
PROFILE_ENERGY_UTILITY = "Enerji Utility/Altyapı"
PROFILE_ENERGY_EQUIPMENT = "Enerji Ekipman/Taahhüt"

DEFAULT_SECTOR_PROFILE_CONFIG: dict[str, Any] = {
    "sector_groups": {
        PROFILE_FINANCIAL: ["Banka", "Sigorta", "Finans", "Finansal Hizmetler"],
        PROFILE_GROWTH: ["Teknoloji", "Yarı İletken", "E-Ticaret", "İletişim & Medya", "Otomotiv"],
        PROFILE_REAL_ESTATE: ["Gayrimenkul"],
        PROFILE_HOLDING: ["Holding & Karma"],
        PROFILE_ENERGY_UTILITY: ["Enerji", "Enerji Altyapı", "Petrol", "Telekomünikasyon", "Havacılık"],
        PROFILE_ENERGY_EQUIPMENT: ["Enerji Ekipman & Taahhüt", "Sanayi & Savunma", "Sanayi & Üretim", "Savunma", "Çimento"],
    },
    "keyword_profiles": [
        ["finans", PROFILE_FINANCIAL],
        ["sigorta", PROFILE_FINANCIAL],
        ["gayrimenkul", PROFILE_REAL_ESTATE],
        ["holding", PROFILE_HOLDING],
        ["teknoloji", PROFILE_GROWTH],
        ["yarı iletken", PROFILE_GROWTH],
        ["iletisim", PROFILE_GROWTH],
        ["iletişim", PROFILE_GROWTH],
        ["e-ticaret", PROFILE_GROWTH],
        ["enerji ekipman", PROFILE_ENERGY_EQUIPMENT],
        ["taahhüt", PROFILE_ENERGY_EQUIPMENT],
        ["taahhut", PROFILE_ENERGY_EQUIPMENT],
        ["savunma", PROFILE_ENERGY_EQUIPMENT],
        ["sanayi", PROFILE_ENERGY_EQUIPMENT],
        ["çimento", PROFILE_ENERGY_EQUIPMENT],
        ["cimento", PROFILE_ENERGY_EQUIPMENT],
        ["petrol", PROFILE_ENERGY_UTILITY],
        ["telekom", PROFILE_ENERGY_UTILITY],
        ["havac", PROFILE_ENERGY_UTILITY],
        ["enerji", PROFILE_ENERGY_UTILITY],
    ],
}


def _deep_update(base: dict[str, Any], incoming: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in incoming.items():
        if key in merged and isinstance(merged[key], dict) and isinstance(value, dict):
            merged[key] = _deep_update(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_sector_profile_config(path: Path = SECTOR_PROFILE_CONFIG_PATH) -> dict[str, Any]:
    if not path.exists():
        return deepcopy(DEFAULT_SECTOR_PROFILE_CONFIG)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return deepcopy(DEFAULT_SECTOR_PROFILE_CONFIG)
    if not isinstance(raw, dict):
        return deepcopy(DEFAULT_SECTOR_PROFILE_CONFIG)
    return _deep_update(DEFAULT_SECTOR_PROFILE_CONFIG, raw)


def _build_sector_lookup(raw_groups: Any) -> dict[str, str]:
    if not isinstance(raw_groups, dict):
        return {}
    sector_lookup: dict[str, str] = {}
    for profile_name, sector_names in raw_groups.items():
        if not isinstance(profile_name, str) or not isinstance(sector_names, list):
            continue
        normalized_profile = profile_name.strip()
        if not normalized_profile:
            continue
        for sector_name in sector_names:
            if isinstance(sector_name, str) and sector_name.strip():
                sector_lookup[sector_name.strip()] = normalized_profile
    return sector_lookup


def _parse_keyword_profile(item: Any) -> tuple[str, str] | None:
    if not isinstance(item, list) or len(item) != 2:
        return None
    keyword, profile_name = item
    if not isinstance(keyword, str) or not isinstance(profile_name, str):
        return None
    normalized_keyword = keyword.strip().casefold()
    normalized_profile = profile_name.strip()
    if not normalized_keyword or not normalized_profile:
        return None
    return normalized_keyword, normalized_profile


def _build_keyword_pairs(raw_keywords: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(raw_keywords, list):
        return ()
    keyword_pairs: list[tuple[str, str]] = []
    for item in raw_keywords:
        parsed = _parse_keyword_profile(item)
        if parsed is not None:
            keyword_pairs.append(parsed)
    return tuple(keyword_pairs)


def build_sector_profile_maps(config: dict[str, Any]) -> tuple[dict[str, str], tuple[tuple[str, str], ...]]:
    raw_groups = config.get("sector_groups", {})
    raw_keywords = config.get("keyword_profiles", [])
    return _build_sector_lookup(raw_groups), _build_keyword_pairs(raw_keywords)
