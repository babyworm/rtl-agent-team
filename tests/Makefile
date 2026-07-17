# Makefile for rtl-agent-team plugin test suite
PYTHON ?= python3
MAKEFLAGS += --no-print-directory

.PHONY: test unit integration test-unit test-integration test-fast install-deps help test-all test-coverage test-hooks test-python-scripts test-bash-scripts test-json test-plugin-runtime test-docker

help:  ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $$1, $$2}'

install-deps:  ## Install test dependencies
	$(PYTHON) -m pip install -r requirements-test.txt

test: test-all  ## Run both unit and integration tests

unit: test-unit  ## Alias for test-unit

integration: test-integration  ## Alias for test-integration

test-unit:  ## Run unit tests (no EDA tools required)
	$(PYTHON) -m pytest unit/ -v --tb=short

test-integration:  ## Run integration tests (requires Docker/EDA tools)
	$(PYTHON) -m pytest integration/ -v --tb=short

test-fast:  ## Run unit tests in parallel
	$(PYTHON) -m pytest unit/ -v --tb=short -x -n auto

test-all:  ## Run both unit and integration tests
	$(PYTHON) -m pytest unit/ integration/ -v --tb=short

test-coverage:  ## Run unit tests with coverage report
	$(PYTHON) -m pytest unit/ -v --tb=short --cov --cov-report=term-missing

test-hooks:  ## Run only hook tests
	$(PYTHON) -m pytest unit/test_hooks.py -v --tb=short

test-python-scripts:  ## Run only Python script unit tests
	$(PYTHON) -m pytest unit/test_bd_rate.py unit/test_parse_yosys_stat.py unit/test_compare_output.py unit/test_run_eval.py -v --tb=short

test-bash-scripts:  ## Run only Bash script tests
	$(PYTHON) -m pytest unit/test_check_conventions.py unit/test_run_sim_args.py -v --tb=short

test-json:  ## Run only JSON validation tests
	$(PYTHON) -m pytest unit/test_json_schemas.py -v --tb=short

test-plugin-runtime:  ## Run plugin runtime contract tests
	$(PYTHON) -m pytest unit/test_plugin_runtime_contract.py -v --tb=short

test-docker:  ## Run Docker image build + EDA tool verification (slow)
	$(PYTHON) -m pytest integration/test_docker_build.py -v --tb=short --timeout=3600
