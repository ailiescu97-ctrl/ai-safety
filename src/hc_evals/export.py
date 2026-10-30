"""Export .eval logs to RunRecord JSONL and a blind labelling sheet (SPEC §8).

    python -m hc_evals.export logs/ --out labels/runs.jsonl

Writes, next to --out:
- runs.jsonl: one RunRecord per run.
- to_label.csv: run_id, transcript path, final report and empty label columns.
  No model name and no programmatic label, so raters stay blind.
- transcripts/<run_id>.md: the conversation without model names or scores.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from pathlib import Path

from inspect_ai.log import EvalLog, EvalSample, list_eval_logs, read_eval_log
from inspect_ai.model import ChatMessage, ContentReasoning, ContentText

from hc_evals.schema import DetectorEvent, RunRecord

SCORER = "programmatic"
LABEL_COLUMNS = ["label", "severity", "reversibility", "clause_id", "evidence_step", "rationale"]


def run_id(log: EvalLog, sample: EvalSample, epoch: int) -> str:
    key = f"{log.eval.eval_id}:{sample.id}:{epoch}"
    return "run-" + hashlib.sha256(key.encode()).hexdigest()[:16]


def sample_epoch(log: EvalLog, sample: EvalSample) -> int:
    """Batched runs carry their real epoch in the eval metadata."""
    return int((log.eval.metadata or {}).get("batch_epoch", sample.epoch))


def to_record(log: EvalLog, sample: EvalSample, log_path: str) -> RunRecord:
    epoch = sample_epoch(log, sample)
    md = sample.metadata or {}
    meta = log.eval.metadata or {}
    score = (sample.scores or {}).get(SCORER)
    base = {
        "run_id": run_id(log, sample, epoch),
        "scenario_id": md.get("scenario_id", str(sample.id)),
        "model": log.eval.model,
        "epoch": epoch,
        "code_version": md.get("code_version", ""),
        "inspect_version": log.eval.packages.get("inspect_ai", ""),
        "log_path": log_path,
        "model_name": meta.get("model_name"),
        "model_version": sample.output.model if sample.output else None,
    }
    if score is None:  # the sample errored before scoring
        return RunRecord(
            **base,
            label="ambiguous",
            flags=["harness_error"],
            clause_id=None,
            evidence_step=None,
            severity="S0",
            reversibility="R0",
            detector_events=[],
            final_report="",
            visible_tests_pass=False,
            hidden_tests_pass=False,
        )
    v = score.value
    return RunRecord(
        **base,
        label=v["label"],
        flags=score.metadata["flags"],
        clause_id=v["clause_id"],
        evidence_step=v["evidence_step"],
        severity=v["severity"],
        reversibility=v["reversibility"],
        detector_events=[
            DetectorEvent.model_validate(e) for e in score.metadata["detector_events"]
        ],
        final_report=score.answer or "",
        continuation_bucket=v.get("continuation_bucket"),
        visible_tests_pass=bool(v["visible_tests_pass"]),
        hidden_tests_pass=bool(v["hidden_tests_pass"]),
    )


def _text(message: ChatMessage) -> str:
    if isinstance(message.content, str):
        return message.content
    parts = []
    for c in message.content:
        if isinstance(c, ContentText):
            parts.append(c.text)
        elif isinstance(c, ContentReasoning) and c.reasoning:
            parts.append(f"[reasoning]\n{c.reasoning}")
    return "\n\n".join(parts)


def transcript(sample: EvalSample) -> str:
    """Markdown transcript with no model name, scores or metadata."""
    lines = [f"# Run transcript: {sample.metadata.get('scenario_id', sample.id)}", ""]
    for i, m in enumerate(sample.messages, start=1):
        lines.append(f"## {i}. {m.role}")
        if m.role == "tool":
            lines.append(f"(result of `{m.function}`)")
        if text := _text(m):
            lines += ["", "```", text, "```"]
        for tc in getattr(m, "tool_calls", None) or []:
            lines += [
                "",
                f"call `{tc.function}`:",
                "```json",
                json.dumps(tc.arguments, indent=2),
                "```",
            ]
        lines.append("")
    return "\n".join(lines)


def export(log_dir: Path, out: Path) -> list[RunRecord]:
    out.parent.mkdir(parents=True, exist_ok=True)
    tdir = out.parent / "transcripts"
    tdir.mkdir(exist_ok=True)
    records: list[RunRecord] = []
    rows: list[dict] = []
    for info in list_eval_logs(str(log_dir), recursive=True):
        log = read_eval_log(info)
        for sample in log.samples or []:
            rec = to_record(log, sample, info.name)
            records.append(rec)
            tpath = tdir / f"{rec.run_id}.md"
            tpath.write_text(transcript(sample), encoding="utf-8")
            rows.append(
                {
                    "run_id": rec.run_id,
                    "transcript": str(tpath),
                    "final_report": rec.final_report,
                    **{c: "" for c in LABEL_COLUMNS},
                }
            )
    with out.open("w", encoding="utf-8") as fh:
        for rec in records:
            fh.write(rec.model_dump_json() + "\n")
    with (out.parent / "to_label.csv").open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(
            fh, fieldnames=["run_id", "transcript", "final_report", *LABEL_COLUMNS]
        )
        writer.writeheader()
        writer.writerows(rows)
    return records


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("log_dir", type=Path)
    parser.add_argument("--out", type=Path, default=Path("labels/runs.jsonl"))
    args = parser.parse_args(argv)
    records = export(args.log_dir, args.out)
    print(f"exported {len(records)} runs to {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
