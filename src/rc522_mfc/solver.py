from __future__ import annotations

import os
import platform
import re
from collections.abc import Callable
from pathlib import Path

from .models import normalize_key
from .process import run_streaming

KEY_PATTERN = re.compile(r"Key found:\s*([0-9A-Fa-f]{12})", re.IGNORECASE)
OFFLINE_PATCH_MARKERS = (
    "(g_session.pm3_present == false) && (tests == false) && (nonce_file_read == false)",
    "if (nonce_file_read && fnlen == 0)",
    "if (nonce_file_write && fnlen == 0)",
)


class HardnestedSolver:
    def __init__(self, pm3: Path, line_sink: Callable[[str], None] | None = None) -> None:
        self.pm3 = pm3
        self.line_sink = line_sink

    def ensure_ready(self) -> None:
        if not self.pm3.is_file():
            raise RuntimeError(f"patched Proxmark3 client not found: {self.pm3}")
        if os.name != "nt" and not os.access(self.pm3, os.X_OK):
            raise RuntimeError(f"patched Proxmark3 client is not executable: {self.pm3}")

        development_client = self._development_client()
        if development_client is not None:
            if not self._is_executable_file(development_client):
                raise RuntimeError(
                    "patched Proxmark3 launcher exists but the compiled client executable is missing: "
                    f"{development_client}\n"
                    "Run `rc522-mfc setup --force` or `./scripts/build-proxmark.sh --force` "
                    "to rebuild the offline solver."
                )
            self._ensure_offline_patch_present()
            self._ensure_development_client_current(development_client)

    def solve(self, dataset: Path, *, log_path: Path) -> str:
        self.ensure_ready()
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
            tail = self._tail_output(result.output)
            detail = f" Last output: {tail}" if tail else ""
            if "No device connected" in result.output:
                raise RuntimeError(
                    "Hardnested solver refused offline nonce-file mode because the compiled "
                    "Proxmark3 client is missing this project's offline Hardnested patch, "
                    "or it was compiled before the patch was applied. "
                    "Run `rc522-mfc setup --force` or `./scripts/build-proxmark.sh --force`. "
                    f"See {log_path}.{detail}"
                )
            if result.returncode != 0:
                raise RuntimeError(
                    f"Hardnested solver failed with exit code {result.returncode}. See {log_path}.{detail}"
                )
            raise RuntimeError(f"Hardnested solver did not recover a key. See {log_path}.{detail}")
        return normalize_key(matches[-1])

    def _development_client(self) -> Path | None:
        root = self.pm3.parent
        if self.pm3.name != "pm3" or not (root / "client").is_dir():
            return None
        if not (root / "Makefile").is_file() and not (root / ".git").is_dir():
            return None
        return root / "client" / ("proxmark3.exe" if os.name == "nt" else "proxmark3")

    def _ensure_offline_patch_present(self) -> None:
        source = self._offline_patch_source()
        if not source.is_file():
            return
        text = source.read_text(encoding="utf-8", errors="replace")
        if all(marker in text for marker in OFFLINE_PATCH_MARKERS):
            return
        raise RuntimeError(
            "patched Proxmark3 client source is missing this project's offline Hardnested patch: "
            f"{source}\n"
            "Run `rc522-mfc setup --force` or `./scripts/build-proxmark.sh --force` "
            "to refetch, patch, and rebuild the offline solver."
        )

    def _ensure_development_client_current(self, development_client: Path) -> None:
        source = self._offline_patch_source()
        if not source.is_file():
            return
        if development_client.stat().st_mtime >= source.stat().st_mtime:
            return
        raise RuntimeError(
            "patched Proxmark3 client executable is older than the patched Hardnested source: "
            f"{development_client}\n"
            "Run `rc522-mfc setup --force` or `./scripts/build-proxmark.sh --force` "
            "to rebuild the offline solver."
        )

    def _offline_patch_source(self) -> Path:
        return self.pm3.parent / "client" / "src" / "cmdhfmf.c"

    @staticmethod
    def _is_executable_file(path: Path) -> bool:
        if not path.is_file():
            return False
        return os.name == "nt" or os.access(path, os.X_OK)

    @staticmethod
    def _tail_output(output: str, *, limit: int = 240) -> str:
        tail = " ".join(line.strip() for line in output.splitlines() if line.strip())
        if len(tail) <= limit:
            return tail
        return f"...{tail[-limit:]}"
