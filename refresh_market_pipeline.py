from __future__ import annotations

from sector import TR_PROFILE, US_PROFILE, build_sector_maps, calculate_sector_multiples
from sector_override_builder import build_sector_overrides, save_sector_overrides
from update_macro_config import main as update_macro_main


def main() -> None:
    update_macro_main()

    tr_map, us_map = build_sector_maps(auto_classify=True)
    calculate_sector_multiples(tr_map, "sector_multiples_tr.csv", TR_PROFILE)
    calculate_sector_multiples(us_map, "sector_multiples_us.csv", US_PROFILE)

    overrides = build_sector_overrides(auto_classify=False)
    save_sector_overrides(overrides)
    print(f"Kaydedildi -> sector_overrides.json ({len(overrides)} ticker)")


if __name__ == "__main__":
    main()
