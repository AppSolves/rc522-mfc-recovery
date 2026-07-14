# Architecture

## Components

### Python control plane

The `rc522_mfc` package owns orchestration, persistent state, dependency discovery, export formats, user interaction, and safety checks.

It never implements Crypto1 search itself. It invokes two isolated executables:

1. `rc522-mfc-native` for reader-facing work.
2. the patched Proxmark3 client for offline Hardnested solving.

### Native RC522 helper

The native helper is a single C++ executable with machine-readable output prefixed by `RC522_JSON:`. Its commands are:

- `reader-version`
- `identify`
- `auth`
- `keyscan`
- `nonce-probe`
- `weak-nested`
- `collect-hardnested`
- `dump`

The core reader and weak-Nested implementation is a modified copy of Håkon Hystad's GPL-3.0 project.

### Hardnested data path

```text
known verified sector key
        |
        v
normal authentication to known sector
        |
        v
encrypted nested auth request to target sector
        |
        v
32 encrypted nonce bits + 4 encrypted parity bits
        |
        v
5-byte RC522 records
        |
        v
Python parity-nibble conversion
        |
        v
Proxmark3 nonce-pair file
        |
        v
Proxmark3 offline Hardnested solver
        |
        v
candidate key
        |
        v
direct RC522 authentication verification
```

## Recovery order

For each selected card:

1. Verify supplied seed keys.
2. Test the bundled and user-provided dictionary unless `--skip-dictionary` disables that stage.
3. When Key A succeeds, read the sector trailer and verify any exposed Key B.
4. Test all known keys across all unknown sectors.
5. Classify the nonce generator.
6. Recover one missing key.
7. Verify it against the card.
8. Test the new key across every remaining sector.
9. Persist state atomically.
10. Continue until the requested map is complete.

This ordering minimizes expensive nonce collection when deployments reuse keys.

## State model

State is stored per UID under the platform data directory. A key is accepted only after direct authentication. Each record stores its source, verification status, and discovery time.

Raw trace files and solver logs live beside the private state, not in the source checkout.

## Dependency model

No Git submodules are used.

- The small modified Håkon core is vendored and reviewed.
- WiringPi is a separately installed system dependency.
- Proxmark3 is a pinned cached dependency because it is large and only one client feature is used.
