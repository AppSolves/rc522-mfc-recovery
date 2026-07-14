# CLI reference

## `--version` and `version`

```bash
rc522-mfc --version
rc522-mfc version
```

## `setup`

Install prerequisites and build the native helper and offline solver.

```bash
rc522-mfc setup
rc522-mfc setup --force
rc522-mfc setup --skip-apt
```

## `doctor`

Check:

- SPI device availability
- WiringPi command availability
- native helper installation
- patched Proxmark3 client installation
- MFRC522 VersionReg communication

```bash
rc522-mfc doctor
```

## `inspect`

Identify the card and classify its nonce generator.

```bash
rc522-mfc inspect
rc522-mfc inspect --samples 256
```

The sampling phase shows collected sample count and native attempt count in the Rich progress display.

## `recover`

Run the complete recovery workflow.

```bash
rc522-mfc recover \
  --known 4:A=FFFFFFFFFFFF \
  --sectors 0-15 \
  --key-types AB
```

Important options:

| Option | Meaning |
|---|---|
| `--known SECTOR:TYPE=KEY` | Add and verify a seed key. Repeatable. |
| `--sectors 5-15` | Select MIFARE Classic 1K sectors. |
| `--key-types A`, `B`, or `AB` | Select target key types. |
| `--dictionary FILE` | Add a one-key-per-line dictionary. Repeatable. |
| `--skip-dictionary` | Skip bundled and user-provided dictionary scanning entirely. |
| `--samples N` | Hardnested RC522 trace count per target. Rounded up to even. |
| `--nonce-type weak`, `hard` or `static` | Override classification for controlled testing. |
| `--no-fallback` | Prevent Hardnested fallback after weak Nested failure. |
| `--delete-traces` | Delete nonce files after a verified result. |

### Resume behavior

The state file is updated after every verified key. Complete Hardnested datasets are reused only when their size and metadata match the current UID and target.

Running the same command again resumes the remaining targets.

### Progress display

`recover` keeps one overall key-completion bar and one phase bar. Dictionary scans, nonce classification, and Hardnested trace collection are determinate. Hardnested collection includes attempt count and consecutive failure count so a stalled card or bad seed key is visible before the command exits. The offline Proxmark3 solver is intentionally indeterminate because the solver does not emit a reliable total-work value.

### Smart key reuse

After each discovery, the CLI tests all known key values across selected sectors. When Key A allows Key B to be read from a sector trailer, the extracted bytes are accepted only after a fresh Key B authentication succeeds.

### Skip dictionary scans

If you have already exhausted the bundled and custom dictionaries for a card, use `--skip-dictionary` to bypass that stage and move directly into nonce classification and recovery.

## `status`

Display a saved key map:

```bash
rc522-mfc status DEADBEEF
```

## `verify`

Authenticate all saved keys again against the card:

```bash
rc522-mfc verify DEADBEEF
```

Failed keys are marked unverified in state.

## `export`

```bash
rc522-mfc export DEADBEEF --format json
rc522-mfc export DEADBEEF --format csv
rc522-mfc export DEADBEEF --format keys
rc522-mfc export DEADBEEF --format dump
```

CSV, `.keys`, and dump export use verified keys only. JSON preserves the full state, including unverified records.

The dump export requires at least one verified key for every sector. The native reader still reports a clear block-specific error when the available key does not have read permission for a block.
