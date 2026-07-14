# Contributing

Contributions are welcome for reliability, portability, testing, documentation, and read-only research workflows.

## Development setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e '.[dev]'
cmake -S native -B build/mock -DRC522_HARDWARE=OFF
cmake --build build/mock
pytest
ruff check src tests
mypy src
```

Hardware behavior must be tested on a disposable card that the contributor owns. Never submit real UIDs, keys, nonce files, dumps, or access-system data.

## Pull requests

- Keep commits focused.
- Add tests for Python format or state changes.
- Retain third-party copyright and license notices.
- Update `CHANGELOG.md` for user-visible changes.
- Explain any RF timing or parity changes with a reproducible test.

Before opening a pull request, run:

```bash
./scripts/clean.sh
./scripts/release-check.sh
```
