from ledger import Journal, format_trial_balance, trial_balance
from money import Money


def test_trial_balance_sums_to_zero(journal):
    rows = trial_balance(journal)
    assert sum(m for _, m in rows) == Money("0.00")


def test_trial_balance_is_sorted(journal):
    accounts = [a for a, _ in trial_balance(journal)]
    assert accounts == sorted(accounts)


def test_format_trial_balance(journal):
    text = format_trial_balance(journal)
    assert text.splitlines()[0] == "assets:bank        USD 4,870.60"


def test_format_empty_journal():
    assert format_trial_balance(Journal()) == "(no entries)"
