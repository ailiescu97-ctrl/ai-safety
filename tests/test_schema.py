"""Acceptance 1: scenarios and the clause map validate."""

import subprocess
import sys

import pytest
import yaml

from hc_evals import validate
from hc_evals.clauses import load_clause_map, normalise, text_sha256
from hc_evals.schema import Scenario


def test_nine_scenarios_validate():
    scenarios = validate.load_scenarios()
    assert len(scenarios) == 9
    assert all(isinstance(s, Scenario) for s in scenarios.values())


def test_validate_cli_exits_zero():
    res = subprocess.run(
        [sys.executable, "-m", "hc_evals.validate"], capture_output=True, text=True
    )
    assert res.returncode == 0, res.stderr


def test_validate_reports_no_errors():
    assert validate.validate() == []


def test_clause_hash_ignores_whitespace():
    assert normalise("  a \n\t b ") == "a b"
    assert text_sha256("They  will\nnot") == text_sha256("They will not")


def test_clause_map_has_week1_clauses():
    ids = {c.id for c in load_clause_map().clauses}
    assert {"HC-2b", "HC-4", "HC-6"} <= ids


def _one_scenario():
    path = validate.SCENARIO_DIR / "TAMP-ledger-user-plain-high.yaml"
    return path, yaml.safe_load(path.read_text())


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("task_text", "Fix it.", "task_text"),
        ("code_version", "HAI-CoC-2026-09-14#00", "code_version"),
        ("pressure", "low", "id should be"),
        ("tripwires", ["protected_hash", "made_up"], "unknown tripwires"),
        ("canary", "00000000-0000-0000-0000-000000000000", "canary"),
    ],
)
def test_validate_catches_bad_scenarios(field, value, message):
    path, data = _one_scenario()
    data[field] = value
    s = Scenario.model_validate(data)
    clause_ids = {c.id for c in load_clause_map().clauses}
    errors = validate.check_scenario(path, s, clause_ids, validate.code_version())
    assert any(message in e for e in errors), errors


def test_schema_rejects_unknown_level():
    _, data = _one_scenario()
    data["wording"] = "shouty"
    with pytest.raises(ValueError):
        Scenario.model_validate(data)
