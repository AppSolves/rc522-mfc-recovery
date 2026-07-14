from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib.resources import files
from pathlib import Path

from .formats import convert_rc522_to_pm3
from .models import CardInfo, KeyRecord, KeyType, NonceType, RecoveryState, normalize_key
from .native import NativeTool
from .paths import ToolPaths
from .solver import HardnestedSolver
from .state import StateStore


@dataclass(slots=True)
class RecoveryOptions:
    sectors: list[int]
    key_types: list[KeyType]
    known: list[tuple[int, KeyType, str]]
    dictionaries: list[Path]
    samples: int = 20_000
    force_nonce_type: NonceType | None = None
    fallback_hardnested: bool = True
    keep_traces: bool = True


class RecoveryWorkflow:
    def __init__(
        self,
        paths: ToolPaths,
        line_sink: Callable[[str], None] | None = None,
    ) -> None:
        self.paths = paths
        self.native = NativeTool(paths.native, line_sink=line_sink)
        self.solver = HardnestedSolver(paths.pm3, line_sink=line_sink)
        self.line_sink = line_sink

    def _say(self, text: str) -> None:
        if self.line_sink:
            self.line_sink(text)

    def identify(self) -> CardInfo:
        payload = self.native.identify()
        return CardInfo(
            uid=str(payload["uid"]).upper(),
            atqa=str(payload.get("atqa", "0400")),
            sak=str(payload.get("sak", "08")),
            card_type=str(payload.get("type", "MIFARE Classic 1K")),
            reader_version=str(payload.get("reader_version", "")) or None,
        )

    def classify_nonce(self, block: int = 0, samples: int = 128) -> NonceType:
        payload = self.native.nonce_probe(block=block, samples=samples)
        return NonceType(str(payload["classification"]))

    @staticmethod
    def _timestamp() -> str:
        return datetime.now(UTC).isoformat()

    def _save_record(
        self,
        state: RecoveryState,
        store: StateStore,
        record: KeyRecord,
    ) -> None:
        record.discovered_at = record.discovered_at or self._timestamp()
        state.put(record)
        store.save(state)

    def _verify_and_save(
        self,
        state: RecoveryState,
        store: StateStore,
        sector: int,
        key_type: KeyType,
        key: str,
        source: str,
    ) -> bool:
        key = normalize_key(key)
        if not self.native.authenticate(sector * 4, key_type, key, allow_failure=True):
            return False
        self._save_record(
            state,
            store,
            KeyRecord(
                sector=sector,
                key_type=key_type,
                value=key,
                source=source,
                verified=True,
            ),
        )
        return True

    def _load_dictionary_values(self, extra: Iterable[Path]) -> list[str]:
        values: set[str] = set()

        def add_lines(text: str) -> None:
            for line in text.splitlines():
                line = line.split("#", 1)[0].strip()
                if not line:
                    continue
                try:
                    values.add(normalize_key(line))
                except ValueError:
                    continue

        resource = files("rc522_mfc.data").joinpath("common.keys")
        add_lines(resource.read_text(encoding="utf-8"))
        for path in extra:
            if path.is_file():
                add_lines(path.read_text(encoding="utf-8"))
        return sorted(values)

    def _scan_values(
        self,
        state: RecoveryState,
        store: StateStore,
        values: Iterable[str],
        sectors: list[int],
        source: str,
    ) -> int:
        hits = self.native.keyscan(values, sectors, work_dir=store.card_dir / "tmp")
        added = 0
        for hit in hits:
            if state.get(hit.sector, hit.key_type) is None:
                if hit.source != "sector-trailer":
                    hit.source = source
                hit.discovered_at = self._timestamp()
                state.put(hit)
                added += 1
        if added:
            store.save(state)
        return added

    def _propagate(
        self,
        state: RecoveryState,
        store: StateStore,
        sectors: list[int],
    ) -> int:
        values = state.unique_key_values()
        if not values:
            return 0
        added = self._scan_values(state, store, values, sectors, "reused-key")
        if added:
            self._say(f"Key reuse discovered {added} additional sector key(s)")
        return added

    @staticmethod
    def _choose_source(state: RecoveryState, target_sector: int) -> KeyRecord:
        records = [record for record in state.all_records() if record.verified]
        if not records:
            raise RuntimeError("at least one verified key is required for nested recovery")
        different = [record for record in records if record.sector != target_sector]
        pool = different or records
        return min(
            pool,
            key=lambda record: (
                abs(record.sector - target_sector),
                record.sector,
                record.key_type.value,
            ),
        )

    @staticmethod
    def _read_metadata(path: Path) -> dict[str, str]:
        if not path.is_file():
            return {}
        values: dict[str, str] = {}
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key.strip()] = value.strip()
        return values

    def _trace_dataset_matches(
        self,
        *,
        raw: Path,
        meta: Path,
        uid: str,
        target_block: int,
        target_key_type: KeyType,
        samples: int,
    ) -> bool:
        if not raw.is_file() or raw.stat().st_size != samples * 5:
            return False
        metadata = self._read_metadata(meta)
        expected = {
            "format": "RC522-HARDNESTED-RECORDS-V1",
            "record_size": "5",
            "uid": uid,
            "target_block": str(target_block),
            "target_key_type": target_key_type.value,
            "records": str(samples),
        }
        return all(metadata.get(key) == value for key, value in expected.items())

    def _recover_hardnested(
        self,
        *,
        card: CardInfo,
        store: StateStore,
        source: KeyRecord,
        sector: int,
        key_type: KeyType,
        samples: int,
    ) -> str:
        target_block = sector * 4
        known_block = source.sector * 4 + 3
        target_dir = store.card_dir / "artifacts" / f"sector-{sector:02d}-{key_type.value}"
        target_dir.mkdir(parents=True, exist_ok=True)
        raw = target_dir / "rc522-nonces.bin"
        meta = target_dir / "rc522-nonces.meta"

        if self._trace_dataset_matches(
            raw=raw,
            meta=meta,
            uid=card.uid,
            target_block=target_block,
            target_key_type=key_type,
            samples=samples,
        ):
            self._say(f"Reusing complete trace dataset for sector {sector} Key {key_type.value}")
        else:
            raw.unlink(missing_ok=True)
            meta.unlink(missing_ok=True)
            self._say(f"Collecting Hardnested traces for sector {sector} Key {key_type.value}")
            self.native.collect_hardnested(
                known_block=known_block,
                known_key_type=source.key_type,
                known_key=source.value,
                target_block=target_block,
                target_key_type=key_type,
                samples=samples,
                output=raw,
                meta=meta,
                log_path=target_dir / "collect.log",
            )

        pm3_file = target_dir / "pm3-nonces.bin"
        conversion = convert_rc522_to_pm3(
            raw,
            pm3_file,
            uid=card.uid,
            target_block=target_block,
            target_key_type=key_type,
        )
        self._say(
            f"Converted {conversion.records} traces, first-byte coverage "
            f"{conversion.first_byte_coverage}/256, First_Byte_Sum "
            f"{conversion.first_byte_sum}"
        )
        return self.solver.solve(pm3_file, log_path=target_dir / "solve.log")

    def recover(self, options: RecoveryOptions) -> tuple[RecoveryState, StateStore]:
        card = self.identify()
        store = StateStore(self.paths.card_dir(card.uid))
        state = store.load_or_create(card)

        for sector, key_type, key in options.known:
            if not self._verify_and_save(state, store, sector, key_type, key, "provided"):
                raise RuntimeError(
                    f"provided key failed verification for sector {sector} Key {key_type.value}"
                )

        dictionary_values = self._load_dictionary_values(options.dictionaries)
        if dictionary_values:
            self._say(f"Scanning {len(dictionary_values)} common and user-provided keys")
            self._scan_values(state, store, dictionary_values, options.sectors, "dictionary")

        self._propagate(state, store, options.sectors)

        nonce_type = options.force_nonce_type or self.classify_nonce(block=0, samples=128)
        card.nonce_type = nonce_type
        state.card = card
        store.save(state)
        self._say(f"Nonce classification: {nonce_type.value}")

        missing_targets = any(
            state.get(sector, key_type) is None
            for sector in options.sectors
            for key_type in options.key_types
        )
        if missing_targets and not state.unique_key_values():
            raise RuntimeError(
                "no verified sector key is available for nested recovery; "
                "supply at least one --known key or a dictionary containing a valid key"
            )
        if nonce_type is NonceType.STATIC and missing_targets:
            raise RuntimeError(
                "static nonce cards are detected but not yet supported by this RC522 workflow; "
                "use a static-nested capable tool"
            )

        for sector in options.sectors:
            for key_type in options.key_types:
                if state.get(sector, key_type) is not None:
                    continue

                self._propagate(state, store, options.sectors)
                if state.get(sector, key_type) is not None:
                    continue

                source = self._choose_source(state, sector)
                target_block = sector * 4
                target_dir = store.card_dir / "artifacts" / f"sector-{sector:02d}-{key_type.value}"
                target_dir.mkdir(parents=True, exist_ok=True)
                candidate: str | None = None
                recovery_source = nonce_type.value

                if nonce_type is NonceType.WEAK:
                    self._say(f"Running weak Nested recovery for sector {sector} Key {key_type.value}")
                    candidate = self.native.weak_nested(
                        known_block=source.sector * 4 + 3,
                        known_key_type=source.key_type,
                        known_key=source.value,
                        target_block=target_block,
                        target_key_type=key_type,
                        log_path=target_dir / "weak-nested.log",
                    )
                    if candidate is not None:
                        if self._verify_and_save(
                            state,
                            store,
                            sector,
                            key_type,
                            candidate,
                            "weak-nested",
                        ):
                            self._say(f"Verified sector {sector} Key {key_type.value}: {candidate}")
                            self._propagate(state, store, options.sectors)
                            continue
                        self._say("Weak Nested produced an unverifiable candidate")
                        candidate = None

                should_use_hardnested = candidate is None and (
                    nonce_type is NonceType.HARD or options.fallback_hardnested
                )
                if should_use_hardnested:
                    recovery_source = "hardnested"
                    candidate = self._recover_hardnested(
                        card=card,
                        store=store,
                        source=source,
                        sector=sector,
                        key_type=key_type,
                        samples=options.samples,
                    )

                if candidate is None:
                    raise RuntimeError(f"failed to recover sector {sector} Key {key_type.value}")

                if not self._verify_and_save(
                    state,
                    store,
                    sector,
                    key_type,
                    candidate,
                    recovery_source,
                ):
                    raise RuntimeError(
                        f"solver candidate {candidate} failed direct RC522 verification "
                        f"for sector {sector} Key {key_type.value}"
                    )
                self._say(f"Verified sector {sector} Key {key_type.value}: {candidate}")
                self._propagate(state, store, options.sectors)

                if not options.keep_traces:
                    for path in target_dir.glob("*nonces.bin"):
                        path.unlink(missing_ok=True)

        return state, store
