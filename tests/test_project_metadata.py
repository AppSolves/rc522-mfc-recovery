from __future__ import annotations

import tomllib
from pathlib import Path


def test_direct_runtime_imports_are_declared() -> None:
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = metadata["project"]["dependencies"]

    assert not any(dependency.startswith("click") for dependency in dependencies)
    assert any(dependency.startswith("typer") for dependency in dependencies)


def test_bootstrap_verifies_cli_import_path() -> None:
    bootstrap = Path("scripts/bootstrap.sh").read_text(encoding="utf-8")

    assert "import typer; import rc522_mfc.cli" in bootstrap
