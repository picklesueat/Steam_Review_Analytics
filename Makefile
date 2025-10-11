.PHONY: help dev-install lint test format dbt-compile docs

PYTHON ?= python3
VENV ?= .venv

help:
	@echo "Available targets:"
	@echo "  make dev-install  # Create virtual environment & install deps"
	@echo "  make lint         # Run static analysis (ruff/black/mypy)"
	@echo "  make format       # Auto-format Python code"
	@echo "  make test         # Execute unit tests & dbt tests"
	@echo "  make dbt-compile  # Compile dbt project"
	@echo "  make docs         # Build documentation previews"

$(VENV)/bin/activate:
	@echo "Creating virtual environment in $(VENV)"
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

dev-install: $(VENV)/bin/activate
	@echo "Environment ready. Activate with 'source $(VENV)/bin/activate'"

lint: $(VENV)/bin/activate
        @echo "Running lint checks"
        $(VENV)/bin/ruff check ingest_steam pipelines replayer
        $(VENV)/bin/black --check ingest_steam pipelines replayer
        $(VENV)/bin/mypy ingest_steam pipelines replayer || true

format: $(VENV)/bin/activate
        $(VENV)/bin/ruff check --fix ingest_steam pipelines replayer
        $(VENV)/bin/black ingest_steam pipelines replayer

test:
	@echo "TODO: implement pytest + dbt test execution"

dbt-compile:
	@echo "TODO: run 'dbt compile' once models are defined"

docs:
	@echo "TODO: build docs (MkDocs/Sphinx/Notion sync)"
