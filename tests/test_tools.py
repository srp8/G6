import pytest

from minicodex.guardrails import GuardrailViolation, Sandbox
from minicodex.tools import ToolBox


@pytest.fixture
def toolbox(tmp_path):
    (tmp_path / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    tests = tmp_path / "tests"
    tests.mkdir()
    (tmp_path / "conftest.py").write_text("")
    (tests / "test_calc.py").write_text(
        "from calc import add\n\ndef test_add():\n    assert add(1, 2) == 3\n"
    )
    (tmp_path / ".env").write_text("SECRET=fake\n")
    return ToolBox(Sandbox(tmp_path))


def test_list_files_hides_secrets(toolbox):
    files = toolbox.list_files()
    assert "calc.py" in files
    assert "tests/test_calc.py" in files
    assert ".env" not in files


def test_read_file(toolbox):
    assert "def add" in toolbox.read_file("calc.py")


def test_read_secret_blocked(toolbox):
    with pytest.raises(GuardrailViolation):
        toolbox.read_file(".env")


def test_write_file_roundtrip(toolbox):
    toolbox.write_file("newmod.py", "VALUE = 42\n")
    assert toolbox.read_file("newmod.py") == "VALUE = 42\n"


def test_write_secret_blocked(toolbox):
    with pytest.raises(GuardrailViolation):
        toolbox.write_file(".env", "SECRET=stolen\n")


def test_write_outside_sandbox_blocked(toolbox):
    with pytest.raises(GuardrailViolation):
        toolbox.write_file("../evil.py", "boom\n")


def test_search(toolbox):
    hits = toolbox.search("return a + b")
    assert any(hit.startswith("calc.py:2") for hit in hits)


def test_run_tests_passing(toolbox):
    result = toolbox.run_tests()
    assert result.passed
    assert "1 passed" in result.output


def test_run_tests_failing(toolbox):
    toolbox.write_file("calc.py", "def add(a, b):\n    return a - b\n")
    result = toolbox.run_tests()
    assert not result.passed
    assert "failed" in result.output.lower()
