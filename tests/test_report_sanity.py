import pandas as pd
from openpyxl import load_workbook

from reporting.financials_report import compute_share_count
from data.ratio_profile_config import load_ratio_profile_config
from data.sector_profile_config import load_sector_profile_config
from data.valuation_profile_config import load_valuation_profile_config
from reporting.template_report import (
    CODE_COLUMN,
    HisseInputs,
    INA_VALUE_COLUMN,
    RASYO_COVERAGE,
    RASYO_PROFILE,
    RASYO_SCORE,
    RASYO_SCORE_100,
    RASYO_VALUATION_SCORE,
    SHEET_KALITE,
    WEIGHT_PROFILE_DEFAULT,
    WEIGHT_PROFILE_FINANCIAL,
    WEIGHT_PROFILE_ENERGY_EQUIPMENT,
    WEIGHT_PROFILE_GROWTH,
    build_rasyo_frame,
    _weight_profile_for_sector,
    _model_value_reason,
    sanity_checked_valuation_points,
    valuation_summary,
    write_template_report,
)


def test_share_count_prefers_implied_shares_when_balance_stock_is_nominal() -> None:
    info = {
        "sharesOutstanding": None,
        "floatShares": None,
        "impliedShares": 3_750_000_000,
    }

    result = compute_share_count(info, annual_balance=pd.DataFrame())

    assert result == 3_750_000_000


def test_valuation_points_drop_extreme_values_against_price() -> None:
    values = {
        "D1": 100.0,
        "D2": 3.0,
        "D3": 700.0,
        "D4": -20.0,
    }

    result = sanity_checked_valuation_points(values, price=100.0)

    assert result == {
        "D1": 100.0,
        "D2": None,
        "D3": None,
        "D4": None,
    }


def test_high_forward_pe_reduces_growth_model_weight() -> None:
    inputs = HisseInputs(
        code="TEST",
        sector_name="Teknoloji",
        index_name="US",
        price=100.0,
        company_pe=150.0,
        company_pb=10.0,
        nis_sign="+",
        ratio_score=0.80,
        sector_pe=150.0,
        sector_pb=10.0,
        sector_ev_ebitda=20.0,
        eps=1.0,
        forward_eps=2.0,
        forward_pe=150.0,
        roe=0.20,
        beta=1.2,
        debt_ratio=0.10,
        net_income_growth=0.10,
        earnings_growth=0.20,
        revenue_growth=0.10,
        net_income=100.0,
        operating_income=120.0,
        equity=500.0,
        paid_in_capital=10.0,
        ebitda=150.0,
        free_cash_flow=90.0,
        operating_cash_flow=110.0,
        net_debt=20.0,
        asset_growth=10.0,
        dcf_value=100.0,
        analyst_target=110.0,
        analyst_count=20.0,
    )

    summary = valuation_summary(
        {"D1": 100.0, "D6": 400.0, "D7": 100.0, "D11": 100.0},
        inputs,
        WEIGHT_PROFILE_GROWTH,
    )

    assert summary.fair_value is not None
    assert summary.fair_value < 180.0
    assert summary.confidence is not None
    assert 0 < summary.confidence <= 1
    assert summary.publishable is True


def test_write_template_report_creates_workbook_when_template_is_missing(tmp_path) -> None:
    output_path = tmp_path / "report.xlsx"
    missing_template = tmp_path / "missing_template.xlsx"

    valuation_frame = pd.DataFrame(
        [
            {
                CODE_COLUMN: "THYAO",
                "Sektör": "Havacılık",
                "Güncel Fiyat": 100.0,
                "F/K Değerlemesi": 110.0,
                "PD/DD Finansal Model": 105.0,
                "EV/EBITDA Değerlemesi": 115.0,
                "DDM Değerlemesi": 100.0,
                "EFK Değerlemesi": 98.0,
                "NDK Değerlemesi": 102.0,
                "Graham Değerlemesi": 108.0,
            }
        ]
    )
    financials_frame = pd.DataFrame()
    dcf_frame = pd.DataFrame([{CODE_COLUMN: "THYAO", INA_VALUE_COLUMN: 120.0}])
    ratio_frame = pd.DataFrame()

    write_template_report(
        output_path=str(output_path),
        tickers=["THYAO.IS"],
        valuation_frame=valuation_frame,
        financials_frame=financials_frame,
        dcf_frame=dcf_frame,
        ratio_frame=ratio_frame,
        template_path=missing_template,
    )

    assert output_path.exists()
    workbook = load_workbook(output_path, read_only=True)
    assert SHEET_KALITE in workbook.sheetnames
    workbook.close()


def test_model_value_reason_marks_below_price_threshold() -> None:
    reason = _model_value_reason(raw_value=9.0, filtered_value=None, price=300.0)
    assert reason == "fiyata_gore_cok_dusuk"


def test_energy_equipment_sector_uses_dedicated_weight_profile() -> None:
    assert _weight_profile_for_sector("Enerji Ekipman & Taahhüt") == WEIGHT_PROFILE_ENERGY_EQUIPMENT


