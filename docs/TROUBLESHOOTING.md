# Troubleshooting

## `VersionReg` is `0x00` or `0xFF`

- confirm 3.3 V power,
- confirm common ground,
- verify SDA/SS is connected to physical pin 24,
- verify RST is connected to physical pin 18,
- confirm `/dev/spidev0.0` exists,
- shorten jumper wires,
- try another RC522 module.

## The card is not detected

This project supports the MIFARE Classic 1K identification values expected by the vendored reader core. Confirm the card type with another reader or Android MIFARE Classic Tool.

## Weak Nested produces no key

Run `rc522-mfc inspect`. A hardened card will not work with classic Nested. If the card is classified as weak but recovery fails, keep the card still and rerun with the default timing before changing compile-time tuning values.

## Hardnested solver rejects `First_Byte_Sum`

Do not solve the file. The usual causes are:

- parity nibble order was not converted,
- the dataset was truncated,
- records came from different cards,
- UID or target metadata is wrong.

The built-in converter rejects invalid complete datasets automatically.

## Hardnested collection stops before all samples are collected

The collector exits with an explicit error when it reaches the native attempt limit or stalls after repeated authentication failures. Check the seed key, keep the card motionless on the antenna, and rerun with the same command. Complete datasets are reused automatically; incomplete datasets are recollected.

The progress display shows collected records, total records, native attempts, and consecutive failures. If collected records do not increase while consecutive failures climb, the problem is before the offline solver: card coupling, card movement, reader communication, or an invalid known key.

## Proxmark3 client build fails on a warning

The pinned build uses `NOERROR=1` because recent GCC versions can emit warnings in unrelated Proxmark3 commands. The Hardnested sources are still compiled normally.

## SSH disconnected

Run long recovery jobs in `tmux` or `screen`. Verified state and complete datasets are reusable, but a partially written nonce file is recollected.

## Continuous communication failures

Do not run two reader processes simultaneously. Reposition the card, check antenna coupling, and verify that no previous native helper remains active:

```bash
pgrep -af rc522-mfc-native
```
