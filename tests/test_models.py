import pytest

from rc522_mfc.models import KeyType, normalize_key, parse_known_key, parse_sector_expression


def test_normalize_key() -> None:
    assert normalize_key("ff:ff:ff:ff:ff:ff") == "FFFFFFFFFFFF"


def test_invalid_key() -> None:
    with pytest.raises(ValueError):
        normalize_key("1234")


def test_parse_known_key() -> None:
    assert parse_known_key("4:b=ffffffffffff") == (4, KeyType.B, "FFFFFFFFFFFF")


def test_sector_expression() -> None:
    assert parse_sector_expression("0,4,7-9") == [0, 4, 7, 8, 9]
