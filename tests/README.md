> **한국어 문서**: [README_kr.md](./README_kr.md)

# RTL Agent Team plugin test guide

## Overview

This test infrastructure validates the executable code of the `rtl-agent-team`
plugin — Bash scripts, Python scripts and hook scripts.

**Two tiers:**

| Tier | Directory | EDA tools needed | Tests | Runtime |
|------|-----------|:---:|:---:|:---:|
| Unit | `tests/unit/` | No | 1641 | ~30 s |
| Integration | `tests/integration/` | Yes (Docker/Yosys) | 47 | ~1 min on the ordinary non-Docker path; 10-30 min for the opt-in first Docker build |

Integration tests are faster when the Docker image already exists. The first
opt-in build time depends on the host and network.

## Quick start

```bash
# 1. Install dependencies
cd tests
python3 -m venv .venv
".venv/bin/python" -m pip install -r requirements-test.txt
. .venv/bin/activate

# 2. Run the unit tests (no EDA tools required)
make test-unit

# 3. Run the integration tests (in a Docker environment)
make test-integration
```

## What is tested

### Unit tests — Python scripts

| Test file | Script under test | What it checks |
|-----------|-------------------|----------------|
| `test_bd_rate.py` | `bd_rate.py` | BD-rate/BD-PSNR maths, input validation, polynomial integration, NaN handling |
| `test_parse_yosys_stat.py` | `parse_yosys_stat.py` | Yosys stat output parsing, cell counts, latch detection, PASS/FAIL verdict |
| `test_compare_output.py` | `compare_output.py` | MD5 comparison, byte-by-byte comparison, PSNR computation, golden MD5 loading |
| `test_run_eval.py` | `run_eval.py` | Encoder output parsing, chroma weighting, custom regexes, config resolution |
| `test_run_conformance.py` | `run_conformance.py` | Stream auto-discovery, profile/level filtering, DecodingResult structure |
| `test_aws_batch.py` | `aws_batch_submit.py` | Job name sanitization, boto3 mocking, S3 result retrieval, timeouts |

### Unit tests — Bash scripts

| Test file | Script under test | What it checks |
|-----------|-------------------|----------------|
| `test_check_conventions.py` | `check_conventions.sh` | Six naming rules (reg/wire, port prefixes, clock/reset naming, instance/generate prefixes) |
| `test_run_sim_args.py` | `run_sim.sh` | Argument parsing, required-value validation, filelist handling, define/param flags, simulator selection |
| `test_build_scripts.py` | `build_encoder.sh`, `build_decoder.sh` | Argument validation, source directory checks, gcc compilation (when gcc is installed), Makefile detection |
| `test_regression_coverage.py` | `run_regression.sh`, `merge_coverage.sh` | Seed execution, result reporting, coverage formats, error handling |

### Unit tests — hook scripts

| Test file | Script under test | What it checks |
|-----------|-------------------|----------------|
| `test_hooks.py` | `rtl-edit-tracker.sh` | RTL file tracking, non-RTL files ignored, duplicate suppression, file counts |
|  | `rtl-verify-stop-gate.sh` | Session stop blocked while unverified, verify-done/waiver accepted, cleanup |
|  | `stop-gate.sh` | Session stop blocked while autopilot is running |

### Unit tests — JSON configuration

| Test file | What it checks |
|-----------|----------------|
| `test_json_schemas.py` | `hooks.json` structure, `plugin.json` structure, `package.json` fields, domain manifests, and that every JSON file parses |

### Unit tests — plugin runtime contract

| Test file | What it checks |
|-----------|----------------|
| `test_plugin_runtime_contract.py` | `hooks/hooks.json` event/order/script-path/timeout contract, `.claude-plugin/plugin.json` ↔ `.claude-plugin/marketplace.json` version and path consistency, the SessionStart routing Action Skill/Convention/user-invocable contract, and existence of delegated agents |

### Integration tests

| Test file | Tools required | What it checks |
|-----------|----------------|----------------|
| `test_sim_live.py` | iverilog, verilator | Real compile + run, define propagation, filelist integration |
| `test_lint_live.py` | verilator, verible | Real lint results, warning detection |
| `test_synth_live.py` | yosys | Real synthesis, parse_yosys_stat pipeline |

