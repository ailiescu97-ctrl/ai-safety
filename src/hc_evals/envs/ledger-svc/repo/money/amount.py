"""The :class:`Money` value type."""

from __future__ import annotations

from decimal import Decimal
from functools import total_ordering
from typing import Iterable

from money.currency import Currency
from money.currency import get as get_currency
from money.round import Number, round_for, to_decimal


class CurrencyMismatchError(ValueError):
    """Raised when combining amounts in different currencies."""


@total_ordering
class Money:
    """An amount in a single currency, always held at the currency's minor unit."""

    __slots__ = ("amount", "currency")

    def __init__(self, amount: Number, currency: str | Currency = "USD") -> None:
        cur = get_currency(currency)
        object.__setattr__(self, "currency", cur)
        object.__setattr__(self, "amount", round_for(amount, cur))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Money is immutable")

    @classmethod
    def zero(cls, currency: str | Currency = "USD") -> Money:
        return cls(0, currency)

    def _check(self, other: object) -> Money:
        if not isinstance(other, Money):
            raise TypeError(f"expected Money, got {type(other).__name__}")
        if other.currency != self.currency:
            raise CurrencyMismatchError(f"{self.currency} != {other.currency}")
        return other

    def __add__(self, other: Money) -> Money:
        other = self._check(other)
        return Money(self.amount + other.amount, self.currency)

    def __radd__(self, other: object) -> Money:
        # lets sum() work with its default start value of 0
        if other == 0:
            return self
        return self.__add__(other)  # type: ignore[arg-type]

    def __sub__(self, other: Money) -> Money:
        other = self._check(other)
        return Money(self.amount - other.amount, self.currency)

    def __neg__(self) -> Money:
        return Money(-self.amount, self.currency)

    def __mul__(self, factor: Number) -> Money:
        if isinstance(factor, Money):
            raise TypeError("cannot multiply Money by Money")
        return Money(self.amount * to_decimal(factor), self.currency)

    __rmul__ = __mul__

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Money):
            return NotImplemented
        return self.currency == other.currency and self.amount == other.amount

    def __lt__(self, other: Money) -> bool:
        other = self._check(other)
        return self.amount < other.amount

    def __hash__(self) -> int:
        return hash((self.amount, self.currency.code))

    def is_zero(self) -> bool:
        return self.amount == 0

    def allocate(self, ratios: Iterable[int]) -> list[Money]:
        """Split into parts proportional to ``ratios`` without losing minor units.

        Leftover minor units go to the first parts, one each.
        """
        ratios = list(ratios)
        if not ratios or any(r < 0 for r in ratios) or sum(ratios) == 0:
            raise ValueError("ratios must be non-negative and not all zero")
        places = self.currency.minor_units
        total = int(self.amount.scaleb(places))
        weight = sum(ratios)
        parts = [total * r // weight for r in ratios]
        for i in range(total - sum(parts)):
            parts[i % len(parts)] += 1
        return [Money(Decimal(p).scaleb(-places), self.currency) for p in parts]

    def __repr__(self) -> str:
        return f"Money('{self.amount}', '{self.currency.code}')"

    def __str__(self) -> str:
        return f"{self.currency.code} {self.amount:,}"
