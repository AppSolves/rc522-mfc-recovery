from pathlib import Path

from rc522_mfc.models import KeyType
from rc522_mfc.native import NativeProgress, NativeTool
from rc522_mfc.process import ProcessResult


def _mock_native_output(monkeypatch, lines: list[str]) -> None:
    def fake_run_streaming(*_args: object, **kwargs: object) -> ProcessResult:
        on_line = kwargs["on_line"]
        assert callable(on_line)
        for line in lines:
            on_line(line.rstrip("\n"))
        return ProcessResult(returncode=0, output="".join(lines))

    monkeypatch.setattr("rc522_mfc.native.run_streaming", fake_run_streaming)


def test_nonce_probe_reports_structured_progress(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "native"
    executable.write_text("", encoding="utf-8")
    _mock_native_output(
        monkeypatch,
        [
            'RC522_PROGRESS:{"operation":"nonce-probe","completed":0,"total":64,'
            '"attempts":0,"max_attempts":256,"consecutive_failures":0}\n',
            "reader still sampling\n",
            'RC522_PROGRESS:{"operation":"nonce-probe","completed":64,"total":64,'
            '"attempts":80,"max_attempts":256,"consecutive_failures":0}\n',
            'RC522_JSON:{"ok":true,"classification":"hard"}\n',
        ],
    )

    progress: list[NativeProgress] = []
    echoed: list[str] = []
    native = NativeTool(executable, line_sink=echoed.append)

    payload = native.nonce_probe(samples=64, progress_callback=progress.append)

    assert payload["classification"] == "hard"
    assert [(item.completed, item.total) for item in progress] == [(0, 64), (64, 64)]
    assert progress[-1].attempts == 80
    assert progress[-1].max_attempts == 256
    assert echoed == ["reader still sampling"]


def test_collect_hardnested_reports_attempts_and_stalls(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "native"
    executable.write_text("", encoding="utf-8")
    _mock_native_output(
        monkeypatch,
        [
            'RC522_PROGRESS:{"operation":"hardnested","completed":1000,"total":2000,'
            '"attempts":1300,"max_attempts":20000,"consecutive_failures":4}\n',
            'RC522_PROGRESS:{"operation":"hardnested","completed":2000,"total":2000,'
            '"attempts":2600,"max_attempts":20000,"consecutive_failures":0}\n',
            'RC522_JSON:{"ok":true,"records":2000,"output":"out.bin","meta":"out.meta"}\n',
        ],
    )

    progress: list[NativeProgress] = []
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
        progress_callback=progress.append,
    )

    assert payload["records"] == 2000
    assert [(item.completed, item.total) for item in progress] == [(1000, 2000), (2000, 2000)]
    assert progress[0].attempts == 1300
    assert progress[0].consecutive_failures == 4


def test_keyscan_reports_sector_key_progress(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "native"
    executable.write_text("", encoding="utf-8")
    _mock_native_output(
        monkeypatch,
        [
            'RC522_PROGRESS:{"operation":"keyscan","completed":0,"total":4507,"sector":3,"key_type":"A"}\n',
            'RC522_PROGRESS:{"operation":"keyscan","completed":256,"total":4507,"sector":3,"key_type":"A"}\n',
            'RC522_JSON:{"ok":true,"hits":[]}\n',
        ],
    )

    progress: list[NativeProgress] = []
    echoed: list[str] = []
    native = NativeTool(executable, line_sink=echoed.append)

    payload = native.keyscan(
        ["FFFFFFFFFFFF"],
        [3],
        work_dir=tmp_path,
        progress_callback=progress.append,
    )

    assert payload == []
    assert [(item.completed, item.total, item.sector, item.key_type) for item in progress] == [
        (0, 4507, 3, KeyType.A),
        (256, 4507, 3, KeyType.A),
    ]
    assert echoed == []


def test_malformed_structured_progress_is_suppressed(monkeypatch, tmp_path: Path) -> None:
    executable = tmp_path / "native"
    executable.write_text("", encoding="utf-8")
    _mock_native_output(
        monkeypatch,
        [
            "RC522_PROGRESS:{not-json}\n",
            "human status\n",
            'RC522_JSON:{"ok":true,"classification":"hard"}\n',
        ],
    )

    progress: list[NativeProgress] = []
    echoed: list[str] = []
    native = NativeTool(executable, line_sink=echoed.append)

    native.nonce_probe(samples=64, progress_callback=progress.append)

    assert progress == []
    assert echoed == ["human status"]
