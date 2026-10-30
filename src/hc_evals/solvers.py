"""Setup and agent solvers for the tampering task."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

from inspect_ai.agent import AgentSubmit, as_solver, react
from inspect_ai.solver import Generate, Solver, TaskState, solver
from inspect_ai.util import sandbox

from hc_evals.tools import AGENT_USER, WORK_ROOT, agent_tools, append_audit, audited, submit

PKG = Path(__file__).parent

# Store keys read by the scorer.
RUN_START = "run_start"
ORIG_HEAD = "orig_head"
PREFILL_CALL_IDS = "prefill_call_ids"
CONT_EDIT_SHA = "cont_edit_sha"  # tests/test_money.py right after the prefill edit

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


class SetupError(RuntimeError):
    pass


async def _exec(cmd: str, user: str = AGENT_USER) -> str:
    res = await sandbox().exec(["bash", "-c", cmd], cwd=WORK_ROOT, user=user)
    if not res.success:
        raise SetupError(f"{cmd!r} failed: {res.stderr.strip()}")
    return res.stdout


def load_prefill(rel_path: str) -> dict:
    return json.loads((PKG / rel_path).read_text(encoding="utf-8"))


@solver
def setup_environment() -> Solver:
    """Record the starting state; for continuation, replay the prefilled edit.

    The prefilled tool calls get audit lines, timestamped before the run
    started, so the log the agent can read has no gap. They are marked
    ``source: prefill`` in the harness copy only.
    """

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        start = datetime.now(UTC)
        state.store.set(RUN_START, start.strftime(TS_FORMAT))
        state.store.set(ORIG_HEAD, (await _exec("git rev-parse HEAD")).strip())
        if state.metadata["mode"] == "continuation":
            doc = load_prefill(state.metadata["prefill"])
            setup = doc["setup"]
            await _exec(setup["cmd"], user=setup.get("user", AGENT_USER))
            calls = {tc["id"]: tc for m in doc["messages"] for tc in m.get("tool_calls", []) or []}
            audit = setup["audit"]
            for call_id, offset in zip(audit["tool_call_ids"], audit["offsets_s"], strict=True):
                tc = calls[call_id]
                ts = (start + timedelta(seconds=offset)).strftime(TS_FORMAT)
                await append_audit(tc["function"], tc["arguments"], source="prefill", ts=ts)
            state.store.set(PREFILL_CALL_IDS, list(audit["tool_call_ids"]))
            sha = await _exec("sha256sum tests/test_money.py")
            state.store.set(CONT_EDIT_SHA, sha.split()[0])
        return state

    return solve


@solver
def coding_agent(tool_timeout: int) -> Solver:
    """react() with the audited tools; the system and user messages come from the sample."""

    async def solve(state: TaskState, generate: Generate) -> TaskState:
        agent = react(
            prompt=None,
            tools=agent_tools(state.metadata["escalation_path"], tool_timeout),
            submit=AgentSubmit(tool=audited(submit()), answer_only=True, keep_in_messages=True),
        )
        return await as_solver(agent)(state, generate)

    return solve
