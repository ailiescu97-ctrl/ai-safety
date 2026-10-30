"""Budget-capped real-model runs (SPEC §9a). Lead only.

    python -m hc_evals.run --init-ledger           # create the spend ledger, once
    python -m hc_evals.run --set dry_run           # one cheap model + reasoning probe
    python -m hc_evals.run --set week1_targets     # needs logs/dry_run_ok.json

Runs go in batches of one model x one epoch over the set's scenarios. Before
each batch the worst case (every run hitting token_limit) must fit both the
total cap and the phase allocation in configs/budget.yaml. After each batch the
actual cost is appended to logs/spend_ledger.jsonl. There is deliberately no
flag or environment variable to skip any of this: raising the cap means the
lead edits configs/budget.yaml.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

from inspect_ai import eval
from inspect_ai.log import EvalLog, EvalSample
from inspect_ai.model import ContentReasoning, GenerateConfig, Model, get_model

from hc_evals.clauses import REPO_ROOT
from hc_evals.config import load_budget, load_models, load_prices
from hc_evals.schema import DryRunOk, LedgerEntry, ModelPrice, TokensPerRun
from hc_evals.tasks import tampering
from hc_evals.validate import load_scenarios

LEDGER = REPO_ROOT / "logs" / "spend_ledger.jsonl"
DRY_RUN_OK = REPO_ROOT / "logs" / "dry_run_ok.json"
RUN_LOG_DIR = REPO_ROOT / "logs" / "runs"
PHASES = {"dry_run": "dry_runs", "week1_targets": "week1"}
EXPECTED_DETECTORS = 5
MTOK = 1_000_000


class Refused(Exception):
    """A run or batch was refused; the message says why."""


# --- ledger --------------------------------------------------------------------


def now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def read_ledger(path: Path | None = None) -> list[LedgerEntry]:
    path = path or LEDGER
    if not path.exists():
        raise Refused(f"spend ledger {path} is missing; the lead creates it with --init-ledger")
    try:
        entries = [
            LedgerEntry.model_validate_json(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except Exception as exc:
        raise Refused(f"spend ledger {path} can't be parsed ({exc}); refusing to run") from exc
    if not entries or entries[0].kind != "init":
        raise Refused(f"spend ledger {path} has no init line; refusing to run")
    running = 0.0
    for e in entries:
        running += e.cost_usd
        if abs(running - e.cumulative_usd) > 0.01:
            raise Refused(f"spend ledger {path} totals don't add up at {e.ts}; refusing to run")
    return entries


def init_ledger(path: Path | None = None) -> None:
    path = path or LEDGER
    if path.exists():
        raise Refused(f"{path} already exists; the ledger is created exactly once")
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = LedgerEntry(ts=now(), kind="init", cumulative_usd=0.0)
    with path.open("x", encoding="utf-8") as fh:
        fh.write(entry.model_dump_json() + "\n")


def append_ledger(entry: LedgerEntry, path: Path | None = None) -> None:
    with (path or LEDGER).open("a", encoding="utf-8") as fh:
        fh.write(entry.model_dump_json() + "\n")


def total_spent(entries: list[LedgerEntry]) -> float:
    return entries[-1].cumulative_usd


def phase_spent(entries: list[LedgerEntry], phase: str) -> float:
    return sum(e.cost_usd for e in entries if e.phase == phase)


# --- prices and costs ---------------------------------------------------------


def price(model_name: str) -> ModelPrice:
    p = load_prices().models.get(model_name)
    if p is None or p.input is None or p.output is None:
        raise Refused(f"no input/output price for {model_name} in configs/prices.yaml")
    return p


def usage_cost(model_name: str, input_tokens: float, cached: float, output: float) -> float:
    """Cached reads are priced on top of input tokens (overestimates if input includes them)."""
    p = price(model_name)
    cached_rate = p.cached_input if p.cached_input is not None else p.input
    return (input_tokens * p.input + cached * cached_rate + output * p.output) / MTOK


def worst_case(model_name: str, runs: int) -> float:
    """Every run hits token_limit at the budget's input/output mix."""
    p = price(model_name)
    mix = load_budget().cost_at_limit_mix
    tokens = load_models().run_limits.token_limit
    return runs * tokens * (mix.input_share * p.input + mix.output_share * p.output) / MTOK


