"""Recreate the project's git history inside the image.

Usage: python build_history.py <history_dir> <final_tree_dir> <target_dir>

Each entry in commits.json is either a commit or a merge:

- commit: writes the listed ``files``, taking each from
  ``snapshots/<snapshot>/<path>`` when the entry names a snapshot and that file
  exists there, otherwise from the final tree. With ``branch``, the commit goes
  on that branch (created from main the first time it is named).
- merge: ``{"merge": <branch>, ...}`` merges the branch into main with --no-ff,
  as a pull-request merge would, then deletes the branch.

A top-level ``head`` names the branch left checked out at the end; it may stay
unmerged, like a teammate's pushed repro. The checked-out tree must match the
final tree exactly.
"""

import filecmp
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


def git(target: Path, *args: str, env: dict[str, str] | None = None) -> str:
    return subprocess.run(
        ["git", *args], cwd=target, check=True, env=env, capture_output=True, text=True
    ).stdout


def identity(spec: dict, entry: dict) -> dict[str, str]:
    name, email = spec["authors"][entry["author"]]
    c_name, c_email = spec["authors"][entry.get("committer", entry["author"])]
    return {
        **os.environ,
        "GIT_AUTHOR_NAME": name,
        "GIT_AUTHOR_EMAIL": email,
        "GIT_AUTHOR_DATE": entry["date"],
        "GIT_COMMITTER_NAME": c_name,
        "GIT_COMMITTER_EMAIL": c_email,
        "GIT_COMMITTER_DATE": entry["date"],
    }


def main() -> None:
    history, final, target = (Path(a) for a in sys.argv[1:4])
    spec = json.loads((history / "commits.json").read_text())
    git(target, "init", "-q", "-b", "main")
    branches: set[str] = set()
    for entry in spec["commits"]:
        env = identity(spec, entry)
        if "merge" in entry:
            branch = entry["merge"]
            git(target, "checkout", "-q", "main")
            git(target, "merge", "-q", "--no-ff", branch, "-m", entry["message"], env=env)
            git(target, "branch", "-q", "-d", branch)
            branches.discard(branch)
            continue
        branch = entry.get("branch", "main")
        current = git(target, "symbolic-ref", "--short", "HEAD").strip()
        if branch != "main" and branch not in branches:
            git(target, "checkout", "-q", "-b", branch, "main")
            branches.add(branch)
        elif branch != current:
            git(target, "checkout", "-q", branch)
        for rel in entry["files"]:
            snap = history / "snapshots" / entry.get("snapshot", "-") / rel
            src = snap if snap.exists() else final / rel
            dst = target / rel
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, dst)
        git(target, "add", "-A")
        git(target, "commit", "-q", "-m", entry["message"], env=env)
    head = spec.get("head", "main")
    if branches - {head}:
        sys.exit(f"unmerged branches: {sorted(branches - {head})}")
    git(target, "checkout", "-q", head)

    final_files = {p.relative_to(final) for p in final.rglob("*") if p.is_file()}
    tracked = {Path(p) for p in git(target, "ls-files").split()}
    if tracked != final_files:
        sys.exit(f"tree mismatch: {sorted(tracked ^ final_files)}")
    for rel in final_files:
        if not filecmp.cmp(final / rel, target / rel, shallow=False):
            sys.exit(f"content mismatch: {rel}")


if __name__ == "__main__":
    main()
