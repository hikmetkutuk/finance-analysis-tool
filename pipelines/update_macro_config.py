from __future__ import annotations

from datetime import date

from data.macro_config import load_macro_config, save_macro_config

MANUAL_US_RISK_FREE = 0.0434
MANUAL_US_BOND_2Y = 0.0384
MANUAL_US_COST_OF_DEBT = 0.0584

MANUAL_TR_RISK_FREE = 0.4218
MANUAL_TR_BOND_2Y = 0.4218
MANUAL_TR_COST_OF_DEBT = 0.4618


def apply_manual_us_block(config: dict) -> None:
    us = config["us"]
    us["risk_free_rate"] = MANUAL_US_RISK_FREE
    us["bond_yield_2"] = MANUAL_US_BOND_2Y
    us["cost_of_debt"] = MANUAL_US_COST_OF_DEBT
    us["source"] = "manual_override_treasury_gov_2026_04_06"


def apply_manual_tr_block(config: dict) -> None:
    tr = config["tr"]
    tr["risk_free_rate"] = MANUAL_TR_RISK_FREE
    tr["bond_yield_2"] = MANUAL_TR_BOND_2Y
    tr["cost_of_debt"] = MANUAL_TR_COST_OF_DEBT
    tr["source"] = "manual_override_tr_2y_bloomberght_2026_04_07"


def main() -> None:
    config = load_macro_config()
    apply_manual_us_block(config)
    apply_manual_tr_block(config)
    config["as_of"] = date.today().isoformat()
    save_macro_config(config)
    print("Kaydedildi -> macro_config.json")
    print(f"US rf: {config['us']['risk_free_rate']}, TR rf: {config['tr']['risk_free_rate']}")


if __name__ == "__main__":
    main()
