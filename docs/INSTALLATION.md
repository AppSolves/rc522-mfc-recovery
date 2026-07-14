# Installation

## Supported installation target

The automated installer currently targets Raspberry Pi OS or Debian on:

- `arm64`
- `armhf`

Raspberry Pi OS Trixie arm64 on Raspberry Pi 5 is the primary validated environment.

## Automated installation

From a source checkout:

```bash
./scripts/bootstrap.sh
```

Equivalent CLI command after the Python package is available:

```bash
rc522-mfc setup
```

Use `--force` to rebuild the native helper and refetch the pinned Proxmark3 source:

```bash
./scripts/bootstrap.sh --force
```

Use `--skip-apt` when the Debian packages are already installed or package management is handled externally:

```bash
./scripts/bootstrap.sh --skip-apt
```

## What is installed

### System packages

The installer uses `apt` for:

- C and C++ build tools
- CMake and Ninja
- Git and curl
- Python development and virtual-environment support
- the reduced set of libraries required by the Proxmark3 client build

### WiringPi

WiringPi 3.18 is installed from its official GitHub release Debian package. The architecture is selected from `dpkg --print-architecture`.

### Native helper

The native executable is installed to:

```text
~/.local/lib/rc522-mfc/bin/rc522-mfc-native
```

Override the prefix with:

```bash
export RC522_MFC_PREFIX=/custom/prefix
```

### Proxmark3 offline solver

The installer fetches the pinned Proxmark3 commit into:

```text
~/.cache/rc522-mfc/proxmark3-<commit>/
```

It applies `patches/proxmark3-offline-hardnested.patch`, builds the client only, and exposes the checkout through:

```text
~/.local/lib/rc522-mfc/proxmark3/
```

The `pm3` file in that directory is a launcher. The actual compiled client is `client/proxmark3` inside the same checkout, and setup validates that executable before treating the solver as installed. If the offline Hardnested patch is newly applied, or the compiled client is older than the patched source, setup rebuilds the client.

Override the cache path with:

```bash
export RC522_MFC_CACHE=/custom/cache
```

### Python CLI

A virtual environment is created at:

```text
<repository>/.venv/
```

Activate it with:

```bash
source .venv/bin/activate
```

## SPI

The installer attempts to enable SPI non-interactively when `raspi-config` exists:

```bash
sudo raspi-config nonint do_spi 0
```

Reboot after first enabling SPI, then confirm:

```bash
ls -l /dev/spidev0.0
```

## Environment overrides

| Variable | Purpose |
|---|---|
| `RC522_MFC_PREFIX` | Native helper and Proxmark3 link prefix |
| `RC522_MFC_CACHE` | Downloaded Proxmark3 source cache |
| `RC522_MFC_NATIVE` | Explicit native helper path |
| `RC522_MFC_PM3` | Explicit patched PM3 launcher path |

## Manual build

### Native helper

```bash
./scripts/build-native.sh
```

For a hardware-free build used in CI:

```bash
cmake -S native -B build/mock -DRC522_HARDWARE=OFF
cmake --build build/mock
```

### Proxmark3 client

```bash
./scripts/build-proxmark.sh
```

The script pins the tested commit and refuses to continue when the source is unexpectedly modified or the patch does not apply cleanly.

## Updating dependencies

Dependency updates should be deliberate:

1. update one pinned version or commit,
2. rebuild on Raspberry Pi,
3. validate card identification,
4. validate a known-key Hardnested trace set,
5. run a complete solve and direct key verification,
6. update `docs/TEST_MATRIX.md` and `CHANGELOG.md`.

Do not silently follow Proxmark3 `master` during normal installation. Its file format and command behavior are external integration points for this project.

## Uninstall

Remove project-installed user files with:

```bash
./scripts/uninstall.sh
```

By default, this does not remove WiringPi because WiringPi is a shared system library. Use the script's `--remove-wiringpi` option only when no other project needs it.
