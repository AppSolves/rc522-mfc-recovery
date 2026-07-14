# Test matrix

## Hardware-validated configuration

| Component | Validated value |
|---|---|
| Raspberry Pi | Raspberry Pi 5, 8 GB |
| Operating system | Raspberry Pi OS, Debian Trixie, arm64 |
| WiringPi | 3.18 |
| Reader | MFRC522-compatible RC522 module |
| VersionReg | `0x92` |
| Interface | SPI0 CE0 |
| Card class | MIFARE Classic 1K, 4-byte UID |
| Nonce class | Hardened PRNG |
| RC522 acquisition | 20,000 unique encrypted nonce records |
| First-byte coverage | 256 of 256 |
| Offline solver | RRG/Iceman Proxmark3 commit `d0e8cf18614286c8f6be0864ef77b7ce5cae693d` |
| Verification | Recovered Key A and Key B authenticated and read data successfully |

No card UID, key, nonce file, hash, or dump from the validation card is included in this repository.

The validated hardware run exercised the same native Hardnested acquisition, parity conversion, Proxmark3 offline solving, and direct verification path used here. The final Typer orchestration layer has automated tests and a hardware-free native build, but this publication archive has not been rerun end to end on physical hardware after the final CLI refactor.

## Automated tests

GitHub Actions runs:

- Python unit tests on Python 3.11 and 3.13
- Ruff linting
- strict Mypy checking
- source and wheel package builds
- native C and C++ compilation with hardware access disabled

## Not yet hardware-revalidated in this release

- weak-PRNG card recovery after the generic CLI refactor
- MFRC522 VersionReg `0x91`
- Raspberry Pi 4
- armhf Raspberry Pi OS

The weak-Nested core is based on the existing upstream RC522 implementation and includes correctness fixes, but release claims distinguish implementation from current hardware validation.
