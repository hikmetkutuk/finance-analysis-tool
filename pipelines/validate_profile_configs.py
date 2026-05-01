from __future__ import annotations

import sys
from pathlib import Path
from typing import List

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from data.sector_profile_config import load_sector_profile_config
from data.ratio_profile_config import build_ratio_profile_map, load_ratio_profile_config
from data.valuation_profile_config import build_valuation_profile_maps, load_valuation_profile_config


def _collect_missing_profile_issues(
    referenced_profiles: set[str],
    available_profiles: set[str],
    notes: dict[str, str],
) -> list[str]:
    issues: list[str] = []
    for profile_name in sorted(referenced_profiles - available_profiles):
        issues.append(f"Missing valuation weights for profile: {profile_name}")
    for profile_name in sorted(available_profiles - set(notes.keys())):
        issues.append(f"Missing profile note for profile: {profile_name}")
    if "Genel Sanayi" not in available_profiles:
        issues.append("Default valuation profile 'Genel Sanayi' is missing")
    return issues


def _collect_weight_issues(weights: dict[str, dict[str, float]]) -> list[str]:
    issues: list[str] = []
    for profile_name, model_weights in weights.items():
        total = sum(model_weights.values())
        if not 0.99 <= total <= 1.01:
            issues.append(f"Weight sum for profile {profile_name} is {total:.4f}, expected ~1.0")
        if not model_weights:
            issues.append(f"Profile {profile_name} has no active model weights")
    return issues


def _collect_ratio_profile_issues(
    available_profiles: set[str],
    ratio_profiles: dict[str, object],
) -> list[str]:
    issues: list[str] = []
    for profile_name in sorted(available_profiles - set(ratio_profiles.keys())):
        issues.append(f"Missing ratio profile for valuation profile: {profile_name}")
    return issues


def _collect_ratio_rule_issues(ratio_profiles: dict[str, object]) -> list[str]:
    issues: list[str] = []
    for profile_name, ratio_profile in ratio_profiles.items():
        if not isinstance(ratio_profile, dict):
            issues.append(f"Ratio profile {profile_name} is not a mapping")
            continue
        metrics = ratio_profile.get("metrics", {})
        if not isinstance(metrics, dict) or not metrics:
            issues.append(f"Ratio profile {profile_name} has no metric rules")
            continue
        for metric_name, rule in metrics.items():
            if not isinstance(rule, dict):
                issues.append(f"Ratio metric rule for {profile_name}:{metric_name} is invalid")
                continue
            if rule.get("kind") not in {"band", "min"}:
                issues.append(f"Ratio metric rule for {profile_name}:{metric_name} has unsupported kind")
    return issues


def _collect_market_overlay_issues(
    valuation_config: dict[str, object],
    ratio_config: dict[str, object],
    available_profiles: set[str],
) -> list[str]:
    issues: list[str] = []
    issues.extend(_collect_valuation_overlay_issues(valuation_config, available_profiles))
    issues.extend(_collect_ratio_overlay_issues(ratio_config, available_profiles))
    return issues


def _collect_valuation_overlay_issues(
    valuation_config: dict[str, object],
    available_profiles: set[str],
) -> list[str]:
    issues: list[str] = []
    raw_valuation_overrides = valuation_config.get("market_overrides", {})
    if not isinstance(raw_valuation_overrides, dict):
        return issues
    for market_key, market_override in raw_valuation_overrides.items():
        if not isinstance(market_override, dict):
            issues.append(f"Valuation market override {market_key} is not a mapping")
            continue
        weight_overrides = market_override.get("weights", {})
        if not isinstance(weight_overrides, dict):
            continue
        for profile_name in weight_overrides.keys():
            if profile_name not in available_profiles:
                issues.append(f"Unknown valuation override profile {profile_name} for market {market_key}")
    return issues


def _collect_ratio_overlay_issues(
    ratio_config: dict[str, object],
    available_profiles: set[str],
) -> list[str]:
    issues: list[str] = []
    raw_ratio_overrides = ratio_config.get("market_overrides", {})
    if not isinstance(raw_ratio_overrides, dict):
        return issues
    for market_key, market_override in raw_ratio_overrides.items():
        if not isinstance(market_override, dict):
            issues.append(f"Ratio market override {market_key} is not a mapping")
            continue
        profile_overrides = market_override.get("profiles", {})
        if not isinstance(profile_overrides, dict):
            continue
        for profile_name in profile_overrides.keys():
            if profile_name not in available_profiles:
                issues.append(f"Unknown ratio override profile {profile_name} for market {market_key}")
    return issues


def validate_profile_configs() -> List[str]:
    issues: List[str] = []
    sector_config = load_sector_profile_config()
    ratio_config = load_ratio_profile_config()
    valuation_config = load_valuation_profile_config()
    weights, notes = build_valuation_profile_maps(valuation_config)
    ratio_profiles = build_ratio_profile_map(ratio_config)
    sector_groups = sector_config.get("sector_groups", {})
    referenced_profiles = set(sector_groups.keys()) if isinstance(sector_groups, dict) else set()
    available_profiles = set(weights.keys())
    issues.extend(_collect_missing_profile_issues(referenced_profiles, available_profiles, notes))
    issues.extend(_collect_weight_issues(weights))
    issues.extend(_collect_ratio_profile_issues(available_profiles, ratio_profiles))
    issues.extend(_collect_ratio_rule_issues(ratio_profiles))
    issues.extend(_collect_market_overlay_issues(valuation_config, ratio_config, available_profiles))
    return issues


def main() -> int:
    issues = validate_profile_configs()
    if not issues:
        print("Profile configuration validation passed.")
        return 0
    print("Profile configuration validation failed:")
    for issue in issues:
        print(f"- {issue}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
