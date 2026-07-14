#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${RC522_MFC_PREFIX:-$HOME/.local/lib/rc522-mfc}"
BUILD_DIR="${RC522_MFC_NATIVE_BUILD:-$ROOT/build/native}"

cmake -S "$ROOT/native" -B "$BUILD_DIR" \
  -DRC522_HARDWARE=ON \
  -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD_DIR" -j"$(nproc)"
install -Dm755 "$BUILD_DIR/rc522-mfc-native" "$PREFIX/bin/rc522-mfc-native"
printf 'Installed native helper to %s\n' "$PREFIX/bin/rc522-mfc-native"
