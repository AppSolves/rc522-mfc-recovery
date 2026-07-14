#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

rm -rf \
  "$ROOT/build" \
  "$ROOT/build-test" \
  "$ROOT/dist" \
  "$ROOT/.pytest_cache" \
  "$ROOT/.mypy_cache" \
  "$ROOT/.ruff_cache"

find "$ROOT" -type d -name __pycache__ -prune -exec rm -rf {} +
find "$ROOT" -type f \( -name '*.pyc' -o -name '*.pyo' \) -delete

printf 'Removed local build and test artifacts.\n'
