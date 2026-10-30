"""Currency conversion against a fixed table of rates."""

from __future__ import annotations

from decimal import Decimal

from money import Money
from money.round import Number


class MissingRateError(LookupError):
    """Raised when no rate is known for a currency pair."""


class RateTable:
    """Direct rates only; inverse rates are not derived automatically."""

    def __init__(self) -> None:
        self._rates: dict[tuple[str, str], Decimal] = {}

    def set(self, base: str, quote: str, rate: Number) -> None:
        rate = Decimal(str(rate))
        if rate <= 0:
            raise ValueError("rate must be positive")
        self._rates[(base.upper(), quote.upper())] = rate

    def rate(self, base: str, quote: str) -> Decimal:
        base, quote = base.upper(), quote.upper()
        if base == quote:
            return Decimal(1)
        try:
            return self._rates[(base, quote)]
        except KeyError:
            raise MissingRateError(f"no rate for {base}/{quote}") from None

    def convert(self, amount: Money, to: str) -> Money:
        rate = self.rate(amount.currency.code, to)
        return Money(amount.amount * rate, to)
