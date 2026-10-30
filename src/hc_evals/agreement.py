"""Inter-rater agreement and detector accuracy (SPEC §8).

    python -m hc_evals.agreement labels/human/*.jsonl [--runs labels/runs.jsonl]

Each input file holds HumanLabel lines. Runs labelled by every rater are compared.
The confusion matrix and detector accuracy need the exported runs (default
labels/runs.jsonl, used when it exists).
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from pathlib import Path

import krippendorff
import numpy as np
from sklearn.metrics import cohen_kappa_score

from hc_evals.schema import HumanLabel, RunRecord

LABELS = ["compliant", "violation", "ambiguous"]
SEVERITY = ["S0", "S1", "S2", "S3", "S4"]
REVERS = ["R0", "R1", "R2", "R3"]
N_BOOT = 2000
DEFAULT_RUNS = Path("labels/runs.jsonl")
SEED = 0


def load_labels(paths: Sequence[Path]) -> dict[str, dict[str, HumanLabel]]:
    """rater_id -> run_id -> label."""
    raters: dict[str, dict[str, HumanLabel]] = {}
    for path in paths:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                lab = HumanLabel.model_validate_json(line)
                raters.setdefault(lab.rater_id, {})[lab.run_id] = lab
    return raters


def common_runs(raters: dict[str, dict[str, HumanLabel]]) -> list[str]:
    sets = [set(r) for r in raters.values()]
    return sorted(set.intersection(*sets)) if sets else []


def matrix(raters, runs, field: str, scale: list[str]) -> np.ndarray:
    """raters x runs codes, as krippendorff expects."""
    return np.array(
        [[scale.index(getattr(raters[r][run], field)) for run in runs] for r in sorted(raters)],
        dtype=float,
    )


def kappa(m: np.ndarray) -> float:
    return float(cohen_kappa_score(m[0], m[1]))


def alpha(m: np.ndarray, level: str) -> float:
    if len(np.unique(m)) < 2:
        return float("nan")  # no variation: alpha undefined
    return float(krippendorff.alpha(reliability_data=m, level_of_measurement=level))


def bootstrap_ci(m: np.ndarray, stat: Callable[[np.ndarray], float]) -> tuple[float, float]:
    rng = np.random.default_rng(SEED)
    n = m.shape[1]
    vals = []
    for _ in range(N_BOOT):
        v = stat(m[:, rng.integers(0, n, size=n)])
        if not np.isnan(v):
            vals.append(v)
    if not vals:
        return float("nan"), float("nan")
    low, high = np.percentile(vals, [2.5, 97.5])
    return float(low), float(high)


def consensus(raters, runs) -> dict[str, str | None]:
    """Majority label per run; ties give None."""
    out: dict[str, str | None] = {}
    for run in runs:
        counts = Counter(raters[r][run].label for r in raters).most_common()
        tie = len(counts) > 1 and counts[0][1] == counts[1][1]
        out[run] = None if tie else counts[0][0]
    return out


def confusion(cons: dict[str, str | None], programmatic: dict[str, str]) -> dict:
    table = {c: {p: 0 for p in LABELS} for c in LABELS}
    for run, c in cons.items():
        if c is not None and run in programmatic:
            table[c][programmatic[run]] += 1
    return table


def detector_accuracy(cons: dict[str, str | None], records: dict[str, RunRecord]) -> dict:
    """Precision/recall of each detector's trigger against consensus 'violation'."""
    names = sorted({e.detector for r in records.values() for e in r.detector_events})
    out = {}
    for name in names:
        tp = fp = fn = 0
        for run, c in cons.items():
            if c is None or run not in records:
                continue
            fired = any(e.detector == name and e.triggered for e in records[run].detector_events)
            actual = c == "violation"
            tp += fired and actual
            fp += fired and not actual
            fn += actual and not fired
        out[name] = {
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
            "tp": tp,
            "fp": fp,
            "fn": fn,
        }
    return out


def report(paths: Sequence[Path], runs_path: Path | None = None) -> dict:
    raters = load_labels(paths)
    if len(raters) < 2:
        raise SystemExit("need labels from at least two raters")
    runs = common_runs(raters)
    if not runs:
        raise SystemExit("no run was labelled by every rater")
    lab = matrix(raters, runs, "label", LABELS)
    sev = matrix(raters, runs, "severity", SEVERITY)
    rev = matrix(raters, runs, "reversibility", REVERS)
    out: dict = {"raters": sorted(raters), "runs": len(runs)}
    if len(raters) == 2:
        out["kappa_label"] = {"value": kappa(lab), "ci95": bootstrap_ci(lab, kappa)}
    for name, m, level in (
        ("label", lab, "nominal"),
        ("severity", sev, "ordinal"),
        ("reversibility", rev, "ordinal"),
    ):
        out[f"alpha_{name}"] = {
            "value": alpha(m, level),
            "ci95": bootstrap_ci(m, lambda x, lv=level: alpha(x, lv)),
        }
    cons = consensus(raters, runs)
    out["consensus_ties"] = sum(v is None for v in cons.values())
    if runs_path is not None:
        records = {
            r.run_id: r
            for r in (
                RunRecord.model_validate_json(line)
                for line in runs_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            )
        }
        out["confusion_consensus_vs_programmatic"] = confusion(
            cons, {k: r.label for k, r in records.items()}
        )
        out["detectors"] = detector_accuracy(cons, records)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("labels", nargs="+", type=Path)
    parser.add_argument("--runs", type=Path, default=DEFAULT_RUNS, help="exported RunRecords")
    args = parser.parse_args(argv)
    runs = args.runs if args.runs.exists() else None
    print(json.dumps(report(args.labels, runs), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
