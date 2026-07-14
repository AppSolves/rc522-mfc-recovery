from pathlib import Path

from rc522_mfc.formats import convert_rc522_to_pm3, reverse_parity_nibble
from rc522_mfc.models import KeyType


def test_reverse_parity_nibble() -> None:
    assert reverse_parity_nibble(0b0001) == 0b1000
    assert reverse_parity_nibble(0b1010) == 0b0101


def test_conversion(tmp_path: Path) -> None:
    raw = bytes.fromhex("1122334401 AABBCCDD08")
    source = tmp_path / "raw.bin"
    output = tmp_path / "pm3.bin"
    source.write_bytes(raw)
    result = convert_rc522_to_pm3(
        source,
        output,
        uid="DEADBEEF",
        target_block=20,
        target_key_type=KeyType.A,
    )
    data = output.read_bytes()
    assert data[:6] == bytes.fromhex("DEADBEEF1400")
    assert data[6:10] == bytes.fromhex("11223344")
    assert data[10:14] == bytes.fromhex("AABBCCDD")
    assert data[14] == 0x81
    assert result.records == 2
    assert result.pairs == 1


def test_conversion_rejects_invalid_full_coverage_sum(tmp_path: Path) -> None:
    records = bytearray()
    # With all PM3 first-byte parity bits clear, encrypted first-byte parity
    # produces a deliberately invalid full-coverage sum after toggling a subset
    # of byte-0 parity bits.
    for first in range(256):
        nonce = bytes((first, 0, 0, 0))
        rc522_parity = 0x01 if first < 11 else 0x00
        records.extend(nonce)
        records.append(rc522_parity)

    source = tmp_path / "raw.bin"
    output = tmp_path / "pm3.bin"
    source.write_bytes(records)

    import pytest

    with pytest.raises(ValueError, match="invalid Proxmark3 First_Byte_Sum"):
        convert_rc522_to_pm3(
            source,
            output,
            uid="DEADBEEF",
            target_block=20,
            target_key_type=KeyType.A,
        )
