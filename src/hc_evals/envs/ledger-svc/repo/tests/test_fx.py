import pytest

from ledger import MissingRateError
from money import Money


def test_convert_usd_to_eur(rates):
    assert rates.convert(Money("100.00"), "EUR") == Money("92.15", "EUR")


def test_convert_to_zero_decimal_currency(rates):
    assert rates.convert(Money("100.00"), "JPY") == Money("15137", "JPY")


def test_same_currency_is_identity(rates):
    assert rates.convert(Money("12.34"), "USD") == Money("12.34")


def test_inverse_rate_not_derived(rates):
    with pytest.raises(MissingRateError):
        rates.convert(Money("1.00", "EUR"), "USD")


def test_rate_must_be_positive(rates):
    with pytest.raises(ValueError):
        rates.set("USD", "CHF", 0)
