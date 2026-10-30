"""Double-entry journal: postings, entries and running balances."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Iterator

from money import Money


class UnbalancedEntryError(ValueError):
    """Raised when an entry's postings do not sum to zero in every currency."""


@dataclass(frozen=True)
class Posting:
    account: str
    amount: Money


@dataclass(frozen=True)
class JournalEntry:
    on: date
    memo: str
    postings: tuple[Posting, ...]

    def __post_init__(self) -> None:
        if len(self.postings) < 2:
            raise ValueError("an entry needs at least two postings")
        totals: dict[str, Money] = {}
        for p in self.postings:
            code = p.amount.currency.code
            totals[code] = totals.get(code, Money.zero(code)) + p.amount
        unbalanced = sorted(code for code, total in totals.items() if not total.is_zero())
        if unbalanced:
            raise UnbalancedEntryError(f"entry {self.memo!r} does not balance in {unbalanced}")


@dataclass
class Journal:
    entries: list[JournalEntry] = field(default_factory=list)

    def post(self, on: date, memo: str, *postings: tuple[str, Money]) -> JournalEntry:
        entry = JournalEntry(on, memo, tuple(Posting(a, m) for a, m in postings))
        self.entries.append(entry)
        return entry

    def __iter__(self) -> Iterator[JournalEntry]:
        return iter(self.entries)

    def __len__(self) -> int:
        return len(self.entries)

    def balances(self) -> dict[tuple[str, str], Money]:
        """Balance per (account, currency code)."""
        out: dict[tuple[str, str], Money] = {}
        for entry in self.entries:
            for p in entry.postings:
                key = (p.account, p.amount.currency.code)
                out[key] = out.get(key, Money.zero(p.amount.currency)) + p.amount
        return out

    def balance(self, account: str, currency: str = "USD") -> Money:
        return self.balances().get((account, currency.upper()), Money.zero(currency))
