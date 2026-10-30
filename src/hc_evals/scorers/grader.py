"""LLM grader (week 2). Week 1: interface only, never called from the task."""

from __future__ import annotations

from pathlib import Path

from inspect_ai.model import ChatMessage

from hc_evals.schema import DetectorEvent


async def grade(
    trajectory: list[ChatMessage],
    detector_events: list[DetectorEvent],
    rubric_path: Path,
) -> dict | None:
    """Grade one run against a clause rubric.

    Will return a dict with at least label, severity, reversibility, clause_id,
    evidence_step and rationale, from the median of the grader samples set in
    configs/models.yaml (grader_samples). Week 1 returns None.
    """
    # TODO: call the grader model from configs/models.yaml (grader:) with the
    # rubric, the trajectory and the detector events; parse and vote.
    return None
