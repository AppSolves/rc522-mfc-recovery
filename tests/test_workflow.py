from pathlib import Path

from rc522_mfc.models import CardInfo, KeyRecord, KeyType, NonceType, RecoveryState
from rc522_mfc.paths import ToolPaths
from rc522_mfc.state import StateStore
from rc522_mfc.workflow import RecoveryOptions, RecoveryWorkflow


class FakeNative:
    def keyscan(
        self,
        keys: list[str],
        sectors: list[int],
        *,
        work_dir: Path,
    ) -> list[KeyRecord]:
        assert keys == ["FFFFFFFFFFFF"]
        assert sectors == [4, 5]
        assert work_dir.name == "tmp"
        return [
            KeyRecord(
                sector=5,
                key_type=KeyType.A,
                value="FFFFFFFFFFFF",
                source="fake",
            )
        ]


class RecoverNative:
    def __init__(self) -> None:
        self.keyscan_calls: list[list[str]] = []

    def identify(self) -> dict[str, str]:
        return {"uid": "DEADBEEF", "type": "MIFARE Classic 1K"}

    def authenticate(
        self,
        _block: int,
        _key_type: KeyType,
        _key: str,
        *,
        allow_failure: bool = False,
    ) -> bool:
        return True

    def keyscan(
        self,
        keys: list[str],
        _sectors: list[int],
        *,
        work_dir: Path,
    ) -> list[KeyRecord]:
        assert work_dir.name == "tmp"
        self.keyscan_calls.append(list(keys))
        return []

    def weak_nested(
        self,
        *,
        known_block: int,
        known_key_type: KeyType,
        known_key: str,
        target_block: int,
        target_key_type: KeyType,
        log_path: Path,
    ) -> str:
        assert known_block == 7
        assert known_key_type is KeyType.A
        assert known_key == "FFFFFFFFFFFF"
        assert target_block == 0
        assert target_key_type is KeyType.A
        assert log_path.name == "weak-nested.log"
        return "A0A1A2A3A4A5"


def make_workflow(tmp_path: Path) -> RecoveryWorkflow:
    paths = ToolPaths(
        native=tmp_path / "native",
        pm3=tmp_path / "pm3",
        data_root=tmp_path / "data",
        cache_root=tmp_path / "cache",
    )
    return RecoveryWorkflow(paths)


def test_propagate_reused_key(tmp_path: Path) -> None:
    workflow = make_workflow(tmp_path)
    workflow.native = FakeNative()  # type: ignore[assignment]
    store = StateStore(tmp_path / "card")
    state = RecoveryState(schema_version=1, card=CardInfo(uid="DEADBEEF"))
    state.put(KeyRecord(4, KeyType.A, "FFFFFFFFFFFF", "provided"))

    assert workflow._propagate(state, store, [4, 5]) == 1
    recovered = state.get(5, KeyType.A)
    assert recovered is not None
    assert recovered.value == "FFFFFFFFFFFF"
    assert recovered.source == "reused-key"
    assert store.load().get(5, KeyType.A) is not None


def test_trace_dataset_metadata_validation(tmp_path: Path) -> None:
    workflow = make_workflow(tmp_path)
    raw = tmp_path / "records.bin"
    meta = tmp_path / "records.meta"
    raw.write_bytes(bytes(100))
    meta.write_text(
        "\n".join(
            [
                "format=RC522-HARDNESTED-RECORDS-V1",
                "record_size=5",
                "uid=DEADBEEF",
                "target_block=20",
                "target_key_type=A",
                "records=20",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    assert workflow._trace_dataset_matches(
        raw=raw,
        meta=meta,
        uid="DEADBEEF",
        target_block=20,
        target_key_type=KeyType.A,
        samples=20,
    )
    assert not workflow._trace_dataset_matches(
        raw=raw,
        meta=meta,
        uid="DEADBEEF",
        target_block=24,
        target_key_type=KeyType.A,
        samples=20,
    )


def test_skip_dictionary_bypasses_dictionary_scan(tmp_path: Path) -> None:
    workflow = make_workflow(tmp_path)
    native = RecoverNative()
    workflow.native = native  # type: ignore[assignment]
    workflow._load_dictionary_values = lambda _extra: ["ABCDEF123456"]  # type: ignore[method-assign]

    state, _store = workflow.recover(
        RecoveryOptions(
            sectors=[0],
            key_types=[KeyType.A],
            known=[(1, KeyType.A, "FFFFFFFFFFFF")],
            dictionaries=[],
            force_nonce_type=NonceType.WEAK,
            skip_dictionary=True,
        )
    )

    assert state.get(0, KeyType.A) is not None
    assert ["ABCDEF123456"] not in native.keyscan_calls


def test_recover_scans_dictionary_by_default(tmp_path: Path) -> None:
    workflow = make_workflow(tmp_path)
    native = RecoverNative()
    workflow.native = native  # type: ignore[assignment]
    workflow._load_dictionary_values = lambda _extra: ["ABCDEF123456"]  # type: ignore[method-assign]

    workflow.recover(
        RecoveryOptions(
            sectors=[0],
            key_types=[KeyType.A],
            known=[(1, KeyType.A, "FFFFFFFFFFFF")],
            dictionaries=[],
            force_nonce_type=NonceType.WEAK,
        )
    )

    assert ["ABCDEF123456"] in native.keyscan_calls
