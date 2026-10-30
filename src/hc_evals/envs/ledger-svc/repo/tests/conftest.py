from datetime import date

import pytest

from ledger import Journal, RateTable
from money import Money


@pytest.fixture
def rates() -> RateTable:
    table = RateTable()
    table.set("USD", "EUR", "0.9215")
    table.set("USD", "JPY", "151.37")
    table.set("EUR", "GBP", "0.8612")
    return table


@pytest.fixture
def journal() -> Journal:
    j = Journal()
    j.post(
        date(2026, 3, 2),
        "Opening capital",
        ("assets:bank", Money("5000.00")),
        ("equity:capital", Money("-5000.00")),
    )
    j.post(
        date(2026, 3, 9),
        "Office supplies",
        ("expenses:office", Money("129.40")),
        ("assets:bank", Money("-129.40")),
    )
    j.post(
        date(2026, 3, 15),
        "Consulting income",
        ("assets:receivable", Money("1800.00")),
        ("income:consulting", Money("-1800.00")),
    )
    return j
