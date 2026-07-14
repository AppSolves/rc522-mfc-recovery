from pathlib import Path

from rc522_mfc.models import CardInfo, KeyRecord, KeyType
from rc522_mfc.state import StateStore


def test_state_round_trip(tmp_path: Path) -> None:
    store = StateStore(tmp_path / "card")
    state = store.load_or_create(CardInfo(uid="DEADBEEF"))
    state.put(KeyRecord(0, KeyType.A, "FFFFFFFFFFFF", "test"))
    store.save(state)
    loaded = store.load()
    assert loaded.card.uid == "DEADBEEF"
    assert loaded.get(0, KeyType.A).value == "FFFFFFFFFFFF"
