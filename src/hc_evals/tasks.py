"""Inspect tasks."""

from __future__ import annotations

from inspect_ai import Epochs, Task, task
from inspect_ai.dataset import Sample
from inspect_ai.model import ChatMessage, ChatMessageSystem, ChatMessageUser
from inspect_ai.scorer import mean_score
from pydantic import TypeAdapter

from hc_evals.cells import system_suffix
from hc_evals.config import load_models
from hc_evals.gen_hostside import COMPOSE
from hc_evals.schema import Scenario
from hc_evals.scorers.programmatic import numeric_only, programmatic
from hc_evals.solvers import PKG, coding_agent, load_prefill, setup_environment
from hc_evals.validate import load_scenarios

SYSTEM_PROMPT = PKG / "prompts" / "system.md"


def system_prompt(s: Scenario) -> str:
    text = SYSTEM_PROMPT.read_text(encoding="utf-8").strip()
    if suffix := system_suffix(s.placement, s.wording):
        text = f"{text}\n\n{suffix}"
    return text


def sample_input(s: Scenario) -> list[ChatMessage]:
    messages: list[ChatMessage] = [ChatMessageSystem(content=system_prompt(s))]
    if s.mode == "continuation":
        assert s.prefill is not None
        prefill = load_prefill(s.prefill)["messages"]
        messages += TypeAdapter(list[ChatMessage]).validate_python(prefill)
    else:
        messages.append(ChatMessageUser(content=s.task_text))
    return messages


def to_sample(s: Scenario) -> Sample:
    return Sample(
        id=s.scenario_id,
        input=sample_input(s),
        metadata={
            "scenario_id": s.scenario_id,
            "base_env_id": s.base_env_id,
            "placement": s.placement,
            "wording": s.wording,
            "pressure": s.pressure,
            "escalation_path": s.escalation_path,
            "mode": s.mode,
            "prefill": s.prefill,
            "code_version": s.code_version,
            "clause_ids": s.clause_ids,
            "severity_default": s.severity_default,
            "reversibility_default": s.reversibility_default,
        },
    )


@task
def tampering(scenario: str | None = None) -> Task:
    """The 9 tampering scenarios on ledger-svc; ``scenario`` picks one by id."""
    scenarios = [s for s in load_scenarios().values() if scenario in (None, s.scenario_id)]
    if not scenarios:
        raise ValueError(f"no scenario {scenario!r}")
    limits = load_models().run_limits
    return Task(
        dataset=[to_sample(s) for s in scenarios],
        setup=setup_environment(),
        solver=coding_agent(tool_timeout=limits.tool_timeout_s),
        scorer=programmatic(),
        sandbox=("docker", str(COMPOSE)),
        epochs=Epochs(10, mean_score(numeric_only())),
        message_limit=limits.message_limit,
        token_limit=limits.token_limit,
        time_limit=limits.time_limit_s,
    )
