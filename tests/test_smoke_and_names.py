"""Acceptance 10 (CLI smoke) and A3 (no model names outside the config)."""

import re
import subprocess
import sys
from pathlib import Path

import pytest
from inspect_ai.log import read_eval_log

from hc_evals.clauses import REPO_ROOT
from hc_evals.config import load_models


@pytest.mark.docker
def test_smoke_cli(tmp_path, compose_project):
    inspect_bin = Path(sys.executable).parent / "inspect"
    res = subprocess.run(
        [
            str(inspect_bin),
            "eval",
            "src/hc_evals/tasks.py@tampering",
            "--model",
            "mockllm/model",
            "--limit",
            "1",
            "--epochs",
            "1",
            "--log-dir",
            str(tmp_path),
            "--display",
            "plain",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        timeout=600,
    )
    assert res.returncode == 0, res.stdout[-2000:] + res.stderr[-2000:]
    (log_file,) = tmp_path.glob("*.eval")
    log = read_eval_log(str(log_file))
    assert log.status == "success" and log.error is None
    assert all(s.error is None for s in log.samples)


def _model_names() -> set[str]:
    cfg = load_models()
    names = set(cfg.dry_run + cfg.week1_targets + cfg.later_targets_add + cfg.grader + cfg.excluded)
    # names that appear only in comments of models.yaml
    text = (REPO_ROOT / "configs" / "models.yaml").read_text()
    names |= set(re.findall(r"#.*?\b((?:claude|gpt|gemini|grok|kimi|glm)-[\w.-]+)", text))
    return names


def test_no_model_names_in_src():
    names = _model_names()
    assert "gpt-6.1-sol" in names and "claude-haiku-5-5" in names
    hits = []
    for path in (REPO_ROOT / "src").rglob("*"):
        if path.is_file() and path.suffix in {".py", ".md", ".yaml", ".yml", ".json", ".toml"}:
            text = path.read_text(encoding="utf-8", errors="replace")
            hits += [f"{path.relative_to(REPO_ROOT)}: {n}" for n in names if n in text]
    assert hits == []
