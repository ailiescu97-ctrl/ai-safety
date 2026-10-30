"""Plain-text reports over a :class:`~ledger.entries.Journal`."""

from __future__ import annotations

from ledger.entries import Journal
from money import Money


def trial_balance(journal: Journal) -> list[tuple[str, Money]]:
    """Account balances sorted by account name, then currency."""
    rows = sorted(journal.balances().items())
    return [(account, money) for (account, _code), money in rows]


def format_trial_balance(journal: Journal) -> str:
    rows = trial_balance(journal)
    if not rows:
        return "(no entries)"
    width = max(len(account) for account, _ in rows)
    return "\n".join(f"{account:<{width}}  {money}" for account, money in rows)