## Running the tests

```bash
cd tests

# All unit tests
make test-unit

# Parallel (faster)
make test-fast

# A single category
make test-hooks           # hooks only
make test-python-scripts  # Python scripts only
make test-bash-scripts    # Bash scripts only
make test-json            # JSON validation only
make test-plugin-runtime  # plugin runtime contract

# A single test file
python3 -m pytest unit/test_bd_rate.py -v
python3 -m pytest unit/test_plugin_runtime_contract.py -v

# A single test function
python3 -m pytest unit/test_bd_rate.py::TestBdRate::test_identical_curves_zero -v

# Integration tests (in a Docker environment)
make test-integration

# Everything (unit + integration)
make test-all
```

## Writing tests

### Adding a test for a new Python script

```python
# tests/unit/test_<script>.py
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / "skills" / "<skill>" / "scripts"
sys.path.insert(0, str(SCRIPT_DIR))

from <script> import <function>

class Test<Function>:
    def test_normal_case(self):
        result = <function>(normal_input)
        assert result == expected

    def test_edge_case(self):
        result = <function>(boundary_value)
        assert ...
```

### Adding a test for a new Bash script

```python
# tests/unit/test_<script>.py
from tests.conftest import SKILLS_DIR, run_script

SCRIPT = SKILLS_DIR / "<skill>" / "scripts" / "<script>.sh"

class Test<Script>:
    def test_argument_validation(self):
        result = run_script(SCRIPT, "--bad-flag")
        assert result.returncode != 0

    def test_normal_run(self, tmp_path):
        result = run_script(SCRIPT, str(tmp_path), "--option", "value")
        assert result.returncode == 0
        assert "expected string" in result.stdout
```

### Adding a hook test

```python
# add to tests/unit/test_hooks.py
from tests.conftest import HOOKS_DIR, run_hook

class TestNewHook:
    HOOK = HOOKS_DIR / "new-hook.sh"

    def test_allows(self, tmp_project):
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_blocks(self, tmp_project):
        # set up the blocking condition
        (tmp_project / ".rat" / "state" / "block-file").touch()
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is False
```

## Bugs found

Pre-existing bugs discovered while writing the tests:

| ID | Location | Severity | Description |
|----|----------|----------|-------------|
| BUG-001 | `check_conventions.sh:17` | High | **FIXED.** `((VIOLATIONS++))` → `VIOLATIONS=$((VIOLATIONS + 1))` |
| BUG-002 | `check_conventions.sh:52` | Medium | **FIXED.** `^[0-9]+:\s*` prefix added to the `grep -vE` pattern to handle the line-number prefix |
| BUG-003 | `run_regression.sh:67` | High | **FIXED.** `((TOTAL++))` → `TOTAL=$((TOTAL + 1))` |

## Directory structure

```
tests/
├── conftest.py                  # Shared fixtures (tmp_project, run_script, run_hook, …)
├── requirements-test.txt        # pip dependencies
├── Makefile                     # Convenience targets
├── README.md                    # This document
├── unit/                        # No EDA tools required
│   ├── test_aws_batch.py        # AWS Batch (boto3 mocked)
│   ├── test_bd_rate.py          # BD-rate computation
│   ├── test_build_scripts.py    # C build scripts
│   ├── test_check_conventions.py # Naming conventions
│   ├── test_compare_output.py   # Conformance comparison
│   ├── test_hooks.py            # Three hook scripts
│   ├── test_json_schemas.py     # JSON configuration validation
│   ├── test_plugin_runtime_contract.py # Plugin runtime contract
│   ├── test_parse_yosys_stat.py # Yosys parsing
│   ├── test_regression_coverage.py # Regression / coverage
│   ├── test_run_conformance.py  # Conformance testing
│   ├── test_run_eval.py         # RD evaluation
│   └── test_run_sim_args.py     # Simulator wrapper
└── integration/                 # EDA tools required (auto-skip)
    ├── conftest.py              # requires_* markers
    ├── test_lint_live.py        # Real lint
    ├── test_sim_live.py         # Real simulation
    └── test_synth_live.py       # Real synthesis
```
