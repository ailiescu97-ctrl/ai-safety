"""Acceptance A1, A2 and B1–B5: the run script's gates and the $500 budget cap."""

import json
import re
import shutil
import subprocess
import sys

import pytest
import yaml
from inspect_ai.model import ModelUsage, get_model

from hc_evals import config, run
from hc_evals.clauses import REPO_ROOT
from hc_evals.schema import LedgerEntry

PRICES = {
    "claude-haiku-5-5": {"input": 1.0, "output": 5.0},
    "gpt-6.1-sol": {"input": 2.0, "output": 8.0},
    "kimi-k3": {"input": 0.5, "output": 2.0},
    "gemini-4-argon": {"input": 1.0, "output": 4.0},
    "mock-model": {"input": 10.0, "output": 30.0},
    "pricey-model": {"input": 5.0, "output": 5.0},  # 9 runs x 400k tokens -> $18 worst case
    "phase-buster": {"input": 36.2, "output": 36.2},  # 9 runs -> about $130 worst case
}


@pytest.fixture
def env(tmp_path, monkeypatch):
    """Configs, ledger and dry-run file in a temp dir; the real logs/ is never touched."""
    cfg = tmp_path / "configs"
    shutil.copytree(REPO_ROOT / "configs", cfg)
    (cfg / "prices.yaml").write_text(yaml.safe_dump({"models": PRICES}))
    monkeypatch.setattr(config, "CONFIG_DIR", cfg)
    monkeypatch.setattr(run, "LEDGER", tmp_path / "logs" / "spend_ledger.jsonl")
    monkeypatch.setattr(run, "DRY_RUN_OK", tmp_path / "logs" / "dry_run_ok.json")
    monkeypatch.setattr(run, "RUN_LOG_DIR", tmp_path / "logs" / "runs")
    (tmp_path / "logs").mkdir()
    return tmp_path


def _no_eval(*args, **kwargs):
    raise AssertionError("an eval was started")


def _ledger(env, *batches):
    run.init_ledger()
    total = 0.0
    for phase, cost in batches:
        total += cost
        run.append_ledger(
            LedgerEntry(
                ts="t", kind="batch", phase=phase, model="x", cost_usd=cost, cumulative_usd=total
            )
        )


def _dry_run_ok(env, tokens):
    data = {
        "ts": "t",
        "runs": 9,
        "harness_errors": 0,
        "detectors_ok": True,
        "tokens_per_run": tokens,
        "reasoning_visible": {"kimi-k3": True},
    }
    run.DRY_RUN_OK.write_text(json.dumps(data))


# --- A1 ------------------------------------------------------------------------


def test_week1_refused_without_dry_run(env, monkeypatch, capsys):
    _ledger(env)
    monkeypatch.setattr(run, "eval", _no_eval)
    assert run.main(["--set", "week1_targets"]) != 0
    assert "dry_run_ok.json is missing" in capsys.readouterr().err


def test_week1_cli_exits_nonzero_in_fresh_checkout():
    # The real repo has no logs/dry_run_ok.json, so this refuses before anything starts.
    assert not (REPO_ROOT / "logs" / "dry_run_ok.json").exists()
    res = subprocess.run(
        [sys.executable, "-m", "hc_evals.run", "--set", "week1_targets"],
        capture_output=True,
        text=True,
    )
    assert res.returncode != 0 and "REFUSED" in res.stderr


# --- A2 ------------------------------------------------------------------------


def test_estimate_matches_hand_computation_and_needs_yes(env, monkeypatch, capsys):
    _ledger(env)
    _dry_run_ok(
        env,
        {
            "gpt-6.1-sol": {"input": 100_000, "cached_input": 0, "output": 5_000},
            "kimi-k3": {
                "input": 80_000,
                "cached_input": 20_000,
                "output": 10_000,
            },
        },
    )
    dry = run.read_dry_run_ok()
    est = run.estimate([("gpt-6.1-sol", 90), ("kimi-k3", 90)], dry)
    gpt = 90 * (100_000 * 2.0 + 5_000 * 8.0) / 1e6  # $21.60
    kimi = 90 * (80_000 * 0.5 + 20_000 * 0.5 + 10_000 * 2.0) / 1e6  # $6.30
    assert est["expected"] == pytest.approx(gpt + kimi, rel=0.01)
    assert est["worst_case"] == pytest.approx(
        90 * 400_000 * (0.9 * 2 + 0.1 * 8) / 1e6 + 90 * 400_000 * (0.9 * 0.5 + 0.1 * 2) / 1e6,
        rel=0.01,
    )

    monkeypatch.setattr(run, "run_batch", _no_eval)
    monkeypatch.setattr(run, "resolve_model", _no_eval)
    monkeypatch.setattr("builtins.input", lambda prompt="": "no")
    assert run.main(["--set", "week1_targets"]) == 1
    out = capsys.readouterr().out
    assert "not started" in out and "$27.90" in out


def test_no_estimate_without_dry_run_tokens(env):
    _dry_run_ok(env, {})
    with pytest.raises(run.Refused, match="refusing to estimate"):
        run.estimate([("gpt-6.1-sol", 90)], run.read_dry_run_ok())


def test_missing_price_refuses(env):
    with pytest.raises(run.Refused, match="no input/output price"):
        run.worst_case("not-in-prices", 9)


# --- B1, B5: pre-batch check -----------------------------------------------------


def test_batch_refused_near_cap(env, monkeypatch):
    _ledger(env, ("later", 490.0))
    monkeypatch.setattr(run, "eval", _no_eval)
    with pytest.raises(run.Refused) as exc:
        run.run_batch(get_model("mockllm/model"), "pricey-model", "week1", 1)
    msg = str(exc.value)
    assert "total cap" in msg and "$10.00 remaining" in msg and "$18.00" in msg
    assert len(run.read_ledger()) == 2


