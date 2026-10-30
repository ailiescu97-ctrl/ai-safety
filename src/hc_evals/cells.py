"""Combine the per-factor instruction snippets in prompts/cells.yaml."""

from __future__ import annotations

from functools import cache
from pathlib import Path
from typing import Any

import yaml

from hc_evals.schema import Placement, Pressure, Wording

CELLS_PATH = Path(__file__).parent / "prompts" / "cells.yaml"
SEPARATOR = "\n\n"


@cache
def load_cells(path: Path = CELLS_PATH) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def user_message(
    placement: Placement, wording: Wording, pressure: Pressure, escalation_path: bool
) -> str:
    """Task text, then the wording (user_turn only), pressure and escalation lines."""
    cells = load_cells()
    parts = [cells["task"]]
    if cells["placement"][placement] == "user":
        parts.append(cells["wording"][wording])
    parts.append(cells["pressure"][pressure])
    parts.append(cells["escalation"][escalation_path])
    return SEPARATOR.join(p for p in parts if p)


def system_suffix(placement: Placement, wording: Wording) -> str | None:
    """Wording text to append to the system prompt, or None for user_turn cells."""
    cells = load_cells()
    if cells["placement"][placement] == "system":
        return cells["wording"][wording]
    return None
