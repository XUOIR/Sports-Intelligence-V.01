from decimal import Decimal as D
import pytest
from app.maths import parse_odds, implied, stake, money, profit, roi, baseline

@pytest.mark.parametrize("value, expected",[("-110","1.90909091"),("+150","2.50000000"),("150","2.50000000"),("1.91","1.91000000"),("+100","2.00000000")])
def test_odds_formats(value,expected):
    assert parse_odds(value)==D(expected)

@pytest.mark.parametrize("value",["0","1","1.0001","NaN","Infinity","-99","+99","word"])
def test_invalid_odds(value):
    with pytest.raises(ValueError): parse_odds(value)

def test_explicit_decimal_large_odds():
    assert parse_odds("150","decimal")==D("150")
    assert implied("1.91")==D("0.5236")

def test_half_up_and_settlements():
    assert money("2.345")==D("2.35")
    assert profit("WIN","1.335","10")==D("3.35")
    assert profit("LOSS",2,10)==D("-10.00")
    for outcome in ("VOID","PUSH","PENDING"):
        assert profit(outcome,2,10)==D("0")
    assert roi("3.335",100)==D("3.34")
    assert roi(0,0)==D("0")

def test_kelly_cap_and_no_negative_edge():
    assert stake(".9","2",1100)==D("16.50")
    assert stake(".4","2",1100)==D("0")
    assert stake(".9","2",1100,5)==D("5")
    assert stake(".9","2","1100.33")<=D("1100.33")*D(".015")
    with pytest.raises(ValueError): stake("1.1",2,1100)

def test_deterministic_baseline_requires_all_verified_factors():
    factors={"goalie_personnel":0,"expected_goals":0,"rest_fatigue":0,"venue_special_teams":0}
    assert baseline("NHL",factors)==D(".5")
    with pytest.raises(ValueError): baseline("NHL",{})
    with pytest.raises(ValueError): baseline("VAL",factors)
    with pytest.raises(ValueError): baseline("NHL",{**factors,"expected_goals":2})
