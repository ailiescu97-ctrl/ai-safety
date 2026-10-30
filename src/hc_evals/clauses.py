"""Clause-map loading, text normalisation and the code_version string."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from pathlib import Path

import yaml

from hc_evals.schema import ClauseMap

REPO_ROOT = Path(__file__).resolve().parents[2]
CODE_DATE = "2026-09-14"
CLAUSE_MAP_PATH = REPO_ROOT / "code_versions" / CODE_DATE / "clause_map.yaml"
TODO_PREFIX = "TODO(lead)"


def normalise(text: str) -> str:
    """NFC, collapse every whitespace run to one space, strip the ends."""
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def text_sha256(text: str) -> str:
    return hashlib.sha256(normalise(text).encode("utf-8")).hexdigest()


def load_clause_map(path: Path = CLAUSE_MAP_PATH) -> ClauseMap:
    return ClauseMap.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def code_version(path: Path = CLAUSE_MAP_PATH) -> str:
    """``HAI-CoC-<date>#<sha256 of the clause_map.yaml bytes>``."""
    cmap = load_clause_map(path)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"{cmap.code}-{cmap.version}#{digest}"
