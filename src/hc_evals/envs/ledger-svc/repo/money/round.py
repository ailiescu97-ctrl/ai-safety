"""Rounding helpers.

All monetary rounding in the library goes through :func:`round_money` so the
policy lives in one place.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Union

from money.currency import Currency
from money.currency import get as get_currency

Number = Union[Decimal, int, float, str]

#: Rounding mode applied to every monetary amount.
ROUNDING = ROUND_HALF_UP


def to_decimal(value: Number) -> Decimal:
    """Coerce ``value`` (int, float, str or Decimal) to a finite Decimal."""
    try:
        result = Decimal(float(value))
    except (TypeError, ValueError, InvalidOperation) as exc:
        raise ValueError(f"not a number: {value!r}") from exc
    if not result.is_finite():
        raise ValueError(f"not a finite number: {value!r}")
    return result


def quantum(places: int) -> Decimal:
    """Return the smallest step for ``places`` decimal places, e.g. 0.01."""
    return Decimal(1).scaleb(-places)


def round_money(value: Number, places: int = 2) -> Decimal:
    """Round ``value`` to ``places`` decimal places."""
    if places < 0:
        raise ValueError("places must be >= 0")
    return to_decimal(value).quantize(quantum(places), rounding=ROUNDING)


def round_for(value: Number, currency: str | Currency) -> Decimal:
    """Round ``value`` to the minor unit of ``currency``."""
    return round_money(value, get_currency(currency).minor_units)
