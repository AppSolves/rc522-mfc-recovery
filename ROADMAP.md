# Roadmap

## Near term

- Hardware regression test with a weak-PRNG MIFARE Classic 1K card
- Physical-card regression run after the native manual-auth and progress reporting fixes
- Signed release archives and checksums
- More fixture-based tests for Proxmark3 file conversion
- Optional trace-count adaptation based on first-byte coverage

## Future research

- Static Nested acquisition support for compatible static-nonce cards
- Static encrypted nonce variant classification
- Carefully scoped MIFARE Classic 4K support
- Alternative maintained GPIO and SPI backend to reduce WiringPi coupling

## Intentionally out of scope

- card writing
- UID cloning
- card emulation
- access-system automation
- non-MIFARE-Classic protocols
