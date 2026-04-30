import pandas as pd
from openpyxl import load_workbook

from reporting.financials_report import compute_share_count
from reporting.template_report import (
    CODE_COLUMN,
    HisseInputs,
    INA_VALUE_COLUMN,
    SHEET_KALITE,
    WEIGHT_PROFILE_GROWTH,
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
