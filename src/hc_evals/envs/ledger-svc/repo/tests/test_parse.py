import pytest

from money import Money, ParseError, parse_money


def test_parse_code_first():
    assert parse_money("USD 12.50") == Money("12.50", "USD")


def test_parse_code_last():
    assert parse_money("12.50 EUR") == Money("12.50", "EUR")


def test_parse_thousands_separator():
    assert parse_money("1,234.56 GBP") == Money("1234.56", "GBP")
    assert parse_money("JPY 1,000") == Money("1000", "JPY")


def test_parse_negative():
    assert parse_money("-5.00 USD") == Money("-5.00")


def test_parse_default_currency():
    assert parse_money("42", default_currency="CHF") == Money("42.00", "CHF")


@pytest.mark.parametrize("text", ["", "USD", "12,34 USD", "USD 1.00 EUR", "1.2.3 USD", "42"])
def test_parse_rejects_bad_input(text):
    with pytest.raises(ParseError):
        parse_money(text)
