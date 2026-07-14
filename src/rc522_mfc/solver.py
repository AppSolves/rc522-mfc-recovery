from __future__ import annotations

import platform
import re
from collections.abc import Callable
from pathlib import Path

from .models import normalize_key
from .process import run_streaming

KEY_PATTERN = re.compile(r"Key found:\s*([0-9A-Fa-f]{12})", re.IGNORECASE)


class HardnestedSolver:
    def __init__(self, pm3: Path, line_sink: Callable[[str], None] | None = None) -> None:
        self.pm3 = pm3
        self.line_sink = line_sink

    def solve(self, dataset: Path, *, log_path: Path) -> str:
        if not self.pm3.is_file():
            raise RuntimeError(f"patched Proxmark3 client not found: {self.pm3}")
        command_text = f'hf mf hardnested -r -f "{dataset}"'
        if platform.machine().lower() in {"aarch64", "arm64"}:
            command_text += " --ie"
        result = run_streaming(
            [str(self.pm3), "--offline", "-c", command_text],
            cwd=self.pm3.parent,
            on_line=self.line_sink,
            log_path=log_path,
        )
        matches = KEY_PATTERN.findall(result.output)
        if not matches:
            raise RuntimeError(f"Hardnested solver did not recover a key. See {log_path}")
        return normalize_key(matches[-1])
