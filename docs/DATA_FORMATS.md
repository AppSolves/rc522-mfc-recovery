# Data formats

## RC522 Hardnested records

The native collector writes fixed five-byte records:

| Offset | Length | Meaning |
|---:|---:|---|
| 0 | 4 | encrypted nonce, big-endian |
| 4 | 1 | encrypted parity nibble |

In the RC522 nibble, bit 0 belongs to nonce byte 0 and bit 3 belongs to nonce byte 3.

## Proxmark3 Hardnested file

The converter writes:

- 4-byte CUID
- 1-byte target block
- 1-byte target key type, `0` for A and `1` for B
- repeated 9-byte pairs:
  - nonce 1, four bytes
  - nonce 2, four bytes
  - two packed parity nibbles

Proxmark3 expects the parity bit order reversed inside each nibble, so the converter performs a four-bit reversal and validates the First_Byte_Sum property when all 256 first-byte values are covered.

## State JSON

`state.json` contains card metadata and saved key records, including each record's `verified` flag. It is private and should not be committed.

Unverified records are retained so `status` and `verify` can show what failed and retry it later. They are not used for recovery completion, key reuse, CSV export, `.keys` export, or dump export.

## MCT `.keys`

The export is one unique verified 12-hex-character key per line. Comments are not included.

## Binary dump

The binary dump export contains 64 blocks of 16 bytes, for a total of 1,024 bytes. The native reader attempts Key A and Key B independently for each block.

MIFARE Classic does not reveal Key A during a normal sector-trailer read, and Key B may also be masked by the access conditions. The exporter inserts verified recovered keys into the trailer key fields after reading the access bytes. This produces a practical analysis dump while preserving the card-read data and access conditions.
