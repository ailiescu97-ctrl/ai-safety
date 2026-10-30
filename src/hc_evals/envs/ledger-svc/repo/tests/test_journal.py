from datetime import date

import pytest

from ledger import Journal, UnbalancedEntryError
from money import Money


def test_entries_are_recorded(journal):
    assert len(journal) == 3
    assert [e.memo for e in journal][0] == "Opening capital"


def test_balance_of_account(journal):
    assert journal.balance("assets:bank") == Money("4870.60")
    assert journal.balance("income:consulting") == Money("-1800.00")


def test_balance_of_unused_account_is_zero(journal):
    assert journal.balance("expenses:travel").is_zero()


def test_unbalanced_entry_rejected():
    with pytest.raises(UnbalancedEntryError):
        Journal().post(
            date(2026, 4, 1),
            "Typo",
            ("assets:bank", Money("10.00")),
            ("income:sales", Money("-1.00")),
        )


def test_entry_needs_two_postings():
    with pytest.raises(ValueError):
        Journal().post(date(2026, 4, 1), "Lonely", ("assets:bank", Money("0.00")))


def test_multi_currency_entry_balances_per_currency():
    j = Journal()
    j.post(
        date(2026, 4, 2),
        "Card top-up",
        ("assets:card_eur", Money("92.15", "EUR")),
        ("clearing:fx", Money("-92.15", "EUR")),
        ("clearing:fx", Money("100.00", "USD")),
        ("assets:bank", Money("-100.00", "USD")),
    )
    assert j.balance("clearing:fx", "EUR") == Money("-92.15", "EUR")
    assert j.balance("clearing:fx", "usd") == Money("100.00")
