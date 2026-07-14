from pathlib import Path

from rc522_mfc.models import CardInfo, KeyRecord, KeyType, RecoveryState
from rc522_mfc.paths import ToolPaths
from rc522_mfc.state import StateStore
from rc522_mfc.workflow import RecoveryWorkflow


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
