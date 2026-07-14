#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${RC522_MFC_PREFIX:-$HOME/.local/lib/rc522-mfc}"
CACHE="${RC522_MFC_CACHE:-$HOME/.cache/rc522-mfc}"
REMOVE_WIRINGPI=0
REMOVE_PRIVATE_DATA=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --remove-wiringpi) REMOVE_WIRINGPI=1 ;;
    --remove-private-data) REMOVE_PRIVATE_DATA=1 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

rm -rf "$PREFIX" "$CACHE" "$ROOT/.venv"

if [[ $REMOVE_PRIVATE_DATA -eq 1 ]]; then
  rm -rf "${XDG_DATA_HOME:-$HOME/.local/share}/rc522-mfc"
fi

if [[ $REMOVE_WIRINGPI -eq 1 ]]; then
  sudo apt remove wiringpi
fi

printf 'Removed project-installed binaries, cache, and virtual environment.\n'
if [[ $REMOVE_PRIVATE_DATA -eq 0 ]]; then
  printf 'Private recovery state was preserved. Use --remove-private-data to delete it.\n'
fi
