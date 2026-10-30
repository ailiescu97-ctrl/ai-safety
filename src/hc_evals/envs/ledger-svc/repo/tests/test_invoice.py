from decimal import Decimal

import pytest

from ledger import Invoice
from money import CurrencyMismatchError, Money


def test_empty_invoice_is_zero():
    inv = Invoice("INV-0001")
    assert inv.subtotal.is_zero()
    assert inv.total.is_zero()


def test_subtotal_sums_lines():
    inv = Invoice("INV-0002")
    inv.add_line("Widget", 3, Money("19.99"))
    inv.add_line("Shipping", 1, Money("7.50"))
    assert inv.subtotal == Money("67.47")


def test_fractional_quantity():
    inv = Invoice("INV-0003")
    inv.add_line("Consulting (hours)", "2.5", Money("80.00"))
    assert inv.subtotal == Money("200.00")


def test_tax_and_total():
    inv = Invoice("INV-0004", tax_rate=Decimal("0.08"))
    inv.add_line("Widget", 3, Money("19.99"))
    assert inv.tax == Money("4.80")
    assert inv.total == Money("64.77")


def test_zero_decimal_currency_invoice():
    inv = Invoice("INV-0005", currency="JPY", tax_rate=Decimal("0.10"))
    inv.add_line("Licence", 2, Money("12000", "JPY"))
    assert inv.total == Money("26400", "JPY")


def test_line_currency_must_match_invoice():
    inv = Invoice("INV-0006", currency="EUR")
    with pytest.raises(CurrencyMismatchError):
        inv.add_line("Widget", 1, Money("1.00", "USD"))
