"""Run a detector script in the container and read its JSON result back."""

from __future__ import annotations

import json

from inspect_ai.util import sandbox

# Prepended to every Python detector script. Results go to /tmp/det_<id>.json,
# written fresh (any file or symlink already there is removed first, and the
# new file is opened with O_EXCL | O_NOFOLLOW).
PRELUDE = """
import json as _json, os as _os

def safe_write(path, obj):
    try:
        _os.unlink(path)
    except FileNotFoundError:
        pass
    fd = _os.open(path, _os.O_WRONLY | _os.O_CREAT | _os.O_EXCL | _os.O_NOFOLLOW, 0o644)
    with _os.fdopen(fd, "w") as fh:
        _json.dump(obj, fh)
"""


class DetectorError(RuntimeError):
    """A detector could not run or produced no result (a harness error)."""


def result_path(det_id: str) -> str:
    return f"/tmp/det_{det_id}.json"


async def read_result(det_id: str) -> dict:
    try:
        return json.loads(await sandbox().read_file(result_path(det_id)))
    except Exception as exc:  # missing file, bad JSON, dead container
        raise DetectorError(f"{det_id}: no result ({exc})") from exc


async def run_python(det_id: str, source: str, args: list[str], stdin: bytes | str | None = None):
    """Run ``source`` as root with ``python -I`` from /, then read its result."""
    # A __future__ import must come first, so drop it rather than prepend before it;
    # the container's Python 3.11 evaluates these annotations fine without it.
    body = source.replace("from __future__ import annotations\n", "")
    script = PRELUDE + body
    res = await sandbox().exec(
        ["python", "-I", "-c", script, *args], input=stdin, cwd="/", user="root", timeout=300
    )
    if not res.success:
        raise DetectorError(f"{det_id}: exit {res.returncode}: {res.stderr.strip()[-500:]}")
    return await read_result(det_id)
