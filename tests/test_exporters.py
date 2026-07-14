from pathlib import Path

from rc522_mfc.exporters import export_mct_keys
from rc522_mfc.models import CardInfo, KeyRecord, KeyType, RecoveryState


def test_unique_key_export(tmp_path: Path) -> None:
    state = RecoveryState(schema_version=1, card=CardInfo(uid="DEADBEEF"))
    state.put(KeyRecord(0, KeyType.A, "FFFFFFFFFFFF", "test"))
    state.put(KeyRecord(1, KeyType.B, "FFFFFFFFFFFF", "test"))
    output = tmp_path / "card.keys"
    export_mct_keys(state, output)
    assert output.read_text() == "FFFFFFFFFFFF\n"
