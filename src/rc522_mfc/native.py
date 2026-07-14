from __future__ import annotations

import json
import tempfile
from collections.abc import Callable, Iterable
from pathlib import Path
from typing import Any

from .models import KeyRecord, KeyType, normalize_key
from .process import run_streaming

JSON_PREFIX = "RC522_JSON:"
JsonObject = dict[str, Any]


class NativeTool:
    def __init__(
        self,
        executable: Path,
        line_sink: Callable[[str], None] | None = None,
    ) -> None:
        self.executable = executable
        self.line_sink = line_sink

    def _run(
        self,
        args: list[str],
        *,
        log_path: Path | None = None,
        allow_failure: bool = False,
    ) -> JsonObject:
        if not self.executable.is_file():
            raise RuntimeError(f"native helper not found: {self.executable}")
        result = run_streaming(
            [str(self.executable), *args],
            on_line=self.line_sink,
            log_path=log_path,
        )
        payload: JsonObject | None = None
        for line in result.output.splitlines():
            if line.startswith(JSON_PREFIX):
                decoded = json.loads(line[len(JSON_PREFIX) :])
                if not isinstance(decoded, dict):
                    raise RuntimeError("native helper returned an invalid JSON payload")
                payload = decoded
        if payload is None:
            raise RuntimeError("native helper returned no machine-readable result")
        if (result.returncode != 0 or not payload.get("ok", False)) and not allow_failure:
            fallback = f"native helper failed with exit code {result.returncode}"
            raise RuntimeError(str(payload.get("error", fallback)))
        return payload

    def reader_version(self) -> JsonObject:
        return self._run(["reader-version"])

    def identify(self) -> JsonObject:
        return self._run(["identify"])

    def authenticate(
        self,
        block: int,
        key_type: KeyType,
        key: str,
        *,
        allow_failure: bool = False,
    ) -> bool:
        payload = self._run(
            [
                "auth",
                "--block",
                str(block),
                "--key-type",
                key_type.value,
                "--key",
                normalize_key(key),
            ],
            allow_failure=allow_failure,
        )
        return bool(payload.get("authenticated", False))

    def keyscan(
        self,
        keys: Iterable[str],
        sectors: list[int],
        *,
        work_dir: Path,
    ) -> list[KeyRecord]:
        values = sorted({normalize_key(value) for value in keys})
        if not values:
            return []
        work_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=work_dir,
            suffix=".keys",
            delete=False,
        ) as handle:
            handle.write("\n".join(values) + "\n")
            key_file = Path(handle.name)
        try:
            sector_expression = ",".join(str(value) for value in sectors)
            payload = self._run(["keyscan", "--keys", str(key_file), "--sectors", sector_expression])
        finally:
            key_file.unlink(missing_ok=True)

        hits = payload.get("hits", [])
        if not isinstance(hits, list):
            raise RuntimeError("native keyscan returned an invalid hit list")
        records: list[KeyRecord] = []
        for raw_hit in hits:
            if not isinstance(raw_hit, dict):
                continue
            records.append(
                KeyRecord(
                    sector=int(raw_hit["sector"]),
                    key_type=KeyType(str(raw_hit["key_type"])),
                    value=str(raw_hit["key"]),
                    source=(
                        "sector-trailer"
                        if raw_hit.get("method") == "sector-trailer"
                        else "dictionary-or-reuse"
                    ),
                    verified=True,
                )
            )
        return records

    def nonce_probe(self, block: int = 0, samples: int = 128) -> JsonObject:
        return self._run(["nonce-probe", "--block", str(block), "--samples", str(samples)])

    def weak_nested(
        self,
        *,
        known_block: int,
        known_key_type: KeyType,
        known_key: str,
        target_block: int,
        target_key_type: KeyType,
        log_path: Path,
    ) -> str | None:
        payload = self._run(
            [
                "weak-nested",
                "--known-block",
                str(known_block),
                "--known-key-type",
                known_key_type.value,
                "--known-key",
                normalize_key(known_key),
                "--target-block",
                str(target_block),
                "--target-key-type",
                target_key_type.value,
            ],
            log_path=log_path,
            allow_failure=True,
        )
        return normalize_key(str(payload["key"])) if payload.get("recovered") else None

    def collect_hardnested(
        self,
        *,
        known_block: int,
        known_key_type: KeyType,
        known_key: str,
        target_block: int,
        target_key_type: KeyType,
        samples: int,
        output: Path,
        meta: Path,
        log_path: Path,
    ) -> JsonObject:
        output.parent.mkdir(parents=True, exist_ok=True)
        return self._run(
            [
                "collect-hardnested",
                "--known-block",
                str(known_block),
                "--known-key-type",
                known_key_type.value,
                "--known-key",
                normalize_key(known_key),
                "--target-block",
                str(target_block),
                "--target-key-type",
                target_key_type.value,
                "--samples",
                str(samples),
                "--output",
                str(output),
                "--meta",
                str(meta),
            ],
            log_path=log_path,
        )

    def dump(
        self,
        key_records: Iterable[KeyRecord],
        output: Path,
        *,
        work_dir: Path,
    ) -> None:
        work_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w",
            encoding="utf-8",
            dir=work_dir,
            suffix=".keymap",
            delete=False,
        ) as handle:
            for record in key_records:
                handle.write(f"{record.sector},{record.key_type.value},{record.value}\n")
            key_map = Path(handle.name)
        try:
            self._run(["dump", "--key-map", str(key_map), "--output", str(output)])
        finally:
            key_map.unlink(missing_ok=True)
