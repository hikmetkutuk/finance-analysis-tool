import math

from valuation import (
    calculate_financial_fair_value,
    calculate_fk_fair_value,
    clamp_growth,
    safe_div,
)


def test_safe_div_handles_invalid() -> None:
    result = safe_div(10, 2)
    assert result is not None
    assert math.isclose(result, 5.0, rel_tol=1e-9)
    assert safe_div(10, 0) is None
    assert safe_div(None, 2) is None


def test_clamp_growth_caps_over_wacc() -> None:
    clamped = clamp_growth(0.80, 0.30)
    assert clamped <= 0.50
    assert math.isclose(clamped, 0.29, rel_tol=1e-9)


def test_calculate_fk_fair_value() -> None:
    result = calculate_fk_fair_value(2.0, 10.0)
    assert result is not None
    assert math.isclose(result, 20.0, rel_tol=1e-9)
    assert calculate_fk_fair_value(-1.0, 10.0) is None


def test_financial_fair_value_uses_pb_and_roe() -> None:
    info = {"bookValue": 10.0, "returnOnEquity": 0.20}
    params = {"pb": 1.5}
    value = calculate_financial_fair_value(info, params, cost_of_equity=0.10)
    assert value is not None
    assert value > 10.0
