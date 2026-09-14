PYTHON_VERSIONS ?= 3.9 3.10 3.11 3.12 3.13 3.14
PYTEST_VERSIONS ?= 7.0.1 7.4.4 8.0.2 8.4.2 9.1.1

.PHONY: lint format test matrix

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy

format:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest

matrix:
	@for py in $(PYTHON_VERSIONS); do \
		for pt in $(PYTEST_VERSIONS); do \
			printf "python %-5s pytest %-7s " $$py $$pt; \
			uv run --isolated --no-dev --python $$py --with "pytest==$$pt" pytest -q 2>&1 | tail -1; \
		done; \
	done
