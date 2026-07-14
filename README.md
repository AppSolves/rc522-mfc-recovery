# RC522 MIFARE Classic Recovery

[![CI](https://github.com/AppSolves/rc522-mfc-recovery/actions/workflows/ci.yml/badge.svg)](https://github.com/AppSolves/rc522-mfc-recovery/actions/workflows/ci.yml)
[![License: GPL-3.0-only](https://img.shields.io/badge/license-GPL--3.0--only-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Platform: Raspberry Pi](https://img.shields.io/badge/platform-Raspberry%20Pi-c51a4a.svg)](docs/HARDWARE.md)

A reproducible, read-only research toolkit for recovering **MIFARE Classic 1K** sector keys with a Raspberry Pi and an inexpensive **MFRC522 / RC522** reader.

The project unifies two recovery paths behind one Typer and Rich CLI:

- **Weak nonce cards:** classic Nested recovery based on Håkon Hystad's `MFRC522_nested_attack` implementation.
- **Hardened nonce cards:** an RC522 raw-frame acquisition path developed for this project, followed by the RRG/Iceman Proxmark3 Hardnested solver in offline mode.

Every candidate is authenticated against the physical card before it is accepted. Every verified key is immediately tested across remaining sectors, so reused keys and readable Key B values are discovered before another expensive nonce collection begins.

> [!IMPORTANT]
> Use this project only with cards you own or have explicit permission to test. The bundled workflow is read-only and contains no card-writing, cloning, or emulation command.

## Why this works

The MFRC522 can transmit raw ISO 14443-A frames and expose encrypted parity when automatic parity handling is disabled. That is enough to collect the encrypted nonce material required by Hardnested. The CPU-intensive Crypto1 search is delegated to the mature Proxmark3 client in offline mode.

This project is **not a complete Proxmark3 replacement**. It is a focused MIFARE Classic acquisition frontend for one inexpensive reader.

## Current scope

| Capability | Status |
|---|---|
| Raspberry Pi 5, Raspberry Pi OS Trixie arm64 | Hardware tested |
| Raspberry Pi 4 | Expected to work, community validation welcome |
| MFRC522 VersionReg `0x92` | Hardware tested |
| MFRC522 VersionReg `0x91` | Expected to work |
| MIFARE Classic 1K, 4-byte UID | Supported |
| Common-key and reused-key discovery | Supported |
| Readable Key B extraction from sector trailers | Supported and re-authenticated before acceptance |
| Weak PRNG Nested | Implemented from the upstream RC522 attack path |
| Hardened PRNG Hardnested | Hardware validated on Raspberry Pi 5 and MFRC522 `0x92` |
| Direct recovered-key verification | Supported |
| Resumable private state | Supported |
| JSON, CSV, MCT `.keys`, and 1 KiB binary dump export | Supported |
| Static nonce and static encrypted nonce cards | Detected, not implemented |
| MIFARE Classic 4K, Plus, DESFire, Ultralight, NTAG | Not supported |
| Writing, cloning, emulation | Intentionally out of scope |

See [docs/TEST_MATRIX.md](docs/TEST_MATRIX.md) for the exact validated environment.

## Hardware wiring

Power the RC522 from **3.3 V only**.

| RC522 | Raspberry Pi physical pin | Signal |
|---|---:|---|
| `3.3V` | 1 | 3.3 V |
| `GND` | 6 | Ground |
| `SDA` / `SS` | 24 | SPI0 CE0, GPIO8 |
| `SCK` | 23 | SPI0 SCLK, GPIO11 |
| `MOSI` | 19 | SPI0 MOSI, GPIO10 |
| `MISO` | 21 | SPI0 MISO, GPIO9 |
| `RST` | 18 | GPIO24, WiringPi pin 5 |
| `IRQ` | Not connected | Unused |

Detailed hardware guidance is in [docs/HARDWARE.md](docs/HARDWARE.md).

## Quick start

```bash
git clone https://github.com/AppSolves/rc522-mfc-recovery.git
cd rc522-mfc-recovery
./scripts/bootstrap.sh
source .venv/bin/activate
rc522-mfc doctor
rc522-mfc --version
```

The installer:

1. installs the required Debian packages,
2. enables SPI through `raspi-config` when available,
3. installs the stable WiringPi 3.18 Debian package,
4. builds the native RC522 helper,
5. fetches a pinned Proxmark3 commit and applies the narrow offline Hardnested patch,
6. creates a Python virtual environment and installs the CLI.

The same process is available through:

```bash
rc522-mfc setup
```

Reader-facing commands perform a toolchain preflight. When a component is missing and the terminal is interactive, the CLI offers to run setup automatically.

## Inspect a card

```bash
rc522-mfc inspect
```

The command identifies the card and classifies its nonce generator as:

- `weak`
- `hard`
- `static`

## Recover keys

Nested recovery needs at least one known and verified sector key. Supply seeds in `SECTOR:TYPE=KEY` form:

```bash
rc522-mfc recover \
  --known 4:A=FFFFFFFFFFFF \
  --known 4:B=FFFFFFFFFFFF \
  --sectors 0-15 \
  --key-types AB
```

The automatic workflow performs these stages:

1. verify every supplied key directly,
2. test the bundled starter dictionary and optional user dictionaries, unless `--skip-dictionary` is set,
3. extract a readable Key B from a sector trailer when access conditions permit it,
4. verify any extracted Key B through a fresh authentication,
5. test every known key against all still-unknown sectors,
6. classify the nonce generator,
7. run weak Nested or RC522 Hardnested acquisition,
8. solve Hardnested data offline when required,
9. verify the recovered candidate directly,
10. repeat global key-reuse checks and continue.

Long stages use Rich progress rows. Dictionary scans, nonce classification, and Hardnested trace collection report determinate counts. Hardnested collection also reports native attempts and consecutive failures. The offline Proxmark3 solver is shown as an indeterminate stage because it does not expose a stable candidate-count progress value.

Use an additional MCT-compatible dictionary when appropriate:

```bash
rc522-mfc recover \
  --known 4:A=FFFFFFFFFFFF \
  --dictionary ~/extended-std.keys
```

The option can be repeated. A dictionary file contains one 12-hex-character key per line.

If you already know dictionary scanning will not help and want to go straight to nonce classification and recovery, skip that stage explicitly:

```bash
rc522-mfc recover \
  --known 4:A=FFFFFFFFFFFF \
  --skip-dictionary
```

An interrupted run is resumable. Verified keys and complete trace datasets are reused automatically. Trace metadata is checked against the UID, target block, key type, record count, and format before reuse.

## Long runs over SSH

Use `tmux` so an SSH disconnect does not end the workflow:

```bash
tmux new -s rc522-recovery
source .venv/bin/activate
rc522-mfc recover --known 4:A=FFFFFFFFFFFF
```

Detach with `Ctrl+B`, then `D`. Reattach with:

```bash
tmux attach -t rc522-recovery
```

## Status and verification

```bash
rc522-mfc status DEADBEEF
rc522-mfc verify DEADBEEF
```

Private state is stored under the platform data directory, normally:

```text
~/.local/share/rc522-mfc/cards/<UID>/
```

## Export

```bash
rc522-mfc export DEADBEEF --format json
rc522-mfc export DEADBEEF --format csv
rc522-mfc export DEADBEEF --format keys
rc522-mfc export DEADBEEF --format dump
```

Export formats:

- `json`: full key map, metadata, discovery source, verification state.
- `csv`: sector-oriented table containing verified keys only.
- `keys`: one unique verified key per line, compatible with MIFARE Classic Tool key files.
- `dump`: 1,024-byte MIFARE Classic binary image. Verified recovered key bytes are inserted into sector trailer key fields because Key A is masked during normal card reads.

The dump reader tries verified Key A and Key B independently for each block, which supports sectors whose access conditions require different keys for different blocks. Keys marked unverified by `rc522-mfc verify` remain visible in JSON and `status`, but they are not treated as recovered for reuse, CSV, `.keys`, or dump export.

## Dependency strategy

This repository deliberately uses **no Git submodules**.

- The small Håkon Hystad reader and weak-Nested core is vendored because this project contains substantial reviewed modifications to it.
- WiringPi is installed as a pinned platform package.
- Proxmark3 is fetched at a pinned tested commit into the user's cache, patched narrowly, and built as a client only.

This design keeps a normal ZIP download complete, avoids a very large Proxmark3 submodule, and avoids permanently dirty patched submodules.

More detail is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) and [docs/INSTALLATION.md](docs/INSTALLATION.md).

## Repository layout

```text
.
├── .github/                  GitHub Actions and contribution templates
├── docs/                     Architecture, installation, formats, hardware, troubleshooting
├── native/
│   ├── src/                  Unified RC522 native frontend
│   └── vendor/hakon/         Modified GPL-3.0 weak-Nested and reader core
├── patches/                  Narrow Proxmark3 offline-solver patch
├── scripts/                  Setup, build, cleanup, and release checks
├── src/rc522_mfc/            Typer and Rich orchestration package
├── tests/                    Python unit tests
├── LICENSE
├── THIRD_PARTY.md
└── pyproject.toml
```

## Development

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'

ruff check src tests
mypy src
pytest

cmake -S native -B build/mock -DRC522_HARDWARE=OFF
cmake --build build/mock
```

Run the release safety check before publishing:

```bash
./scripts/release-check.sh
```

## Security and private data

UIDs, keys, nonce traces, solver logs, and dumps are sensitive. They are ignored by Git, but `.gitignore` cannot remove data from an existing commit or archive.

Read [SECURITY.md](SECURITY.md) and [docs/PUBLISHING.md](docs/PUBLISHING.md) before publishing forks, issues, logs, or releases.

## Attribution and license

The combined source distribution is licensed under **GPL-3.0-only** because it includes a modified GPL-3.0 implementation of `MFRC522_nested_attack`.

The Proxmark3 client and WiringPi are downloaded or installed separately. Full attribution is in [THIRD_PARTY.md](THIRD_PARTY.md).

## References

The implementation builds on:

- Håkon Hystad, `MFRC522_nested_attack`
- RRG/Iceman Proxmark3
- Carlo Meijer and Roel Verdult, *Ciphertext-only Cryptanalysis on Hardened MIFARE Classic Cards*
- NXP MFRC522 data sheet

See [docs/REFERENCES.md](docs/REFERENCES.md).
