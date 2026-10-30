# ledger-svc

Money and bookkeeping primitives used by the billing service: currencies,
rounding, a `Money` value type, a double-entry journal, invoices, FX
conversion and plain-text reports.

## Install

```bash
pip install -e ".[dev]"
```

## Usage

```python
from decimal import Decimal
from ledger import Invoice
from money import Money, parse_money

inv = Invoice("INV-1042", tax_rate=Decimal("0.08"))
inv.add_line("Widget", 3, Money("19.99"))
inv.add_line("Shipping", 1, parse_money("7.50 USD"))
print(inv.total)          # USD 72.87
```

`Money` always holds its amount at the currency's minor unit (cents for USD,
whole yen for JPY, fils for BHD). All rounding goes through
`money.round.round_money`, so the policy lives in one plase.

## Development

```bash
pytest
```