def check_fits(entries: list[LedgerEntry], phase: str, amount: float, what: str) -> None:
    budget = load_budget()
    spent = total_spent(entries)
    remaining = budget.total_cap_usd - spent
    alloc = budget.allocation_usd.get(phase)
    if alloc is None:
        raise Refused(f"no allocation for phase {phase!r} in configs/budget.yaml")
    in_phase = phase_spent(entries, phase)
    if spent + amount > budget.total_cap_usd:
        raise Refused(
            f"{what} ${amount:.2f} would exceed the total cap: spent ${spent:.2f} of "
            f"${budget.total_cap_usd:.2f}, ${remaining:.2f} remaining"
        )
    if in_phase + amount > alloc:
        raise Refused(
            f"{what} ${amount:.2f} would exceed the {phase} allocation: ${in_phase:.2f} of "
            f"${alloc:.2f} spent in this phase (total remaining ${remaining:.2f})"
        )


# --- models --------------------------------------------------------------------


def model_string(model_name: str) -> str:
    return f"{load_models().api.provider}/{model_name}"


def resolve_model(model_name: str) -> Model:
    cfg = load_models()
    base_url = os.environ.get(cfg.api.base_url_env)
    api_key = os.environ.get(cfg.api.api_key_env)
    if not base_url or not api_key:
        raise Refused(f"set {cfg.api.base_url_env} and {cfg.api.api_key_env} for the model API")
    return get_model(
        model_string(model_name),
        base_url=base_url,
        api_key=api_key,
        # OpenAI models use the Responses API; others use chat completions, which
        # OpenAI-compatible endpoints for other providers support
        responses_api=model_name.rsplit("/", 1)[-1].startswith("gpt-"),
        background=False,
        config=GenerateConfig(max_connections=cfg.run_limits.max_connections),
    )


# --- batches -------------------------------------------------------------------


def sample_tokens(sample: EvalSample) -> tuple[int, int, int]:
    inp = cached = out = 0
    for u in (sample.model_usage or {}).values():
        inp += u.input_tokens
        cached += u.input_tokens_cache_read or 0
        out += u.output_tokens
    return inp, cached, out


def run_batch(
    model: Model,
    model_name: str,
    phase: str,
    epoch: int,
    *,
    limit: int | None = None,
    log_dir: Path | None = None,
) -> EvalLog:
    """One model x one epoch over the scenarios, inside the budget."""
    entries = read_ledger()
    runs = limit or len(load_scenarios())
    check_fits(entries, phase, worst_case(model_name, runs), f"batch worst case ({runs} runs)")
    log = eval(
        tampering(),
        model=model,
        epochs=1,
        limit=limit,
        log_dir=str(log_dir or RUN_LOG_DIR),
        metadata={"batch_epoch": epoch, "model_name": model_name, "phase": phase},
        display="plain",
    )[0]
    inp = cached = out = 0
    for s in log.samples or []:
        a, b, c = sample_tokens(s)
        inp, cached, out = inp + a, cached + b, out + c
    cost = usage_cost(model_name, inp, cached, out)
    entries = read_ledger()
    entry = LedgerEntry(
        ts=now(),
        kind="batch",
        phase=phase,
        model=model_name,
        runs=len(log.samples or []),
        input_tokens=inp,
        cached_input_tokens=cached,
        output_tokens=out,
        cost_usd=round(cost, 6),
        cumulative_usd=round(total_spent(entries) + cost, 6),
        log_path=log.location,
    )
    append_ledger(entry)
    cap = load_budget().total_cap_usd
    spent = entry.cumulative_usd
    print(f"batch {model_name} epoch {epoch}: ${cost:.2f}; spent ${spent:.2f} of ${cap:.2f}")
    return log


# --- estimates -----------------------------------------------------------------


def read_dry_run_ok(path: Path | None = None) -> DryRunOk:
    path = path or DRY_RUN_OK
    if not path.exists():
        raise Refused(f"{path} is missing: run and pass --set dry_run first")
    return DryRunOk.model_validate_json(path.read_text(encoding="utf-8"))


def expected_per_run(model_name: str, dry: DryRunOk) -> float:
    """Dry-run tokens per run for this model, or the mean over dry-run models."""
    tpr = dry.tokens_per_run.get(model_name)
    if tpr is None:
        vals = list(dry.tokens_per_run.values())
        if not vals:
            raise Refused("dry_run_ok.json has no token counts; refusing to estimate")
        tpr = TokensPerRun(
            input=sum(v.input for v in vals) / len(vals),
            cached_input=sum(v.cached_input for v in vals) / len(vals),
            output=sum(v.output for v in vals) / len(vals),
        )
    return usage_cost(model_name, tpr.input, tpr.cached_input, tpr.output)


def estimate(plan: list[tuple[str, int]], dry: DryRunOk | None) -> dict:
    """plan: (model_name, runs). Expected needs dry-run data; worst case never does."""
    rows = []
    for name, runs in plan:
        rows.append(
            {
                "model": name,
                "runs": runs,
                "expected": None if dry is None else runs * expected_per_run(name, dry),
                "worst_case": worst_case(name, runs),
            }
        )
    exp = None if dry is None else sum(r["expected"] for r in rows)
    return {"rows": rows, "expected": exp, "worst_case": sum(r["worst_case"] for r in rows)}


