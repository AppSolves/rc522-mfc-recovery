from pathlib import Path

from rc522_mfc.exporters import export_csv, export_mct_keys
from rc522_mfc.models import CardInfo, KeyRecord, KeyType, RecoveryState


def test_unique_key_export(tmp_path: Path) -> None:
    state = RecoveryState(schema_version=1, card=CardInfo(uid="DEADBEEF"))
    state.put(KeyRecord(0, KeyType.A, "FFFFFFFFFFFF", "test"))
    state.put(KeyRecord(1, KeyType.B, "FFFFFFFFFFFF", "test"))
    output = tmp_path / "card.keys"
    export_mct_keys(state, output)
    assert output.read_text() == "FFFFFFFFFFFF\n"


def test_exports_skip_unverified_keys(tmp_path: Path) -> None:
    state = RecoveryState(schema_version=1, card=CardInfo(uid="DEADBEEF"))
    state.put(KeyRecord(0, KeyType.A, "FFFFFFFFFFFF", "test", verified=False))
    state.put(KeyRecord(0, KeyType.B, "A0A1A2A3A4A5", "test"))

    keys_output = tmp_path / "card.keys"
    csv_output = tmp_path / "card.csv"
    export_mct_keys(state, keys_output)
    export_csv(state, csv_output)

    assert keys_output.read_text() == "A0A1A2A3A4A5\n"
    assert "FFFFFFFFFFFF" not in csv_output.read_text(encoding="utf-8")
