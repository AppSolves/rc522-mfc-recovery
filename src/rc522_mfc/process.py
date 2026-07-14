from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ProcessResult:
    returncode: int
    output: str


def run_streaming(
    command: Sequence[str],
    *,
    cwd: Path | None = None,
    on_line: Callable[[str], None] | None = None,
    log_path: Path | None = None,
    check: bool = False,
) -> ProcessResult:
    if log_path is not None:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        list(command),
        cwd=str(cwd) if cwd else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: list[str] = []
    log_handle = log_path.open("w", encoding="utf-8") if log_path else None
    try:
        assert process.stdout is not None
        for line in process.stdout:
            lines.append(line)
            if on_line:
                on_line(line.rstrip("\n"))
            if log_handle:
                log_handle.write(line)
                log_handle.flush()
    except KeyboardInterrupt:
        process.terminate()
        try:
            process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            process.kill()
        raise
    finally:
        if log_handle:
            log_handle.close()
    returncode = process.wait()
    result = ProcessResult(returncode=returncode, output="".join(lines))
    if check and returncode != 0:
        raise subprocess.CalledProcessError(returncode, command, output=result.output)
    return result
