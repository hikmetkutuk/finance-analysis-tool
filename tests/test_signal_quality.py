from valuation import compute_signal_quality_score


def test_signal_quality_score_high_without_warnings() -> None:
    valuations = {
        "fv_dcf": 100.0,
        "fv_fk": 98.0,
        "fv_ev": 102.0,
        "fv_ddm": 95.0,
        "fv_efk": 101.0,
        "fv_ndk": 99.0,
        "fv_graham": 97.0,
        "fv_financial": None,
    }
    score, label = compute_signal_quality_score(valuations, [], is_financial=False)
    assert score >= 80
    assert label == "High"


def test_signal_quality_score_low_with_warnings_and_sparse_values() -> None:
    valuations = {
        "fv_dcf": None,
        "fv_fk": None,
        "fv_ev": None,
        "fv_ddm": 80.0,
        "fv_efk": None,
        "fv_ndk": None,
        "fv_graham": None,
        "fv_financial": None,
    }
    score, label = compute_signal_quality_score(
        valuations,
        warnings=["info_unavailable", "price_missing", "eps_missing", "shares_missing"],
        is_financial=False,
    )
    assert score < 60
    assert label == "Low"
