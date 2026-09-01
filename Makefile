IMAGE_NAME ?= shelly-prometheus-exporter
PYTHON ?= python3
VENV ?= .venv

.PHONY: help install install-dev test coverage compile run docker-build docker-run clean

help:
	@echo "Available targets:"
	@echo "  install       Create $(VENV) and install runtime dependencies"
	@echo "  install-dev   Install runtime + dev/test dependencies"
	@echo "  test          Run the test suite"
	@echo "  coverage      Run tests with a coverage report"
	@echo "  compile       Byte-compile the exporter package (syntax check)"
	@echo "  run           Run the exporter locally (set SHELLY_AUTH_KEY/SHELLY_SERVER_URI first)"
	@echo "  docker-build  Build the container image"
	@echo "  docker-run    Run the container image locally (set SHELLY_AUTH_KEY/SHELLY_SERVER_URI first)"
	@echo "  clean         Remove caches, build artifacts and $(VENV)"

# All Python tooling runs through this venv so `make` works on
# externally-managed systems (PEP 668) without --break-system-packages.
$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV)

$(VENV)/.installed: requirements.txt | $(VENV)/bin/python
	$(VENV)/bin/pip install -r requirements.txt
	touch $@

$(VENV)/.installed-dev: $(VENV)/.installed
	$(VENV)/bin/pip install pytest pytest-cov
	touch $@

install: $(VENV)/.installed

install-dev: $(VENV)/.installed-dev

test: install-dev
	$(VENV)/bin/pytest tests/ -v

coverage: install-dev
	$(VENV)/bin/pytest tests/ --cov=exporter --cov-report=term-missing

compile: install
	$(VENV)/bin/python -m compileall exporter

run: install
	$(VENV)/bin/python -m exporter

docker-build:
	docker build -t $(IMAGE_NAME) .

docker-run:
	docker run --rm -e SHELLY_AUTH_KEY=$(SHELLY_AUTH_KEY) -e SHELLY_SERVER_URI=$(SHELLY_SERVER_URI) -p 9100:9100 $(IMAGE_NAME)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .pytest_cache .coverage htmlcov $(VENV)
