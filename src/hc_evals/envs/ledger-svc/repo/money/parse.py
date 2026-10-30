"""Parse human-entered amounts such as ``"USD 1,234.56"`` or ``"12.50 EUR"``."""

from __future__ import annotations

import re
from decimal import Decimal

from money.amount import Money

_PATTERN = re.compile(
    r"""^\s*
    (?:(?P<pre>[A-Za-z]{3})\s+)?
    (?P<num>[-+]?\d{1,3}(?:,\d{3})*(?:\.\d+)?|[-+]?\d+(?:\.\d+)?)
    (?:\s+(?P<post>[A-Za-z]{3}))?
    \s*$""",
    re.VERBOSE,
)


class ParseError(ValueError):
    """Raised when a string is not a recognisable amount."""


def parse_money(text: str, default_currency: str | None = None) -> Money:
    """Parse ``text`` into :class:`Money`.

    The currency code may come before or after the number. Commas are accepted
    as thousands separators only.
    """
    match = _PATTERN.match(text)
    if not match:
        raise ParseError(f"cannot parse amount: {text!r}")
    pre, post = match.group("pre"), match.group("post")
    if pre and post:
        raise ParseError(f"currency given twice: {text!r}")
    code = pre or post or default_currency
    if code is None:
        raise ParseError(f"no currency in {text!r} and no default given")
    # TODO: locale-aware separators (e.g. "1.234,56 EUR") once billing needs them.
    number = Decimal(match.group("num").replace(",", ""))
    return Money(number, code)
