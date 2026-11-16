import pytest

from minicodex.guardrails import (
    GuardrailViolation,
    Sandbox,
    changed_files,
    diff_summary,
    snapshot,
)


@pytest.fixture
def sandbox(tmp_path):
    (tmp_path / "app.py").write_text("print('hi')\n")
    (tmp_path / ".env").write_text("API_KEY=fake\n")
    (tmp_path / "server.key").write_text("fake\n")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "config").write_text("fake\n")
    return Sandbox(tmp_path)


def test_normal_file_is_allowed(sandbox):
    assert sandbox.resolve("app.py").name == "app.py"


def test_path_escape_is_blocked(sandbox):
    with pytest.raises(GuardrailViolation, match="escapes"):
        sandbox.resolve("../outside.txt")
    with pytest.raises(GuardrailViolation, match="escapes"):
        sandbox.resolve("a/../../outside.txt")


def test_absolute_path_outside_is_blocked(sandbox):
    with pytest.raises(GuardrailViolation):
        sandbox.resolve("/etc/passwd")


def test_env_file_is_blocked(sandbox):
    with pytest.raises(GuardrailViolation, match="secret"):
        sandbox.resolve(".env")


def test_key_file_is_blocked(sandbox):
    with pytest.raises(GuardrailViolation, match="secret"):
        sandbox.resolve("server.key")


def test_git_dir_is_blocked(sandbox):
    with pytest.raises(GuardrailViolation, match="Blocked directory"):
        sandbox.resolve(".git/config")


def test_is_allowed_helper(sandbox):
    assert sandbox.is_allowed("app.py")
    assert not sandbox.is_allowed(".env")


def test_snapshot_and_diff(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    before = snapshot(tmp_path)
    (tmp_path / "a.py").write_text("x = 2\n")
    (tmp_path / "b.py").write_text("y = 3\n")
    after = snapshot(tmp_path)

    assert changed_files(before, after) == ["a.py", "b.py"]
    diff = diff_summary(before, after)
    assert "-x = 1" in diff and "+x = 2" in diff
    assert "b.py (new file)" in diff


def test_diff_summary_no_changes(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n")
    snap = snapshot(tmp_path)
    assert diff_summary(snap, snap) == "No files were changed."
