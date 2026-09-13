from pathlib import Path

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "python-lint-format.yml"


def test_lint_workflow_uses_frozen_project_toolchain():
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert "astral-sh/setup-uv@v5" in workflow
    assert "uv sync --frozen" in workflow
    assert "uv run black --check ." in workflow
    assert "uv run flake8" in workflow
    assert workflow.count("--exclude=.venv") == 2
    assert "pip install black flake8" not in workflow
