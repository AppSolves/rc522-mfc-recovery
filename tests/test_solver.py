from __future__ import annotations

import os
from pathlib import Path

import pytest

from rc522_mfc.process import ProcessResult
from rc522_mfc.solver import OFFLINE_PATCH_MARKERS, HardnestedSolver


def _make_executable(path: Path) -> None:
    path.write_text("#!/bin/sh\n", encoding="utf-8")
    path.chmod(0o755)


def _write_cmdhfmf_source(checkout: Path, *, patched: bool) -> None:
    source = checkout / "client" / "src" / "cmdhfmf.c"
    source.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(OFFLINE_PATCH_MARKERS) if patched else 'PrintAndLogEx(INFO, "No device connected");'
    source.write_text(text + "\n", encoding="utf-8")


def test_solver_rejects_uncompiled_proxmark_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "proxmark3"
    (checkout / "client").mkdir(parents=True)
    (checkout / "Makefile").write_text("", encoding="utf-8")
    _write_cmdhfmf_source(checkout, patched=True)
    pm3 = checkout / "pm3"
    _make_executable(pm3)

    with pytest.raises(RuntimeError, match="compiled client executable is missing"):
        HardnestedSolver(pm3).ensure_ready()


def test_solver_accepts_compiled_proxmark_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "proxmark3"
    (checkout / "client").mkdir(parents=True)
    (checkout / "Makefile").write_text("", encoding="utf-8")
    _write_cmdhfmf_source(checkout, patched=True)
    pm3 = checkout / "pm3"
    _make_executable(pm3)
    client_name = "proxmark3.exe" if os.name == "nt" else "proxmark3"
    _make_executable(checkout / "client" / client_name)

    HardnestedSolver(pm3).ensure_ready()


def test_solver_rejects_unpatched_proxmark_checkout(tmp_path: Path) -> None:
    checkout = tmp_path / "proxmark3"
    (checkout / "client").mkdir(parents=True)
    (checkout / "Makefile").write_text("", encoding="utf-8")
    _write_cmdhfmf_source(checkout, patched=False)
    pm3 = checkout / "pm3"
    _make_executable(pm3)
    client_name = "proxmark3.exe" if os.name == "nt" else "proxmark3"
    _make_executable(checkout / "client" / client_name)

    with pytest.raises(RuntimeError, match="offline Hardnested patch"):
        HardnestedSolver(pm3).ensure_ready()


def test_solver_rejects_stale_compiled_proxmark_client(tmp_path: Path) -> None:
    checkout = tmp_path / "proxmark3"
    (checkout / "client").mkdir(parents=True)
    (checkout / "Makefile").write_text("", encoding="utf-8")
    _write_cmdhfmf_source(checkout, patched=True)
    pm3 = checkout / "pm3"
    _make_executable(pm3)
    client_name = "proxmark3.exe" if os.name == "nt" else "proxmark3"
    client = checkout / "client" / client_name
    _make_executable(client)
    source = checkout / "client" / "src" / "cmdhfmf.c"
    source_time = client.stat().st_mtime + 10
    os.utime(source, (source_time, source_time))

    with pytest.raises(RuntimeError, match="older than the patched Hardnested source"):
        HardnestedSolver(pm3).ensure_ready()


def test_solver_failure_includes_last_output(monkeypatch, tmp_path: Path) -> None:
    pm3 = tmp_path / "custom-pm3"
    _make_executable(pm3)
    dataset = tmp_path / "nonces.bin"
    dataset.write_bytes(b"")

    def fake_run_streaming(*_args: object, **_kwargs: object) -> ProcessResult:
        return ProcessResult(
            returncode=1,
            output="[!!] In devel workdir but no executable found, did you compile it?\n",
        )

    monkeypatch.setattr("rc522_mfc.solver.run_streaming", fake_run_streaming)

    with pytest.raises(RuntimeError) as error:
        HardnestedSolver(pm3).solve(dataset, log_path=tmp_path / "solve.log")

    message = str(error.value)
    assert "Hardnested solver failed with exit code 1" in message
    assert "no executable found" in message


def test_solver_no_device_error_points_to_offline_patch(monkeypatch, tmp_path: Path) -> None:
    pm3 = tmp_path / "custom-pm3"
    _make_executable(pm3)
    dataset = tmp_path / "nonces.bin"
    dataset.write_bytes(b"")

    def fake_run_streaming(*_args: object, **_kwargs: object) -> ProcessResult:
        return ProcessResult(
            returncode=235,
            output="[offline|script] pm3 --> hf mf hardnested -r -f nonces.bin\n[=] No device connected\n",
        )

    monkeypatch.setattr("rc522_mfc.solver.run_streaming", fake_run_streaming)

    with pytest.raises(RuntimeError) as error:
        HardnestedSolver(pm3).solve(dataset, log_path=tmp_path / "solve.log")

    message = str(error.value)
    assert "missing this project's offline Hardnested patch" in message
    assert "setup --force" in message
