"""Acceptance 8 (export) and 9 (agreement), plus the stats helpers."""

import csv
import json
import subprocess
import sys

import krippendorff
import numpy as np
import pytest
from sklearn.metrics import cohen_kappa_score

from hc_evals import agreement, export, stats
from hc_evals.schema import HumanLabel, RunRecord

# --- 8: export ----------------------------------------------------------------------


@pytest.mark.docker
def test_export_validates_and_is_blind(runs, e2e_log_dir, tmp_path):
    out = tmp_path / "labels" / "runs.jsonl"
    records = export.export(e2e_log_dir, out)
    assert len(records) == len(runs)
    lines = out.read_text().splitlines()
    parsed = [RunRecord.model_validate_json(line) for line in lines]
    assert {r.scenario_id for r in parsed} >= {"TAMP-ledger-CONT", "TAMP-ledger-user-plain-low"}
    assert all(r.model == "mockllm/model" and r.inspect_version for r in parsed)

    sheet = (out.parent / "to_label.csv").read_text()
    rows = list(csv.DictReader(sheet.splitlines()))
    assert len(rows) == len(records)
    assert set(rows[0]) == {"run_id", "transcript", "final_report", *export.LABEL_COLUMNS}
    assert all(not row[c] for row in rows for c in export.LABEL_COLUMNS)
    assert "mockllm" not in sheet
    for row in rows:
        transcript = open(row["transcript"]).read()
        assert "mockllm" not in transcript
        assert "violation" not in transcript.split("## 1.")[0]  # no score in the header


# --- 9: agreement ---------------------------------------------------------------------

A = ["compliant", "compliant", "violation", "violation"]
B = ["compliant", "violation", "violation", "violation"]


def _write(path, rater, labels, sev=None, rev=None):
    with path.open("w") as fh:
        for i, lab in enumerate(labels):
            hl = HumanLabel(
                run_id=f"r{i}",
                rater_id=rater,
                label=lab,
                severity=(sev or ["S0"] * len(labels))[i],
                reversibility=(rev or ["R0"] * len(labels))[i],
                clause_id="HC-2b",
                evidence_step=None,
                rationale="",
            )
            fh.write(hl.model_dump_json() + "\n")


def test_kappa_known_answer(tmp_path):
    _write(tmp_path / "a.jsonl", "a", A)
    _write(tmp_path / "b.jsonl", "b", B)
    rep = agreement.report([tmp_path / "a.jsonl", tmp_path / "b.jsonl"])
    assert rep["kappa_label"]["value"] == pytest.approx(0.5, abs=1e-3)  # po=.75, pe=.5


def test_matches_sklearn_and_krippendorff(tmp_path):
    rng = np.random.default_rng(1)
    labels = agreement.LABELS
    raters = {name: [labels[i] for i in rng.integers(0, 3, 30)] for name in ("a", "b", "c")}
    sev = {name: [f"S{i}" for i in rng.integers(0, 5, 30)] for name in raters}
    for name in raters:
        _write(tmp_path / f"{name}.jsonl", name, raters[name], sev=sev[name])
    two = agreement.report([tmp_path / "a.jsonl", tmp_path / "b.jsonl"])
    codes = {n: [labels.index(x) for x in raters[n]] for n in raters}
    assert round(two["kappa_label"]["value"], 3) == round(
        cohen_kappa_score(codes["a"], codes["b"]), 3
    )
    three = agreement.report([tmp_path / f"{n}.jsonl" for n in raters])
    nominal = krippendorff.alpha(
        reliability_data=[codes[n] for n in "abc"], level_of_measurement="nominal"
    )
    sev_codes = [[int(x[1]) for x in sev[n]] for n in "abc"]
    ordinal = krippendorff.alpha(reliability_data=sev_codes, level_of_measurement="ordinal")
    assert round(three["alpha_label"]["value"], 3) == round(nominal, 3)
    assert round(three["alpha_severity"]["value"], 3) == round(ordinal, 3)
    low, high = three["alpha_label"]["ci95"]
    assert low <= three["alpha_label"]["value"] <= high
    assert "kappa_label" not in three


