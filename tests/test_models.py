import pytest

from rc522_mfc.models import (
    CardInfo,
    KeyRecord,
    KeyType,
    RecoveryState,
    normalize_key,
    parse_known_key,
    parse_sector_expression,
)


def test_normalize_key() -> None:
    assert normalize_key("ff:ff:ff:ff:ff:ff") == "FFFFFFFFFFFF"


def test_invalid_key() -> None:
    with pytest.raises(ValueError):
        normalize_key("1234")


def test_parse_known_key() -> None:
    assert parse_known_key("4:b=ffffffffffff") == (4, KeyType.B, "FFFFFFFFFFFF")


def test_sector_expression() -> None:
    assert parse_sector_expression("0,4,7-9") == [0, 4, 7, 8, 9]


def test_unverified_keys_do_not_count_as_recovered() -> None:
    state = RecoveryState(schema_version=1, card=CardInfo(uid="DEADBEEF"))
    state.put(KeyRecord(0, KeyType.A, "FFFFFFFFFFFF", "verify", verified=False))

    assert state.get(0, KeyType.A) is not None
    assert state.get_verified(0, KeyType.A) is None
    assert state.unique_key_values() == []
    assert not state.has_key_for_every_sector()
    assert not state.complete()
