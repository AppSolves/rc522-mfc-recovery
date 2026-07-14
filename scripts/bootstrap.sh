#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FORCE=0
SKIP_APT=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1 ;;
    --skip-apt) SKIP_APT=1 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

if [[ "$(uname -s)" != "Linux" ]]; then
  printf 'This installer currently supports Raspberry Pi OS and Debian Linux only.\n' >&2
  exit 1
fi

if ! command -v dpkg >/dev/null 2>&1; then
  printf 'dpkg is required. Use Raspberry Pi OS or Debian.\n' >&2
  exit 1
fi

ARCH="$(dpkg --print-architecture)"
if [[ "$ARCH" != "arm64" && "$ARCH" != "armhf" ]]; then
  printf 'Unsupported architecture: %s. Use arm64 or armhf Raspberry Pi OS.\n' "$ARCH" >&2
  exit 1
fi

if [[ $SKIP_APT -eq 0 ]]; then
  sudo apt update
  sudo apt install -y --no-install-recommends \
    build-essential ca-certificates cmake curl git ninja-build pkg-config tmux \
    python3-dev python3-pip python3-venv \
    libbz2-dev liblz4-dev libreadline-dev libssl-dev zlib1g-dev
fi

if command -v raspi-config >/dev/null 2>&1; then
  sudo raspi-config nonint do_spi 0 || true
fi

WIRINGPI_VERSION="3.18"
INSTALLED_WIRINGPI="$(
  gpio -v 2>/dev/null | sed -n 's/^gpio version: //p' | head -1 || true
)"

if [[ $FORCE -eq 1 || "$INSTALLED_WIRINGPI" != "$WIRINGPI_VERSION" ]]; then
  TMP_DEB="$(mktemp --suffix=.deb)"
  trap 'rm -f "$TMP_DEB"' EXIT
  URL="https://github.com/WiringPi/WiringPi/releases/download/${WIRINGPI_VERSION}/wiringpi_${WIRINGPI_VERSION}_${ARCH}.deb"
  printf 'Installing WiringPi %s for %s...\n' "$WIRINGPI_VERSION" "$ARCH"
  curl \
    --fail \
    --location \
    --retry 3 \
    --retry-all-errors \
    --output "$TMP_DEB" \
    "$URL"
  if [[ "$(dpkg-deb -f "$TMP_DEB" Architecture)" != "$ARCH" ]]; then
    printf 'Downloaded WiringPi package architecture does not match %s.\n' "$ARCH" >&2
    exit 1
  fi
  sudo apt install -y --allow-downgrades "$TMP_DEB"
fi

if [[ "$(gpio -v 2>/dev/null | sed -n 's/^gpio version: //p' | head -1)" != "$WIRINGPI_VERSION" ]]; then
  printf 'WiringPi %s was not installed correctly.\n' "$WIRINGPI_VERSION" >&2
  exit 1
fi

"$ROOT/scripts/build-native.sh"
if [[ $FORCE -eq 1 ]]; then
  "$ROOT/scripts/build-proxmark.sh" --force
else
  "$ROOT/scripts/build-proxmark.sh"
fi

if [[ ! -d "$ROOT/.venv" ]]; then
  python3 -m venv "$ROOT/.venv"
fi
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -e "$ROOT"

cat <<EOF

Setup complete.

Activate the environment:
  source "$ROOT/.venv/bin/activate"

Then run:
  rc522-mfc doctor
  rc522-mfc inspect
EOF
