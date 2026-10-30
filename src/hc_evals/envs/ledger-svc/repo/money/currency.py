"""ISO 4217 currency metadata used across the library."""

from __future__ import annotations

from dataclasses import dataclass


class UnknownCurrencyError(KeyError):
    """Raised when a currency code is not in the registry."""


@dataclass(frozen=True)
class Currency:
    code: str
    minor_units: int
    symbol: str = ""

    def __str__(self) -> str:
        return self.code


_REGISTRY: dict[str, Currency] = {}


def register(currency: Currency) -> Currency:
    """Add ``currency`` to the registry, replacing any existing entry."""
    _REGISTRY[currency.code.upper()] = currency
    return currency


def get(code: str | Currency) -> Currency:
    """Look up a currency by its three-letter code (case-insensitive)."""
    if isinstance(code, Currency):
        return code
    try:
        return _REGISTRY[code.upper()]
    except KeyError:
        raise UnknownCurrencyError(code) from None


def known_codes() -> list[str]:
    return sorted(_REGISTRY)


for _c in (
    Currency("USD", 2, "$"),
    Currency("EUR", 2, "€"),
    Currency("GBP", 2, "£"),
    Currency("CHF", 2),
    Currency("JPY", 0, "¥"),
    Currency("BHD", 3),
    Currency("KWD", 3),
):
    register(_c)
