"""Invoices with line items and a single tax rate."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from money import Money
from money.amount import CurrencyMismatchError
from money.round import Number, to_decimal


@dataclass(frozen=True)
class LineItem:
    description: str
    quantity: Decimal
    unit_price: Money

    @property
    def net(self) -> Money:
        return self.unit_price * self.quantity


@dataclass
class Invoice:
    number: str
    currency: str = "USD"
    tax_rate: Decimal = Decimal("0")
    lines: list[LineItem] = field(default_factory=list)

    def add_line(self, description: str, quantity: Number, unit_price: Money) -> LineItem:
        if unit_price.currency.code != self.currency:
            raise CurrencyMismatchError(
                f"line in {unit_price.currency} on a {self.currency} invoice"
            )
        line = LineItem(description, to_decimal(quantity), unit_price)
        self.lines.append(line)
        return line

    @property
    def subtotal(self) -> Money:
        return sum((line.net for line in self.lines), Money.zero(self.currency))

    @property
    def tax(self) -> Money:
        return self.subtotal * self.tax_rate

    @property
    def total(self) -> Money:
        return self.subtotal + self.tax
