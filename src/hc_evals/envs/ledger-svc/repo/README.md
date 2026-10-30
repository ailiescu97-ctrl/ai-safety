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
`money.round.round_money`, so the policy lives in one place.

## Layout

| Path | Contents |
|------|----------|
| `money/currency.py` | ISO 4217 metadata and lookup |
| `money/round.py` | rounding policy |
| `money/amount.py` | `Money` value type and allocation |
| `money/parse.py` | parsing of user-entered amounts |
| `ledger/entries.py` | journal, entries and balances |
| `ledger/invoice.py` | invoices and tax |
| `ledger/fx.py` | conversion against a rate table |
| `ledger/report.py` | trial balance |
| `logs/` | local tool output, ignored by git |

## Development

```bash
pytest
```

CI runs the suite on Python 3.11 and 3.12 for every push to `main` and every
pull request.
