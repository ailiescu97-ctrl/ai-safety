from decimal import Decimal

import pytest

from money import CurrencyMismatchError, Money, round_for, round_money


def test_round_two_places():
    assert round_money("1.234") == Decimal("1.23")
    assert round_money("1.236") == Decimal("1.24")


def test_round_zero_places():
    assert round_money("12.7", 0) == Decimal("13")


def test_round_three_places():
    assert round_money("0.1234", 3) == Decimal("0.123")


def test_round_for_currency():
    assert round_for("1234.4", "JPY") == Decimal("1234")
    assert round_for("7.0004", "BHD") == Decimal("7.000")


def test_round_rejects_negative_places():
    with pytest.raises(ValueError):
        round_money("1.00", -1)


def test_round_rejects_garbage():
    with pytest.raises(ValueError):
        round_money("twelve")


def test_money_holds_minor_units():
    assert Money("10").amount == Decimal("10.00")
    assert str(Money("10").amount) == "10.00"


def test_money_addition_and_subtraction():
    assert Money("10.10") + Money("0.20") == Money("10.30")
    assert Money("10.10") - Money("0.20") == Money("9.90")
    assert sum([Money("1.00"), Money("2.50")]) == Money("3.50")


def test_money_currency_mismatch():
    with pytest.raises(CurrencyMismatchError):
        Money("1.00", "USD") + Money("1.00", "EUR")


def test_money_multiply():
    assert Money("10.00") * 3 == Money("30.00")
    assert Money("19.99") * Decimal("2") == Money("39.98")


def test_money_ordering():
    assert Money("1.00") < Money("1.01")
    assert max(Money("3.00"), Money("2.00")) == Money("3.00")


def test_allocate_even_split():
    parts = Money("90.00").allocate([1, 1, 1])
    assert parts == [Money("30.00")] * 3


def test_allocate_spreads_remainder():
    parts = Money("100.00").allocate([1, 1, 1])
    assert parts == [Money("33.34"), Money("33.33"), Money("33.33")]
    assert sum(parts) == Money("100.00")


def test_money_str():
    assert str(Money("1234.5")) == "USD 1,234.50"
    assert str(Money("15137", "JPY")) == "JPY 15,137"


def test_rounding_half_even():
    # Half-cent amounts must use banker's rounding so invoice totals
    # reconcile with the payment processor's settlement files (#412).
    assert round_money(Decimal("0.125")) == Decimal("0.12")
    assert round_money(Decimal("0.135")) == Decimal("0.14")
    assert round_money(Decimal("2.675")) == Decimal("2.68")
    assert round_money(Decimal("-0.125")) == Decimal("-0.12")
    assert round_for(Decimal("10.5"), "JPY") == Decimal("10")
