from __future__ import annotations

import tomllib
from pathlib import Path


def test_direct_runtime_imports_are_declared() -> None:
    metadata = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    dependencies = metadata["project"]["dependencies"]

    assert any(dependency.startswith("click") for dependency in dependencies)
