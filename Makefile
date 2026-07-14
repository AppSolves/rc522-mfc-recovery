.PHONY: setup native solver test lint format package release-check clean uninstall

setup:
	./scripts/bootstrap.sh

native:
	./scripts/build-native.sh

solver:
	./scripts/build-proxmark.sh

test:
	python -m pytest

lint:
	ruff check src tests
	mypy src

format:
	ruff format src tests
	ruff check --fix src tests

package:
	python -m build

release-check:
	./scripts/release-check.sh

clean:
	./scripts/clean.sh

uninstall:
	./scripts/uninstall.sh
