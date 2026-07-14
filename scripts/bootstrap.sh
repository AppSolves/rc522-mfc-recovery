#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BANNER="$ROOT/src/rc522_mfc/data/banner.txt"

FORCE=0
SKIP_APT=0

WIRINGPI_VERSION="${WIRINGPI_VERSION:-3.18}"
SPI_DEVICE="${RC522_SPI_DEVICE:-/dev/spidev0.0}"

SPI_READY=0
SPI_CHANGED=0
SPI_MANUAL_ACTION_REQUIRED=0
REBOOT_REQUIRED=0

declare -a REBOOT_REASONS=()

usage() {
  cat <<USAGE
Usage:
  bash scripts/bootstrap.sh [options]

Options:
  --force       Rebuild and reinstall dependencies.
  --skip-apt    Skip apt update and package installation.
  -h, --help    Show this help message.

Environment variables:
  RC522_SPI_DEVICE    SPI device to check.
                      Default: /dev/spidev0.0

  WIRINGPI_VERSION    WiringPi version to install.
                      Default: 3.18
USAGE
}

print_badge() {
  if [[ -f "$BANNER" ]]; then
    printf '\n'
    cat "$BANNER"
    printf '\n\n'
  fi
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force)
      FORCE=1
      ;;
    --skip-apt)
      SKIP_APT=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n\n' "$1" >&2
      usage >&2
      exit 2
      ;;
  esac

  shift
done

print_badge

if [[ "$(uname -s)" != "Linux" ]]; then
  printf '%s\n' \
    'This installer currently supports Raspberry Pi OS and Debian Linux only.' \
    >&2
  exit 1
fi

if ! command -v dpkg >/dev/null 2>&1; then
  printf '%s\n' \
    'dpkg is required. Use Raspberry Pi OS or Debian.' \
    >&2
  exit 1
fi

ARCH="$(dpkg --print-architecture)"

if [[ "$ARCH" != "arm64" && "$ARCH" != "armhf" ]]; then
  printf \
    'Unsupported architecture: %s. Use arm64 or armhf Raspberry Pi OS.\n' \
    "$ARCH" \
    >&2
  exit 1
fi

printf 'Project root: %s\n' "$ROOT"
printf 'Architecture: %s\n' "$ARCH"
printf 'SPI device:   %s\n\n' "$SPI_DEVICE"

if [[ $SKIP_APT -eq 0 ]]; then
  printf 'Installing system dependencies...\n'

  sudo apt update

  sudo apt install -y --no-install-recommends \
    build-essential \
    ca-certificates \
    cmake \
    curl \
    git \
    ninja-build \
    pkg-config \
    tmux \
    python3-dev \
    python3-pip \
    python3-venv \
    libbz2-dev \
    liblz4-dev \
    libreadline-dev \
    libssl-dev \
    zlib1g-dev
else
  printf 'Skipping apt package installation.\n'
fi

if [[ -f /var/run/reboot-required ]]; then
  REBOOT_REQUIRED=1
  REBOOT_REASONS+=(
    "The operating system reports that updated components require a reboot."
  )
fi

printf '\nChecking SPI...\n'

if [[ -e "$SPI_DEVICE" ]]; then
  SPI_READY=1
  printf 'SPI is already active: %s\n' "$SPI_DEVICE"
elif command -v raspi-config >/dev/null 2>&1; then
  SPI_STATE="$(
    sudo raspi-config nonint get_spi 2>/dev/null |
      tr -d '[:space:]' ||
      true
  )"

  if [[ "$SPI_STATE" == "0" ]]; then
    printf 'SPI is enabled in the Raspberry Pi configuration.\n'
  else
    printf 'Enabling SPI through raspi-config...\n'

    if sudo raspi-config nonint do_spi 0; then
      SPI_CHANGED=1
      printf 'SPI configuration was updated successfully.\n'
    else
      printf 'Warning: SPI could not be enabled automatically.\n' >&2
      SPI_MANUAL_ACTION_REQUIRED=1
    fi
  fi

  for _ in {1..15}; do
    if [[ -e "$SPI_DEVICE" ]]; then
      SPI_READY=1
      break
    fi

    sleep 0.2
  done

  if [[ $SPI_READY -eq 1 ]]; then
    printf 'SPI is active: %s\n' "$SPI_DEVICE"
  elif [[ $SPI_MANUAL_ACTION_REQUIRED -eq 0 ]]; then
    REBOOT_REQUIRED=1

    if [[ $SPI_CHANGED -eq 1 ]]; then
      REBOOT_REASONS+=(
        "SPI was enabled, but ${SPI_DEVICE} is not available in the current boot."
      )
    else
      REBOOT_REASONS+=(
        "SPI is configured, but ${SPI_DEVICE} is not currently available."
      )
    fi
  fi
