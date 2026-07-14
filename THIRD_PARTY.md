# Third-party software

## MFRC522_nested_attack

- Upstream: https://github.com/HakonHystad/MFRC522_nested_attack
- Pinned source baseline: `211ed2a64ac5658e181b1a5cbf5bc63e9cc90775`
- License: GNU General Public License version 3
- Location: `native/vendor/hakon/`

The vendored source is modified to support Raspberry Pi 5, bounded card selection, complete key caching, generic weak-Nested source and target credentials, nonce classification, and Hardnested trace acquisition.

## Crypto1 / crapto1

The vendored Håkon source incorporates Crypto1 and crapto1 code attributed upstream to the NetGarage / MFOC ecosystem. The original copyright and GPL notices are retained in the source files.

## RRG/Iceman Proxmark3

- Upstream: https://github.com/RfidResearchGroup/proxmark3
- Tested commit: `d0e8cf18614286c8f6be0864ef77b7ce5cae693d`
- License: GNU General Public License version 3 or later
- Integration: fetched and built separately by `scripts/build-proxmark.sh`

The repository contains only a narrow patch that permits the existing Hardnested nonce-file reader to run without attached Proxmark3 hardware and preserves a user-supplied filename.

## WiringPi

- Upstream: https://github.com/WiringPi/WiringPi
- Pinned stable release: `3.18`
- License: GNU Lesser General Public License version 3 or later
- Integration: installed separately as a Debian package

## Python dependencies

Typer, Rich, Platformdirs, Hatchling, Ruff, Mypy, Pytest, and Pre-commit retain their respective upstream licenses. They are not vendored.