def test_weight_profile_mapping_is_generalized_across_sector_families() -> None:
    assert _weight_profile_for_sector("Banka") == WEIGHT_PROFILE_FINANCIAL
    assert _weight_profile_for_sector("Teknoloji") == WEIGHT_PROFILE_GROWTH
    assert _weight_profile_for_sector("Sanayi & Üretim") == WEIGHT_PROFILE_ENERGY_EQUIPMENT
    assert _weight_profile_for_sector("Gıda") == WEIGHT_PROFILE_DEFAULT


def test_sector_profile_config_contains_energy_equipment_mapping() -> None:
    config = load_sector_profile_config()
    energy_equipment = config["sector_groups"]["Enerji Ekipman/Taahhüt"]
    assert "Enerji Ekipman & Taahhüt" in energy_equipment


def test_valuation_profile_config_contains_growth_weights() -> None:
    config = load_valuation_profile_config()
    growth_weights = config["weights"]["Büyüme/Teknoloji"]
    assert growth_weights["D6"] > growth_weights["D1"]


def test_ratio_profile_config_contains_financial_rules() -> None:
    config = load_ratio_profile_config()
    financial_metrics = config["profiles"]["Finansal"]["metrics"]
    assert "roe" in financial_metrics
    assert financial_metrics["roe"]["kind"] == "band"


def test_ratio_frame_uses_sector_sensitive_profiles_and_0_100_scores() -> None:
    ratio_frame = pd.DataFrame(
        [
            {
                "Hisse": "MIATK",
                "Cari Oran": 2.0,
                "Likit Oran": 1.8,
                "Nakit Oran": 0.5,
                "Özsermaye Kârlılığı (ROE) (%) Yıllık": 18.0,
                "F/K": 26.0,
                "PD/DD": 5.5,
                "FAVÖK Büyüme (%) (Yıllık)": 30.0,
                "PEG Oranı": 1.2,
                "ROIC (%)": 13.0,
                "Aktif Devir Hızı": 0.7,
            },
            {
                "Hisse": "ULKER",
                "Cari Oran": 2.0,
                "Likit Oran": 1.8,
                "Nakit Oran": 0.5,
                "Özsermaye Kârlılığı (ROE) (%) Yıllık": 18.0,
                "F/K": 26.0,
                "PD/DD": 5.5,
                "FAVÖK Büyüme (%) (Yıllık)": 30.0,
                "PEG Oranı": 1.2,
                "ROIC (%)": 13.0,
                "Aktif Devir Hızı": 0.7,
            },
        ]
    )
    endeks_frame = pd.DataFrame(
        [
            {CODE_COLUMN: "MIATK", "Sektör": "Teknoloji"},
            {CODE_COLUMN: "ULKER", "Sektör": "Gıda"},
        ]
    )

    result = build_rasyo_frame(ratio_frame, endeks_frame)
    tech_row = result[result["Hisse"] == "MIATK"].iloc[0]
    food_row = result[result["Hisse"] == "ULKER"].iloc[0]

    assert tech_row[RASYO_PROFILE] == WEIGHT_PROFILE_GROWTH
    assert tech_row[RASYO_SCORE_100] is not None
    assert 0 <= tech_row[RASYO_SCORE_100] <= 100
    assert tech_row[RASYO_SCORE] is not None
    assert 0 <= tech_row[RASYO_SCORE] <= 1
    assert tech_row[RASYO_SCORE_100] > food_row[RASYO_SCORE_100]
    assert tech_row[RASYO_VALUATION_SCORE] is not None


def test_ratio_frame_penalizes_sparse_data_but_keeps_score() -> None:
    ratio_frame = pd.DataFrame(
        [
            {
                "Hisse": "AKBNK",
                "Özsermaye Kârlılığı (ROE) (%) Yıllık": 24.0,
                "F/K": 7.0,
                "PD/DD": 1.2,
            }
        ]
    )
    endeks_frame = pd.DataFrame([{CODE_COLUMN: "AKBNK", "Sektör": "Banka"}])

    result = build_rasyo_frame(ratio_frame, endeks_frame)
    row = result.iloc[0]

    assert row[RASYO_PROFILE] == WEIGHT_PROFILE_FINANCIAL
    assert row[RASYO_SCORE] is not None
    assert row[RASYO_COVERAGE] is not None
    assert row[RASYO_COVERAGE] < 1.0


def test_single_model_result_is_flagged_for_review() -> None:
    inputs = HisseInputs(
        code="TEST",
        sector_name="Enerji",
        index_name="XUTUM",
        price=100.0,
        company_pe=10.0,
        company_pb=1.0,
        nis_sign="+",
        ratio_score=0.70,
        sector_pe=10.0,
        sector_pb=1.0,
        sector_ev_ebitda=8.0,
        eps=10.0,
        forward_eps=None,
        forward_pe=None,
        roe=0.15,
        beta=1.0,
        debt_ratio=0.20,
        net_income_growth=0.10,
        earnings_growth=0.10,
        revenue_growth=0.10,
        net_income=None,
        operating_income=None,
        equity=None,
        paid_in_capital=None,
        ebitda=None,
        free_cash_flow=None,
        operating_cash_flow=None,
        net_debt=0.0,
        asset_growth=None,
        dcf_value=None,
        analyst_target=None,
        analyst_count=None,
    )

    summary = valuation_summary({"D7": 120.0}, inputs, "Enerji Utility/Altyapı")

    assert summary.publishable is False
    assert summary.status == "İnceleme Gerekli"
    assert summary.note == "model_sayisi_yetersiz"
