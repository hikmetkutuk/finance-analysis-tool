from __future__ import annotations

from datetime import date

from data.live_params import fetch_bist_rf
from data.macro_config import load_macro_config, save_macro_config

MANUAL_US_RISK_FREE = 0.0434
MANUAL_US_BOND_2Y = 0.0384
MANUAL_US_COST_OF_DEBT = 0.0584

MANUAL_TR_RISK_FREE = 0.3996
MANUAL_TR_BOND_2Y = 0.3996
MANUAL_TR_COST_OF_DEBT = 0.4496


def apply_manual_us_block(config: dict) -> None:
    us = config["us"]
    us["risk_free_rate"] = MANUAL_US_RISK_FREE
    us["bond_yield_2"] = MANUAL_US_BOND_2Y
    us["cost_of_debt"] = MANUAL_US_COST_OF_DEBT
    us["source"] = "manual_override_us_treasury_2026_04_23"


def apply_live_tr_block(config: dict) -> bool:
    tr = config["tr"]
    previous_rate = float(tr.get("risk_free_rate", MANUAL_TR_RISK_FREE))
    rate = fetch_bist_rf(fallback=previous_rate)
    changed = abs(rate - previous_rate) > 1e-9
    tr["risk_free_rate"] = rate
    tr["bond_yield_2"] = rate
    tr["cost_of_debt"] = min(rate + 0.05, 1.0)
    if changed:
        tr["source"] = "fred_INTDSRTRM193N_latest_policy_rate_proxy"
    return changed


def update_tr_macro_config() -> dict:
    config = load_macro_config()
    if apply_live_tr_block(config):
        config["as_of"] = date.today().isoformat()
    save_macro_config(config)
    return config


def main() -> None:
    config = load_macro_config()
    apply_manual_us_block(config)
    apply_live_tr_block(config)
    config["as_of"] = date.today().isoformat()
    save_macro_config(config)
    print("Kaydedildi -> macro_config.json")
    print(f"US rf: {config['us']['risk_free_rate']}, TR rf: {config['tr']['risk_free_rate']}")


if __name__ == "__main__":
    main()
