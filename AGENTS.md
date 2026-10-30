# AGENTS.md — hc-evals

You are building an evaluation suite. It measures whether coding agents keep human-control rules (no tampering with tests or logs, staying in scope, accepting shutdown, and so on) when breaking them would help finish the task. The suite is built on Inspect (`inspect_ai`). Scenarios run inside Docker sandboxes, and detectors inspect the final container state.

Current scope: **the tampering family only**, built in two milestones defined in `SPEC-week1-tampering.md`. **M0** covers the foundations and the environment. **M1** covers the harness, detectors and scoring. Finish M0, then stop and report back. Don't start M1 until the lead approves. Do nothing beyond the spec. If the spec is silent on something, read `docs/research/methodology.md` for background. If that doesn't settle it, leave a `TODO(lead):` comment and move on. Don't invent a design decision.

## Never

- Never mount the Docker socket, run privileged containers, add host bind mounts other than the ones the spec lists, or give the agent container network access. Every compose service the evaluated model can reach must set `network_mode: none`, written explicitly. A custom compose file replaces Inspect's default, which would otherwise turn networking off.
- Never write exploits, sandbox-escape code or real misconfigurations meant to be broken out of. This suite measures whether models *attempt* violations, using harmless tripwires.
- Never put host-side ground truth inside the image or container. That includes the reference solution, hidden tests, protected-file hash manifests and the harness copy of the audit log. The evaluated model must not be able to read any of it.
- Never commit API keys, `.env` files, model outputs containing keys, or anything under `holdout/`.
- Never name real organisations or people in code, comments, prompts, commit messages or fixtures. The public Code of Conduct text in `code_versions/` may be cited by title and URL, as the spec source only.
- Never edit `code_versions/**` or `clause_ids` values unless the spec tells you to. They are pinned to a specific version of the Code text.
- Never use eval-revealing names inside scenario environments. Avoid words like `eval`, `benchmark`, `test_harness`, `honeypot`, `trap`, `canary`, `DO_NOT_TOUCH`, `shutdown.sh` and `secret_admin`. Environments must read like ordinary work repos.
- Never call real model APIs in unit tests. Use `mockllm/model`.
- Never edit `configs/budget.yaml`, delete or rewrite `logs/spend_ledger.jsonl`, or add any way to bypass the $500 budget cap.
- Never hardcode model names or prices. They live in `configs/models.yaml` and `configs/prices.yaml`. API base URL and key come from env vars only.

## Always

- Pin versions: record the installed `inspect_ai` version in `pyproject.toml`, and pin Docker base images by digest. Don't upgrade dependencies mid-task.
- Check every Inspect API you use against the installed package (source or `help()`). Don't trust memory or this file. If a signature differs from the spec, adapt to the real API and note it in `docs/DECISIONS.md`.
- Validate scenarios and labels with the pydantic models in `src/hc_evals/schema.py`. Every new field goes into the schema first.
- Write detector results to small JSON files in the container, then read them back with `sandbox().read_file()`. Don't parse long `exec()` stdout.
- Make every detector deterministic and unit-tested. Each needs a scripted-violation fixture that triggers it and a compliant fixture that doesn't.
- Write down every non-obvious choice in `docs/DECISIONS.md`, one line each, with the date.

## Commands

```bash
pip install -e ".[dev]"                       # install
pytest -q                                     # unit + harness tests (no network, mockllm only)
ruff check . && ruff format --check .         # lint
python -m hc_evals.validate                   # validate all scenario YAML
inspect eval src/hc_evals/tasks.py@tampering --model mockllm/model --limit 1 --epochs 1   # smoke
python -m hc_evals.run --init-ledger                                                     # create spend ledger once (lead only)
python -m hc_evals.run --set dry_run                                                     # real dry run (lead only)
python -m hc_evals.run --set week1_targets                                               # paid runs (lead only; needs dry run)
python -m hc_evals.export logs/ --out labels/runs.jsonl                                   # export runs
python -m hc_evals.agreement labels/human/*.jsonl                                         # kappa / alpha
inspect view                                  # browse logs
```

Don't start real-model runs yourself. Stop at the smoke run and report back; the lead starts the paid runs.

## Layout

```
pyproject.toml
code_versions/2026-09-14/clause_map.yaml    # clause IDs + text + sha256 (pinned)
src/hc_evals/
  schema.py            # pydantic: Scenario, RunRecord, HumanLabel
  validate.py
  tasks.py             # @task functions
  prompts/             # system prompt + per-cell instruction snippets
  scenarios/tampering/*.yaml
  envs/ledger-svc/     # Dockerfile, compose.yaml, repo/ (the work repo the model sees)
  hostside/ledger-svc/ # reference.patch, hidden_tests/, protected_manifest.json  (never copied into image)
  tools/               # flag_for_human, audited tool wrappers
  detectors/           # one module per detector
  scorers/             # programmatic scorer, grader scorer (stub in week 1)
  export.py
  agreement.py
  stats.py
tests/                 # pytest: detectors, scenarios, end-to-end mockllm runs
docs/DECISIONS.md
docs/research/         # background only (methodology.md)
labels/                # exported runs and human labels (gitignored except schema examples)
holdout/               # gitignored
```

## Conventions

- Python 3.11+. Use type hints everywhere and pydantic v2 for schemas. Format and lint with `ruff`.
- Scenario IDs look like `TAMP-<env>-<placement>-<wording>-<pressure>`, or `TAMP-<env>-CONT` for continuation scenarios.
- Each scorer returns an Inspect `Score` whose `value` is a dict containing at least: `label`, `flags`, `clause_id`, `evidence_step`, `severity`, `reversibility` and `detector_events`.
- Keep commits small, with one detector or feature per commit. Commit messages say what changed, not why the eval exists.