def test_batch_refused_over_phase_allocation(env, monkeypatch):
    _ledger(env)
    monkeypatch.setattr(run, "eval", _no_eval)
    assert run.worst_case("phase-buster", 9) < 500
    with pytest.raises(run.Refused, match="week1 allocation"):
        run.run_batch(get_model("mockllm/model"), "phase-buster", "week1", 1)


# --- B2: missing or corrupt ledger -------------------------------------------------


def test_missing_ledger_refused(env, monkeypatch):
    monkeypatch.setattr(run, "eval", _no_eval)
    with pytest.raises(run.Refused, match="missing"):
        run.run_batch(get_model("mockllm/model"), "mock-model", "week1", 1)


@pytest.mark.parametrize(
    "content", ["", "not json\n", '{"ts": "t", "kind": "batch", "cumulative_usd": 0}\n']
)
def test_corrupt_ledger_refused(env, monkeypatch, content):
    run.LEDGER.write_text(content)
    monkeypatch.setattr(run, "eval", _no_eval)
    with pytest.raises(run.Refused):
        run.run_batch(get_model("mockllm/model"), "mock-model", "week1", 1)


def test_ledger_totals_must_add_up(env):
    run.init_ledger()
    run.append_ledger(
        LedgerEntry(ts="t", kind="batch", phase="week1", cost_usd=5.0, cumulative_usd=1.0)
    )
    with pytest.raises(run.Refused, match="don't add up"):
        run.read_ledger()


def test_init_ledger_only_once(env):
    run.init_ledger()
    with pytest.raises(run.Refused, match="exactly once"):
        run.init_ledger()


# --- B3: a real mockllm batch updates the ledger ----------------------------------------


@pytest.mark.docker
def test_mockllm_batch_appends_one_ledger_line(env, compose_project):
    from tests.scripted import call

    _ledger(env)
    # Two calls of 120k tokens stay under the 400k token_limit.
    usage = ModelUsage(input_tokens=100_000, output_tokens=20_000, total_tokens=120_000)
    outs = [
        call("bash", usage=usage, command="ls"),
        call("submit", usage=usage, answer="Nothing to change."),
    ]
    model = get_model("mockllm/model", custom_outputs=outs)
    before = len(run.read_ledger())
    run.run_batch(model, "mock-model", "week1", 3, limit=1)
    entries = run.read_ledger()
    assert len(entries) == before + 1
    last = entries[-1]
    expected = (200_000 * 10.0 + 40_000 * 30.0) / 1e6  # $3.20
    assert (last.input_tokens, last.output_tokens, last.runs) == (200_000, 40_000, 1)
    assert last.cost_usd == pytest.approx(expected, abs=0.01)
    assert last.cumulative_usd == pytest.approx(expected, abs=0.01)


# --- B4: no bypass ----------------------------------------------------------------------


@pytest.mark.parametrize("flag", ["--force", "--ignore-budget", "--no-budget", "--cap"])
def test_no_bypass_flags(flag):
    with pytest.raises(SystemExit) as exc:
        run.main(["--set", "week1_targets", flag])
    assert exc.value.code == 2


def test_only_api_env_vars_are_read():
    src = (REPO_ROOT / "src" / "hc_evals" / "run.py").read_text()
    reads = re.findall(
        r"os\.environ\.get\(([^)]*)\)|os\.getenv\(([^)]*)\)|os\.environ\[([^\]]*)\]", src
    )
    assert [r for r in reads if r[0]] == [
        ("cfg.api.base_url_env", "", ""),
        ("cfg.api.api_key_env", "", ""),
    ]
    assert not any(r[1] or r[2] for r in reads)
    for path in (REPO_ROOT / "src").rglob("*.py"):
        text = path.read_text()
        assert not re.search(r"(force|ignore.budget|skip.budget|override.cap)", text, re.I), path
        assert "budget.yaml" not in text or path.name in {"run.py", "config.py"}, path


API_ENV = {
    "HC_API_BASE_URL": "http://api.test/v1",
    "HC_API_KEY": "k",
}


@pytest.mark.parametrize(
    ("name", "responses"),
    [
        ("claude-haiku-5-5", False),
        ("deepseek-v4-pro", False),
        ("gpt-6.1-sol", True),
    ],
)
def test_model_name_api_route(env, monkeypatch, name, responses):
    for k, v in API_ENV.items():
        monkeypatch.setenv(k, v)
    api = run.resolve_model(name).api
    assert api.responses_api is responses
    assert not api.background


@pytest.mark.parametrize("missing", sorted(API_ENV))
def test_model_name_refused_without_env_var(env, monkeypatch, missing):
    for k, v in API_ENV.items():
        monkeypatch.setenv(k, v)
    monkeypatch.delenv(missing)
    with pytest.raises(run.Refused, match=missing):
        run.resolve_model("claude-haiku-5-5")


def test_cap_holds_even_if_phase_allocation_is_bigger(env, monkeypatch):
    budget = yaml.safe_load((config.CONFIG_DIR / "budget.yaml").read_text())
    budget["allocation_usd"]["week1"] = 10_000
    (config.CONFIG_DIR / "budget.yaml").write_text(yaml.safe_dump(budget))
    _ledger(env, ("later", 495.0))
    monkeypatch.setattr(run, "eval", _no_eval)
    with pytest.raises(run.Refused, match="total cap"):
        run.run_batch(get_model("mockllm/model"), "pricey-model", "week1", 1)
