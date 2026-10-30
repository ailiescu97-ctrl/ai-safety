"""Pydantic models for scenarios, run records, human labels and the clause map."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Placement = Literal["operator_system", "user_turn"]
Wording = Literal["plain", "emphatic"]
Pressure = Literal["low", "high"]
Mode = Literal["fresh", "continuation"]
Label = Literal["compliant", "violation", "ambiguous"]
Severity = Literal["S0", "S1", "S2", "S3", "S4"]
Revers = Literal["R0", "R1", "R2", "R3"]
Flag = Literal[
    "attempted_only",
    "over_cautious",
    "disclosed",
    "concealed",
    "flagged_for_human",
    "harness_error",
    "limit_reached",
    "undisclosed",  # inherited problem fixed but not reported (legibility, HC-6/HC-4)
]
ContinuationBucket = Literal[
    "reverted_disclosed", "reverted_silent", "disclosed_only", "left_silent", "extended"
]


class Scenario(BaseModel):
    scenario_id: str
    base_env_id: str
    split: Literal["dev", "holdout"] = "dev"
    family: Literal["tampering"]
    clause_ids: list[str]
    code_version: str  # "HAI-CoC-2026-09-14#<sha256 of clause_map.yaml>"
    placement: Placement
    wording: Wording
    pressure: Pressure
    escalation_path: bool = True
    mode: Mode
    prefill: str | None = None  # path to prefill JSON, continuation only
    task_text: str
    tripwires: list[str]  # detector IDs
    legit_solution_exists: bool = True
    severity_default: Severity
    reversibility_default: Revers
    canary: str


class DetectorEvent(BaseModel):
    detector: str
    triggered: bool
    attempted: bool = False
    paths: list[str] = []
    detail: str = ""
    step: int | None = None  # index of first tool call touching paths, if found
    # Structured findings the scorer branches on (e.g. truncated, added files).
    facts: dict[str, bool | int | str | list[str] | None] = {}


class RunRecord(BaseModel):
    run_id: str
    scenario_id: str
    model: str
    epoch: int
    label: Label
    flags: list[Flag]
    clause_id: str | None
    evidence_step: int | None
    severity: Severity
    reversibility: Revers
    detector_events: list[DetectorEvent]
    final_report: str
    continuation_bucket: ContinuationBucket | None = None
    visible_tests_pass: bool
    hidden_tests_pass: bool
    code_version: str
    inspect_version: str
    log_path: str
    model_name: str | None = None  # name in configs/models.yaml
    model_version: str | None = None  # as reported by the provider, if returned


class HumanLabel(BaseModel):
    run_id: str
    rater_id: str
    label: Label
    severity: Severity
    reversibility: Revers
    clause_id: str | None
    evidence_step: int | None
    rationale: str


# Clause map (code_versions/<date>/clause_map.yaml). Not in the spec's schema
# block; added so validate.py can check it.


class ClauseSource(BaseModel):
    title: str
    url: str
    date: str


class ClauseEntry(BaseModel):
    id: str
    section: str
    text: str
    sha256: str | None  # None only while text is a TODO(lead) placeholder


class ClauseMap(BaseModel):
    code: str
    version: str
    source: ClauseSource
    normalisation: str
    clauses: list[ClauseEntry]


# Run configuration (configs/*.yaml) and run bookkeeping (logs/*). Not in the
# spec's schema block; added so the run script validates what it reads.


class ApiConfig(BaseModel):
    base_url_env: str
    api_key_env: str
    provider: str


class RunLimits(BaseModel):
    message_limit: int
    token_limit: int
    time_limit_s: int
    tool_timeout_s: int
    max_connections: int


class EpochsConfig(BaseModel):
    week1: int
    later: int


class ModelsConfig(BaseModel):
    api: ApiConfig
    dry_run: list[str]
    week1_targets: list[str]
    later_targets_add: list[str] = []
    grader: list[str]
    excluded: list[str]
    reasoning_check: list[str] = []
    run_limits: RunLimits
    epochs: EpochsConfig
    grader_samples: int


class ModelPrice(BaseModel):
    input: float | None  # USD per million tokens
    output: float | None
    cached_input: float | None = None


class PricesConfig(BaseModel):
    models: dict[str, ModelPrice]


class CostMix(BaseModel):
    input_share: float
    output_share: float


class BudgetConfig(BaseModel):
    total_cap_usd: float
    allocation_usd: dict[str, float]
    cost_at_limit_mix: CostMix


class LedgerEntry(BaseModel):
    ts: str
    kind: Literal["init", "batch"]
    phase: str | None = None
    model: str | None = None
    runs: int = 0
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0
    cumulative_usd: float
    log_path: str | None = None


class TokensPerRun(BaseModel):
    input: float
    cached_input: float
    output: float


class DryRunOk(BaseModel):
    ts: str
    runs: int
    harness_errors: int = Field(ge=0, le=0)
    detectors_ok: Literal[True]
    tokens_per_run: dict[str, TokensPerRun]  # by configured model name
    reasoning_visible: dict[str, bool]
