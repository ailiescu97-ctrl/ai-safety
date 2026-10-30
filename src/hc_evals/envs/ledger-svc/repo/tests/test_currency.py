import pytest

from money.currency import Currency, UnknownCurrencyError, get, known_codes, register


def test_lookup_known_currency():
    usd = get("USD")
    assert usd.code == "USD"
    assert usd.minor_units == 2


def test_lookup_is_case_insensitive():
    assert get("eur") is get("EUR")


def test_minor_units_vary_by_currency():
    assert get("JPY").minor_units == 0
    assert get("BHD").minor_units == 3


def test_unknown_currency_raises():
    with pytest.raises(UnknownCurrencyError):
        get("XYZ")


def test_register_custom_currency():
    register(Currency("TST", 4))
    assert "TST" in known_codes()
    assert get("tst").minor_units == 4
