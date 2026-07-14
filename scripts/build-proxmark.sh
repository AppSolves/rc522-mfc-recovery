#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PREFIX="${RC522_MFC_PREFIX:-$HOME/.local/lib/rc522-mfc}"
CACHE="${RC522_MFC_CACHE:-$HOME/.cache/rc522-mfc}"
PM3_COMMIT="d0e8cf18614286c8f6be0864ef77b7ce5cae693d"
PM3_DIR="$CACHE/proxmark3-$PM3_COMMIT"
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --force) FORCE=1 ;;
    *) printf 'Unknown option: %s\n' "$1" >&2; exit 2 ;;
  esac
  shift
done

if [[ $FORCE -eq 1 ]]; then
  rm -rf "$PM3_DIR"
fi

if [[ ! -d "$PM3_DIR/.git" ]]; then
  mkdir -p "$PM3_DIR"
  git -C "$PM3_DIR" init
  git -C "$PM3_DIR" remote add origin https://github.com/RfidResearchGroup/proxmark3.git
  git -C "$PM3_DIR" fetch --depth 1 origin "$PM3_COMMIT"
  git -C "$PM3_DIR" checkout --detach FETCH_HEAD
fi

if [[ "$(git -C "$PM3_DIR" rev-parse HEAD)" != "$PM3_COMMIT" ]]; then
  printf 'Unexpected Proxmark3 commit in %s.\n' "$PM3_DIR" >&2
  exit 1
fi

if grep -q 'nonce_file_read == false' "$PM3_DIR/client/src/cmdhfmf.c"; then
  printf 'Offline Hardnested patch already applied.\n'
elif git -C "$PM3_DIR" diff --quiet -- client/src/cmdhfmf.c \
  && git -C "$PM3_DIR" apply --check "$ROOT/patches/proxmark3-offline-hardnested.patch"; then
  git -C "$PM3_DIR" apply "$ROOT/patches/proxmark3-offline-hardnested.patch"
else
  printf 'The pinned Proxmark3 source is modified or the patch does not apply cleanly.\n' >&2
  exit 1
fi

if [[ $FORCE -eq 0 && -x "$PM3_DIR/pm3" ]]; then
  printf 'Using existing patched Proxmark3 client at %s\n' "$PM3_DIR/pm3"
else
  make -C "$PM3_DIR" client/clean
  make -C "$PM3_DIR" -j"$(nproc)" client \
    SKIPQT=1 \
    SKIPBT=1 \
    SKIPPYTHON=1 \
    SKIPGD=1 \
    NOERROR=1
fi

if [[ ! -x "$PM3_DIR/pm3" ]]; then
  printf 'Proxmark3 client build did not produce %s/pm3.\n' "$PM3_DIR" >&2
  exit 1
fi

mkdir -p "$PREFIX"
rm -rf "$PREFIX/proxmark3"
ln -s "$PM3_DIR" "$PREFIX/proxmark3"
printf 'Installed patched offline solver at %s\n' "$PREFIX/proxmark3/pm3"