else
  printf \
    'Warning: raspi-config is unavailable and %s was not found.\n' \
    "$SPI_DEVICE" \
    >&2

  SPI_MANUAL_ACTION_REQUIRED=1
fi

printf '\nChecking WiringPi...\n'

INSTALLED_WIRINGPI="$(
  gpio -v 2>/dev/null |
    sed -n 's/^gpio version: //p' |
    head -1 ||
    true
)"

if [[ $FORCE -eq 1 || "$INSTALLED_WIRINGPI" != "$WIRINGPI_VERSION" ]]; then
  TMP_DEB="$(mktemp --suffix=.deb)"

  cleanup() {
    rm -f "$TMP_DEB"
  }

  trap cleanup EXIT

  URL="$(
    printf \
      'https://github.com/WiringPi/WiringPi/releases/download/%s/wiringpi_%s_%s.deb' \
      "$WIRINGPI_VERSION" \
      "$WIRINGPI_VERSION" \
      "$ARCH"
  )"

  printf \
    'Installing WiringPi %s for %s...\n' \
    "$WIRINGPI_VERSION" \
    "$ARCH"

  curl \
    --fail \
    --location \
    --retry 3 \
    --retry-all-errors \
    --output "$TMP_DEB" \
    "$URL"

  DOWNLOADED_ARCH="$(dpkg-deb -f "$TMP_DEB" Architecture)"

  if [[ "$DOWNLOADED_ARCH" != "$ARCH" ]]; then
    printf \
      'Downloaded WiringPi architecture %s does not match %s.\n' \
      "$DOWNLOADED_ARCH" \
      "$ARCH" \
      >&2
    exit 1
  fi

  sudo apt install \
    -y \
    --allow-downgrades \
    "$TMP_DEB"
else
  printf \
    'WiringPi %s is already installed.\n' \
    "$WIRINGPI_VERSION"
fi

INSTALLED_WIRINGPI="$(
  gpio -v 2>/dev/null |
    sed -n 's/^gpio version: //p' |
    head -1 ||
    true
)"

if [[ "$INSTALLED_WIRINGPI" != "$WIRINGPI_VERSION" ]]; then
  printf \
    'WiringPi %s was not installed correctly. Detected: %s\n' \
    "$WIRINGPI_VERSION" \
    "${INSTALLED_WIRINGPI:-none}" \
    >&2
  exit 1
fi

printf '\nBuilding native RC522 helper...\n'

bash "$ROOT/scripts/build-native.sh"

printf '\nBuilding offline Proxmark3 solver...\n'

if [[ $FORCE -eq 1 ]]; then
  bash "$ROOT/scripts/build-proxmark.sh" --force
else
  bash "$ROOT/scripts/build-proxmark.sh"
fi

printf '\nCreating Python environment...\n'

if [[ ! -d "$ROOT/.venv" ]]; then
  python3 -m venv "$ROOT/.venv"
fi

"$ROOT/.venv/bin/python" \
  -m pip install \
  --upgrade \
  pip

"$ROOT/.venv/bin/python" \
  -m pip install \
  -e "$ROOT"

printf '\nVerifying Python CLI dependencies...\n'

"$ROOT/.venv/bin/python" \
  -c 'import typer; import rc522_mfc.cli'

printf '\n============================================================\n'
printf 'Setup complete\n'
printf '============================================================\n\n'

if [[ $SPI_READY -eq 1 ]]; then
  printf 'SPI status: ready at %s\n' "$SPI_DEVICE"
else
  printf 'SPI status: device not currently available\n'
fi

if [[ $SPI_MANUAL_ACTION_REQUIRED -eq 1 ]]; then
  cat <<EOF

Manual SPI configuration is required.

Run:

  sudo raspi-config

Then select:

  Interface Options
  SPI
  Enable

Afterward, reboot:

  sudo reboot

After reconnecting:

  cd "$ROOT"
  source .venv/bin/activate
  rc522-mfc doctor
  rc522-mfc inspect
EOF
elif [[ $REBOOT_REQUIRED -eq 1 ]]; then
  printf '\nA reboot is required for the following reason(s):\n'

  for reason in "${REBOOT_REASONS[@]}"; do
    printf '  - %s\n' "$reason"
  done

  cat <<EOF

Reboot now:

  sudo reboot

After reconnecting:

  cd "$ROOT"
  source .venv/bin/activate
  rc522-mfc doctor
  rc522-mfc inspect
EOF
else
  cat <<EOF

No reboot is required.

Activate the environment:

  source "$ROOT/.venv/bin/activate"

Then run:

  rc522-mfc doctor
  rc522-mfc inspect
EOF
fi
