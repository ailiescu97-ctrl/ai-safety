import shutil
import subprocess
import uuid

import pytest

from hc_evals import gen_hostside


@pytest.fixture(scope="session")
def compose_project():
    """Build the ledger-svc image once per session under a throwaway project name."""
    if shutil.which("docker") is None:
        pytest.fail("docker CLI not found; the environment tests need Docker")
    if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
        pytest.fail("Docker daemon not reachable; start Docker and re-run")
    project = f"hcevals-test-{uuid.uuid4().hex[:8]}"
    built = gen_hostside.compose(project, "build", "--quiet")
    assert built.returncode == 0, built.stderr.decode()
    yield project
    gen_hostside.compose(project, "down", "--rmi", "local", "--remove-orphans")


@pytest.fixture(scope="session")
def e2e_log_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("e2e-logs")


@pytest.fixture(scope="session")
def runs(e2e_log_dir, compose_project):
    """Every scripted run in tests.scripted.SCRIPTS, run once per session."""
    from tests.scripted import SCRIPTS, run_scripted

    return {name: run_scripted(sc, outs, e2e_log_dir) for name, (sc, outs) in SCRIPTS.items()}
