from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from .models import KeyType

VALID_FIRST_BYTE_SUMS = {
    0,
    32,
    56,
    64,
    80,
    96,
    104,
    112,
    120,
    128,
    136,
    144,
    152,
    160,
    176,
    192,
    200,
    224,
    256,
}


@dataclass(frozen=True, slots=True)
class ConversionResult:
    records: int
    pairs: int
    output_size: int
    first_byte_coverage: int
    first_byte_sum: int
    sha256: str


def reverse_parity_nibble(value: int) -> int:
    value &= 0x0F
    return ((value & 0x01) << 3) | ((value & 0x02) << 1) | ((value & 0x04) >> 1) | ((value & 0x08) >> 3)


def calculate_first_byte_sum(data: bytes) -> tuple[int, int]:
    seen: set[int] = set()
    total = 0
    for offset in range(6, len(data), 9):
        nonce1 = data[offset : offset + 4]
        nonce2 = data[offset + 4 : offset + 8]
        packed = data[offset + 8]
        for nonce, parity in ((nonce1, (packed >> 4) & 0x0F), (nonce2, packed & 0x0F)):
            first = nonce[0]
            if first in seen:
                continue
            seen.add(first)
            total += ((first << 24) | (parity & 0x08)).bit_count() & 1
    return total, len(seen)


def convert_rc522_to_pm3(
    input_path: Path,
    output_path: Path,
    *,
    uid: str,
    target_block: int,
    target_key_type: KeyType,
) -> ConversionResult:
    uid_bytes = bytes.fromhex(uid.replace(":", "").replace(" ", ""))
    if len(uid_bytes) != 4:
        raise ValueError("Hardnested PM3 files require a four-byte UID")
    if not 0 <= target_block <= 255:
        raise ValueError("target block must fit in one byte")
    raw = input_path.read_bytes()
    if not raw or len(raw) % 5:
        raise ValueError("RC522 dataset must contain complete five-byte records")
    records = len(raw) // 5
    if records % 2:
        raise ValueError("an even record count is required")
    output = bytearray(uid_bytes)
    output.extend((target_block, 0 if target_key_type is KeyType.A else 1))
    for offset in range(0, len(raw), 10):
        nonce1 = raw[offset : offset + 4]
        parity1 = reverse_parity_nibble(raw[offset + 4])
        nonce2 = raw[offset + 5 : offset + 9]
        parity2 = reverse_parity_nibble(raw[offset + 9])
        output.extend(nonce1)
        output.extend(nonce2)
        output.append((parity1 << 4) | parity2)
    expected = 6 + (records // 2) * 9
    if len(output) != expected:
        raise AssertionError(f"generated {len(output)} bytes, expected {expected}")
    first_byte_sum, coverage = calculate_first_byte_sum(bytes(output))
    if coverage == 256 and first_byte_sum not in VALID_FIRST_BYTE_SUMS:
        raise ValueError(f"invalid Proxmark3 First_Byte_Sum: {first_byte_sum}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(output)
    return ConversionResult(
        records=records,
        pairs=records // 2,
        output_size=len(output),
        first_byte_coverage=coverage,
        first_byte_sum=first_byte_sum,
        sha256=hashlib.sha256(output).hexdigest(),
    )
