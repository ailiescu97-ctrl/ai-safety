from decimal import Decimal

import pytest
from money import round_money

CASES = [
    # (value, places, expected)
    ("2.665", 2, "2.66"),
    ("-2.675", 2, "-2.68"),
    ("-0.135", 2, "-0.14"),
    ("-1.5", 0, "-2"),
    ("2.5", 0, "2"),
    ("3.5", 0, "4"),
    ("0.0125", 3, "0.012"),
    ("1.2355", 3, "1.236"),
    ("0.00025", 4, "0.0002"),
    ("12345678901234.565", 2, "12345678901234.56"),
    ("99999999999999.995", 2, "100000000000000.00"),
    ("-1000000000000.005", 2, "-1000000000000.00"),
]


@pytest.mark.parametrize(("value", "places", "expected"), CASES)
def test_half_even_cases(value, places, expected):
    assert round_money(Decimal(value), places) == Decimal(expected)
