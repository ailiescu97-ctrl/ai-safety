"""Generate the host-side ground-truth files for ledger-svc.

    python -m hc_evals.gen_hostside            # rebuild image, rewrite both files
    python -m hc_evals.gen_hostside --check    # exit 1 if either file is stale

protected_manifest.json is hashed inside a clean container built from the
compose file, so it reflects the image rather than the source tree.
expected_literals.json is read from the test sources with ``ast``.
"""

from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path

from hc_evals import protected

PKG = Path(__file__).parent
ENV_DIR = PKG / "envs" / "ledger-svc"
COMPOSE = ENV_DIR / "compose.yaml"
HOSTSIDE = PKG / "hostside" / "ledger-svc"
MANIFEST = HOSTSIDE / "protected_manifest.json"
LITERALS = HOSTSIDE / "expected_literals.json"
WORK_ROOT = "/work/ledger-svc"
VISIBLE_TEST = ENV_DIR / "repo" / "tests" / "test_money.py"
VISIBLE_TEST_NAME = "test_rounding_half_even"
HIDDEN_TEST = HOSTSIDE / "hidden_tests" / "test_rounding_hidden.py"


def compose(project: str, *args: str, stdin: bytes | None = None) -> subprocess.CompletedProcess:
    """Run ``docker compose -p <project> -f compose.yaml <args>``."""
    cmd = ["docker", "compose", "-p", project, "-f", str(COMPOSE), *args]
    return subprocess.run(cmd, input=stdin, capture_output=True, check=False)


def run_in_fresh_container(
    project: str, script: str, stdin: bytes | None = None
) -> subprocess.CompletedProcess:
    """Run ``bash -c script`` in a throwaway container of the default service."""
    return compose(project, "run", "--rm", "-T", "default", "bash", "-c", script, stdin=stdin)


def build_manifest(project: str = "hcevals-gen") -> dict:
    built = compose(project, "build", "--quiet")
    if built.returncode != 0:
        raise RuntimeError(built.stderr.decode())
    source = Path(protected.__file__).read_bytes()
    # -I and cd /: nothing from the repo or the environment loads at startup.
    res = run_in_fresh_container(project, f"cd / && python -I - {WORK_ROOT}", stdin=source)
    if res.returncode != 0:
        raise RuntimeError(res.stderr.decode())
    return {
        "generated_by": "python -m hc_evals.gen_hostside",
        "root": WORK_ROOT,
        "trees": list(protected.PROTECTED_TREES),
        "files_at_root": list(protected.PROTECTED_ROOT_FILES),
        "names_anywhere": list(protected.PROTECTED_NAMES),
        "suffixes_anywhere": list(protected.PROTECTED_SUFFIXES),
        "site_prefix": protected.SITE_PREFIX,
        "not_hashed": [protected.AUDIT_LOG],
        "ignored_dirs": sorted(protected.IGNORED_DIRS),
        "files": json.loads(res.stdout),
    }


def _decimal_literal(node: ast.expr) -> str | None:
    """Return "x" for ``Decimal("x")``, else None."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "Decimal"
        and len(node.args) == 1
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
    ):
        return node.args[0].value
    return None


def visible_literals() -> list[str]:
    tree = ast.parse(VISIBLE_TEST.read_text())
    fn = next(
        n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == VISIBLE_TEST_NAME
    )
    out = []
    for node in ast.walk(fn):
        if isinstance(node, ast.Compare):
            for comp in node.comparators:
                if (lit := _decimal_literal(comp)) is not None:
                    out.append(lit)
    return out


def hidden_literals() -> list[str]:
    tree = ast.parse(HIDDEN_TEST.read_text())
    cases = next(
        n.value
        for n in tree.body
        if isinstance(n, ast.Assign) and any(getattr(t, "id", "") == "CASES" for t in n.targets)
    )
    return [ast.literal_eval(case)[2] for case in cases.elts]  # type: ignore[attr-defined]


def build_literals() -> dict:
    return {
        "generated_by": "python -m hc_evals.gen_hostside",
        "visible": {f"tests/test_money.py::{VISIBLE_TEST_NAME}": visible_literals()},
        "hidden": {"hidden_tests/test_rounding_hidden.py": hidden_literals()},
    }


def _dump(data: dict) -> str:
    return json.dumps(data, indent=2) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="fail if files are stale")
    args = parser.parse_args()
    wanted = {MANIFEST: _dump(build_manifest()), LITERALS: _dump(build_literals())}
    stale = [p for p, text in wanted.items() if not p.exists() or p.read_text() != text]
    if args.check:
        for p in stale:
            print(f"stale: {p.relative_to(PKG)}", file=sys.stderr)
        return 1 if stale else 0
    for p, text in wanted.items():
        p.write_text(text)
        print(f"wrote {p.relative_to(PKG)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
