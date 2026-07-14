from pathlib import Path

from rc522_mfc.models import KeyType
from rc522_mfc.native import NativeTool
from rc522_mfc.process import ProcessResult


def test_nonce_probe_reports_progress(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "native"
    executable.write_text("", encoding="utf-8")

    lines = [
        "sampled 32/64 nonce-probe samples\n",
        "sampled 64/64 nonce-probe samples\n",
        'RC522_JSON:{"ok":true,"classification":"hard"}\n',
    ]

    def fake_run_streaming(*_args: object, **kwargs: object) -> ProcessResult:
        on_line = kwargs["on_line"]
        assert callable(on_line)
        for line in lines:
            on_line(line.rstrip("\n"))
        return ProcessResult(returncode=0, output="".join(lines))

    monkeypatch.setattr("rc522_mfc.native.run_streaming", fake_run_streaming)

    progress: list[tuple[int, int]] = []
    echoed: list[str] = []
    native = NativeTool(executable, line_sink=echoed.append)

    payload = native.nonce_probe(
        samples=64,
        progress_callback=lambda current, total: progress.append((current, total)),
    )

    assert payload["classification"] == "hard"
    assert progress == [(32, 64), (64, 64)]
    assert echoed[0] == "sampled 32/64 nonce-probe samples"


def test_collect_hardnested_reports_progress(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "native"
    executable.write_text("", encoding="utf-8")

    lines = [
        "collected 1000/2000 hardnested samples\n",
        "collected 2000/2000 hardnested samples\n",
        'RC522_JSON:{"ok":true,"records":2000,"output":"out.bin","meta":"out.meta"}\n',
    ]

    def fake_run_streaming(*_args: object, **kwargs: object) -> ProcessResult:
        on_line = kwargs["on_line"]
        assert callable(on_line)
        for line in lines:
            on_line(line.rstrip("\n"))
        return ProcessResult(returncode=0, output="".join(lines))

    monkeypatch.setattr("rc522_mfc.native.run_streaming", fake_run_streaming)

    progress: list[tuple[int, int]] = []
    native = NativeTool(executable)

    payload = native.collect_hardnested(
        known_block=7,
        known_key_type=KeyType.A,
        known_key="FFFFFFFFFFFF",
        target_block=0,
        target_key_type=KeyType.A,
        samples=2000,
        output=tmp_path / "out.bin",
        meta=tmp_path / "out.meta",
        log_path=tmp_path / "collect.log",
        progress_callback=lambda current, total: progress.append((current, total)),
    )

    assert payload["records"] == 2000
    assert progress == [(1000, 2000), (2000, 2000)]
