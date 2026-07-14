# Modifications to MFRC522_nested_attack

This directory began from Håkon Hystad's `MFRC522_nested_attack` repository at
commit `211ed2a64ac5658e181b1a5cbf5bc63e9cc90775`.

The original project is licensed under GPL-3.0. Its license and upstream README
are preserved in this directory.

## Reader and platform changes

- Enabled hardware support through build definitions instead of editing a source constant.
- Added bounded card selection to replace blocking retry loops in automated workflows.
- Added quiet machine-oriented operation while retaining useful interactive diagnostics.
- Added MFRC522 VersionReg inspection.
- Reduced the default SPI clock to 1 MHz for conservative Raspberry Pi 5 operation.
- Initialized and invalidated cached authentication state explicitly.
- Corrected validated-key caching from four bytes to all six key bytes.
- Corrected block reads so an already authenticated sector is not needlessly re-authenticated.
- Added clean Crypto1 state destruction and reset behavior.

## Weak-Nested changes

- Generalized the known block, known key type, known key, target block, and target key type.
- Added a callable `recoverWeakNested` interface for the unified native frontend.
- Improved candidate ranking across recovery sets.
- Removed assumptions that excluded valid all-zero candidates.
- Added bounded selection and cleanup on error paths.

## New acquisition features

- Added raw authentication nonce sampling for weak, hard, and static nonce classification.
- Added generic encrypted nonce and encrypted parity collection for Hardnested.
- Added validation-friendly parity packing and metadata support in the native frontend.

## New frontend

The original standalone `main.cpp` and web-demo pieces are not included. They
are replaced by `native/src/rc522_mfc_native.cpp`, which exposes focused,
read-only commands with `RC522_JSON:` machine output for the Python CLI.

For exact source changes, compare this directory with the pinned upstream
commit listed above.
