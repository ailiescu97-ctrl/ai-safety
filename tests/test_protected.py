"""The protected-path hasher used to build protected_manifest.json."""

import pytest

from hc_evals.protected import SITE_PREFIX, hash_protected, hash_site_dirs


def _repo(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")
    (tmp_path / "pytest.ini").write_text("[pytest]\n")
    (tmp_path / "pyproject.toml").write_text('[project]\nname = "x"\n')
    (tmp_path / "pkg").mkdir()
    (tmp_path / "pkg" / "mod.py").write_text("X = 1\n")
    return tmp_path


def test_hashes_protected_files_only(tmp_path):
    repo = _repo(tmp_path)
    (repo / "README.md").write_text("hello\n")
    assert set(hash_protected(str(repo))) == {
        "tests/test_a.py",
        ".github/workflows/ci.yml",
        "pytest.ini",
        "pyproject.toml",
    }


def test_bytecode_caches_ignored(tmp_path):
    repo = _repo(tmp_path)
    before = hash_protected(str(repo))
    (repo / "tests" / "__pycache__").mkdir()
    (repo / "tests" / "__pycache__" / "test_a.cpython-311.pyc").write_bytes(b"\0")
    assert hash_protected(str(repo)) == before


def test_editing_a_test_changes_its_hash(tmp_path):
    repo = _repo(tmp_path)
    before = hash_protected(str(repo))
    (repo / "tests" / "test_a.py").write_text("def test_a():\n    pass\n")
    assert hash_protected(str(repo))["tests/test_a.py"] != before["tests/test_a.py"]


def test_whole_pyproject_is_hashed(tmp_path):
    repo = _repo(tmp_path)
    before = hash_protected(str(repo))["pyproject.toml"]
    (repo / "pyproject.toml").write_text('[project]\nname = "x"\nversion = "2"\n')
    assert hash_protected(str(repo))["pyproject.toml"] != before


@pytest.mark.parametrize(
    "rel",
    [
        "setup.cfg",
        "tox.ini",
        "conftest.py",
        "pkg/conftest.py",
        "sitecustomize.py",
        "pkg/usercustomize.py",
        "pkg/hook.pth",
    ],
)
def test_new_config_or_startup_file_is_an_addition(tmp_path, rel):
    repo = _repo(tmp_path)
    before = hash_protected(str(repo))
    (repo / rel).write_text("")
    after = hash_protected(str(repo))
    assert set(after) - set(before) == {rel}


def test_site_dir_entries_hashed(tmp_path):
    site_dir = tmp_path / "site-packages"
    (site_dir / "pkg").mkdir(parents=True)
    (site_dir / "pkg" / "__init__.py").write_text("")
    before = hash_site_dirs([str(site_dir), str(tmp_path / "missing")])
    assert set(before) == {f"{SITE_PREFIX}{site_dir}/pkg"}
    (site_dir / "pkg" / "__init__.py").write_text("import os\n")
    (site_dir / "evil.pth").write_text("import os\n")
    after = hash_site_dirs([str(site_dir)])
    assert after[f"{SITE_PREFIX}{site_dir}/pkg"] != before[f"{SITE_PREFIX}{site_dir}/pkg"]
    assert f"{SITE_PREFIX}{site_dir}/evil.pth" in after
