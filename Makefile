# Use ?= to provide a default value if none is passed
PY ?= python3.12
PIP ?= $(PY) -m pip
VENVDIR ?= .venv
ACTIVATE = . $(VENVDIR)/bin/activate
PKG = src

DEV_EXTRAS ?= dev

.PHONY: help
help:
	@echo "Common targets:"
	@echo "  make all             Makes all except run"
	@echo "  make deps            Makes all dependency installation (Python)"
	@echo "  make setup           Makes all necessary to subsequently run"
	@echo "  make ci              Makes those needed for CI (lint, typecheck, test)"
	@echo "  make clean           Remove caches and build artifacts"
	@echo "  make venv            Create virtualenv (.venv)"
	@echo "  make install-dev     Install project + dev deps"
	@echo "  make docs            Build Sphinx HTML docs"
	@echo "  make lint            Run ruff (lint), black --check, codespell"
	@echo "  make format          Run ruff --fix, black"
	@echo "  make typecheck       Run mypy"
	@echo "  make test            Run pytest"
	@echo "  make run             Run Compliance"

$(VENVDIR):
	$(PY) -m venv $(VENVDIR)

.PHONY: all
all: clean deps install-dev docs lint format typecheck
	$(ACTIVATE); pytest -q

.PHONY: setup
setup: clean deps install-dev

.PHONY: deps
deps:
	bash install-python-deps.sh

.PHONY: ci
ci: install-dev
	$(ACTIVATE); ruff check .
	$(ACTIVATE); black --check --diff .
	$(ACTIVATE); codespell
	$(ACTIVATE); mypy
	$(ACTIVATE); pytest -q

.PHONY: clean
clean:
	rm -rf .pytest_cache .mypy_cache **/__pycache__ docs/_build dist build *.egg-info .venv docs/_autosummary

.PHONY: venv
venv: $(VENVDIR)
	@echo "Virtualenv created in $(VENVDIR)"

.PHONY: install-dev
install-dev: venv
	$(ACTIVATE); $(PIP) install --upgrade pip
	$(ACTIVATE); $(PIP) install -e .[$(DEV_EXTRAS)]

.PHONY: docs
docs: install-dev
	$(ACTIVATE); sphinx-build -a -E -b html docs docs/_build/html

.PHONY: lint
lint: install-dev
	$(ACTIVATE); ruff check .
	$(ACTIVATE); black --check --diff .
	$(ACTIVATE); codespell

.PHONY: format
format: install-dev
	$(ACTIVATE); ruff check --fix --select I .
	$(ACTIVATE); black .

.PHONY: typecheck
typecheck: install-dev
	$(ACTIVATE); mypy

.PHONY: test
test: install-dev
	$(ACTIVATE); pytest -q

.PHONY: run
run:
	$(ACTIVATE); compliance