def confirm(est: dict, entries: list[LedgerEntry], phase: str) -> bool:
    budget = load_budget()
    remaining = budget.total_cap_usd - total_spent(entries)
    for r in est["rows"]:
        exp = "n/a (no dry-run data)" if r["expected"] is None else f"${r['expected']:.2f}"
        print(
            f"  {r['model']}: {r['runs']} runs, expected {exp}, worst case ${r['worst_case']:.2f}"
        )
    exp = "n/a" if est["expected"] is None else f"${est['expected']:.2f}"
    print(
        f"Total expected {exp}, worst case ${est['worst_case']:.2f}. Budget remaining "
        f"${remaining:.2f} of ${budget.total_cap_usd:.2f}; {phase} allocation "
        f"${budget.allocation_usd.get(phase, 0):.2f} (${phase_spent(entries, phase):.2f} spent)."
    )
    return input("Type yes to start: ").strip() == "yes"


# --- the two sets ---------------------------------------------------------------


def reasoning_visible(log: EvalLog) -> bool:
    for s in log.samples or []:
        for m in s.messages:
            if m.role == "assistant" and not isinstance(m.content, str):
                if any(isinstance(c, ContentReasoning) and c.reasoning.strip() for c in m.content):
                    return True
    return False


def run_dry_run() -> int:
    cfg = load_models()
    phase = PHASES["dry_run"]
    n = len(load_scenarios())
    probes = [m for m in cfg.reasoning_check if m not in cfg.dry_run]
    plan = [(m, n) for m in cfg.dry_run] + [(m, 1) for m in probes]
    entries = read_ledger()
    # There is no dry-run data yet, so only the worst case can be shown.
    est = estimate(plan, None)
    check_fits(entries, phase, est["worst_case"], "dry run worst case")
    if not confirm(est, entries, phase):
        print("not started")
        return 1
    logs = {m: run_batch(resolve_model(m), m, phase, 1) for m in cfg.dry_run}
    logs |= {m: run_batch(resolve_model(m), m, phase, 1, limit=1) for m in probes}
    harness_errors, detectors_ok, tokens, runs = 0, True, {}, 0
    for name, log in logs.items():
        per = [sample_tokens(s) for s in log.samples or []]
        runs += len(per)
        if per:
            tokens[name] = TokensPerRun(
                input=sum(p[0] for p in per) / len(per),
                cached_input=sum(p[1] for p in per) / len(per),
                output=sum(p[2] for p in per) / len(per),
            )
        for s in log.samples or []:
            score = (s.scores or {}).get("programmatic")
            if score is None or "harness_error" in score.metadata["flags"]:
                harness_errors += 1
            elif len(score.metadata["detector_events"]) != EXPECTED_DETECTORS:
                detectors_ok = False
    if harness_errors or not detectors_ok:
        print(f"dry run not OK: {harness_errors} harness errors, detectors_ok={detectors_ok}")
        return 1
    ok = DryRunOk(
        ts=now(),
        runs=runs,
        harness_errors=0,
        detectors_ok=True,
        tokens_per_run=tokens,
        reasoning_visible={m: reasoning_visible(logs[m]) for m in cfg.reasoning_check if m in logs},
    )
    DRY_RUN_OK.write_text(ok.model_dump_json(indent=2) + "\n", encoding="utf-8")
    for m, visible in ok.reasoning_visible.items():
        if not visible:
            print(f"WARNING: no reasoning from {m} reached the transcript")
    print(f"dry run OK; wrote {DRY_RUN_OK}")
    return 0


def run_week1() -> int:
    cfg = load_models()
    phase = PHASES["week1_targets"]
    dry = read_dry_run_ok()
    n, epochs = len(load_scenarios()), cfg.epochs.week1
    plan = [(m, n * epochs) for m in cfg.week1_targets]
    entries = read_ledger()
    est = estimate(plan, dry)
    check_fits(entries, phase, est["expected"], "expected cost of the whole run")
    if not confirm(est, entries, phase):
        print("not started")
        return 1
    for m in cfg.week1_targets:
        model = resolve_model(m)
        for epoch in range(1, epochs + 1):
            run_batch(model, m, phase, epoch)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--set", choices=sorted(PHASES))
    group.add_argument("--init-ledger", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.init_ledger:
            init_ledger()
            print(f"created {LEDGER}")
            return 0
        return run_dry_run() if args.set == "dry_run" else run_week1()
    except Refused as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
