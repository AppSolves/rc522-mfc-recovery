#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TEMP_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEMP_ROOT"' EXIT

check_generated_artifacts() {
  for path in build build-test dist .pytest_cache .mypy_cache .ruff_cache; do
    if [[ -e "$path" ]]; then
      printf 'Generated path must be removed before release: %s\n' "$path" >&2
      exit 1
    fi
  done
  if find . -type d -name __pycache__ -print -quit | grep -q .; then
    printf '__pycache__ directories must be removed before release.\n' >&2
    exit 1
  fi
  if find . -type f \( -name '*.pyc' -o -name '*.pyo' \) -print -quit | grep -q .; then
    printf 'Compiled Python files must be removed before release.\n' >&2
    exit 1
  fi
}

printf '== Clean tree preflight ==\n'
check_generated_artifacts
printf 'No generated artifacts found.\n'

printf '\n== Shell syntax ==\n'
bash -n scripts/*.sh

printf '\n== Metadata syntax ==\n'
python3 - <<'PY'
from pathlib import Path
import tomllib

with Path('pyproject.toml').open('rb') as handle:
    tomllib.load(handle)
print('pyproject.toml: OK')

import yaml
for pattern in ('*.yml', '*.yaml'):
    for path in Path('.').rglob(pattern):
        if '.git' in path.parts:
            continue
        with path.open('r', encoding='utf-8') as handle:
            yaml.safe_load(handle)
        print(f'{path}: OK')
PY

printf '\n== Python quality ==\n'
PYTHONDONTWRITEBYTECODE=1 python3 -m ruff check --no-cache src tests
PYTHONDONTWRITEBYTECODE=1 python3 -m ruff format --check --no-cache src tests
PYTHONDONTWRITEBYTECODE=1 MYPYPATH=src python3 -m mypy --no-incremental --cache-dir "$TEMP_ROOT/mypy" src
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m pytest -q -p no:cacheprovider

printf '\n== Native mock build ==\n'
BUILD_DIR="$TEMP_ROOT/native-build"
PACKAGE_DIR="$TEMP_ROOT/packages"
mkdir -p "$BUILD_DIR" "$PACKAGE_DIR"
cmake -S native -B "$BUILD_DIR" -DRC522_HARDWARE=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build "$BUILD_DIR" --parallel 2

printf '\n== Python packages ==\n'
PYTHONDONTWRITEBYTECODE=1 python3 -m build --outdir "$PACKAGE_DIR"
python3 - "$PACKAGE_DIR" <<'PY'
from pathlib import Path
import sys
import tarfile
import zipfile

package_dir = Path(sys.argv[1])
for archive in sorted(package_dir.iterdir()):
    if archive.suffix == '.whl':
        with zipfile.ZipFile(archive) as handle:
            names = handle.namelist()
    elif archive.name.endswith('.tar.gz'):
        with tarfile.open(archive, 'r:gz') as handle:
            names = handle.getnames()
    else:
        continue
    forbidden = ('build-test/', '/build-test/', '/dist/', '/.pytest_cache/', '/__pycache__/')
    bad = [name for name in names if any(token in name for token in forbidden)]
    if bad:
        raise SystemExit(f'{archive.name} contains generated artifacts: {bad[:5]}')
    print(f'{archive.name}: OK ({len(names)} entries)')
PY

printf '\n== Private artifact names ==\n'
private_pattern='\.(bin|mfd|dump|eml|mct|keymap|meta|log|csv)$|(^|/)state\.json$|keys_recovered\.txt$|nonces\.txt$'
if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  tracked="$(git ls-files | grep -Ei "$private_pattern" | grep -v '^src/rc522_mfc/data/common.keys$' || true)"
else
  tracked="$(find . -type f | sed 's#^./##' | grep -Ei "$private_pattern" | grep -v '^src/rc522_mfc/data/common.keys$' || true)"
fi
if [[ -n "$tracked" ]]; then
  printf 'Potential private artifacts found:\n%s\n' "$tracked" >&2
  exit 1
fi
printf 'No private artifact filenames found.\n'

printf '\n== Generated artifacts after checks ==\n'
check_generated_artifacts
printf 'No generated artifacts found.\n'

printf '\n== Large files ==\n'
large="$(find . -type f -size +500k -not -path './.git/*' -print)"
if [[ -n "$large" ]]; then
  printf 'Files larger than 500 KiB require review:\n%s\n' "$large" >&2
  exit 1
fi
printf 'No unexpectedly large files found.\n'

printf '\nRelease checks passed.\n'