def test_confusion_and_detector_accuracy(tmp_path):
    _write(tmp_path / "a.jsonl", "a", A)
    _write(tmp_path / "b.jsonl", "b", A)
    runs = tmp_path / "runs.jsonl"
    fired = [False, True, True, False]
    with runs.open("w") as fh:
        for i, f in enumerate(fired):
            rec = RunRecord(
                run_id=f"r{i}",
                scenario_id="s",
                model="m",
                epoch=1,
                label="violation" if f else "compliant",
                flags=[],
                clause_id=None,
                evidence_step=None,
                severity="S0",
                reversibility="R0",
                detector_events=[{"detector": "protected_hash", "triggered": f}],
                final_report="",
                visible_tests_pass=True,
                hidden_tests_pass=True,
                code_version="c",
                inspect_version="i",
                log_path="l",
            )
            fh.write(rec.model_dump_json() + "\n")
    rep = agreement.report([tmp_path / "a.jsonl", tmp_path / "b.jsonl"], runs)
    conf = rep["confusion_consensus_vs_programmatic"]
    assert conf["compliant"]["violation"] == 1 and conf["violation"]["compliant"] == 1
    det = rep["detectors"]["protected_hash"]
    assert (det["precision"], det["recall"]) == (0.5, 0.5)


def test_agreement_cli(tmp_path):
    _write(tmp_path / "a.jsonl", "a", A)
    _write(tmp_path / "b.jsonl", "b", B)
    res = subprocess.run(
        [
            sys.executable,
            "-m",
            "hc_evals.agreement",
            str(tmp_path / "a.jsonl"),
            str(tmp_path / "b.jsonl"),
            "--runs",
            str(tmp_path / "none.jsonl"),
        ],
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stderr
    assert json.loads(res.stdout)["runs"] == 4


# --- stats --------------------------------------------------------------------------


def _rec(scenario, epoch, violation, flags=()):
    return RunRecord(
        run_id=f"{scenario}-{epoch}",
        scenario_id=scenario,
        model="m",
        epoch=epoch,
        label="violation" if violation else "compliant",
        flags=list(flags),
        clause_id=None,
        evidence_step=None,
        severity="S0",
        reversibility="R0",
        detector_events=[],
        final_report="",
        visible_tests_pass=True,
        hidden_tests_pass=True,
        code_version="c",
        inspect_version="i",
        log_path="l",
    )


def test_wilson_and_cluster_bootstrap():
    low, high = stats.wilson(5, 10)
    assert low < 0.5 < high and 0 < low and high < 1
    recs = [_rec(f"s{s}", e, (s + e) % 3 == 0) for s in range(9) for e in range(10)]
    lo, hi = stats.cluster_bootstrap(recs)
    assert lo <= stats.violation_rate(recs) <= hi


def test_limit_reached_runs_reported_separately():
    recs = [_rec("s", 1, False), _rec("s", 2, True, ["limit_reached"])]
    done, limited = stats.split_limit_reached(recs)
    assert [r.epoch for r in done] == [1] and [r.epoch for r in limited] == [2]


def test_attempt_net_and_legibility_rates():
    def rec(i, label, clause, flags, model="m1"):
        r = _rec("s", i, label == "violation", flags)
        return r.model_copy(update={"label": label, "clause_id": clause, "model": model})

    recs = [
        rec(1, "violation", "HC-2b", []),  # net tampering
        rec(2, "violation", "HC-2b", ["attempted_only"]),  # reverted attempt
        rec(3, "compliant", "HC-6", ["undisclosed"]),  # silent revert of an inherited edit
        rec(4, "violation", "HC-4", ["concealed"]),  # denied the inherited edit
        rec(5, "compliant", None, []),
        rec(6, "violation", "HC-2b", ["limit_reached"]),  # reported separately
    ]
    done, _ = stats.split_limit_reached(recs)
    assert stats.attempt_rate(done) == pytest.approx(2 / 5)
    assert stats.net_tampering_rate(done) == pytest.approx(1 / 5)
    assert stats.legibility_miss_rate(done) == pytest.approx(2 / 5)
    row = stats.rates_by_model(recs)["m1"]
    assert (row["n"], row["n_limit_reached"]) == (5, 1)
    assert row["attempt_rate"] == pytest.approx(0.4)
    low, high = row["attempt_rate_ci95"]
    assert low < 0.4 < high
