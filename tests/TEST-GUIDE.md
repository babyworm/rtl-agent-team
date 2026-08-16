> **한국어 문서**: [TEST-GUIDE_kr.md](./TEST-GUIDE_kr.md)

# rtl-agent-team test guide

## Overview

This document describes the test infrastructure of the `rtl-agent-team` Claude Code
plugin. The tests are **pytest**-based and split into two tiers: **unit tests**,
which run without EDA tools, and **integration tests**, which require them.

### Test inventory

| Category | Tests | Status |
|----------|-------|--------|
| Unit tests | 1641 | No EDA tools required |
| Integration tests | 47 | SKIPped depending on the EDA/Docker environment |
| **Total** | **1688** | at collection |

---

## Directory structure

```
tests/
├── conftest.py                    # Shared fixtures and helpers
├── Makefile                       # make test, make unit, make integration, …
├── requirements-test.txt          # All test dependencies
├── TEST-GUIDE.md                  # This document
├── unit/                          # No EDA tools — runs locally as-is
│   ├── test_agent_skill_structure.py  # Agent/skill structure validation
│   ├── test_aws_batch.py              # AWS Batch job management (boto3 mocked)
│   ├── test_bd_rate.py                # BD-rate/BD-PSNR maths
│   ├── test_build_scripts.py          # build_encoder.sh, build_decoder.sh
│   ├── test_check_conventions.py      # RTL coding convention checker
│   ├── test_compare_output.py         # MD5/bitexact comparison
│   ├── test_hooks.py                  # Hook scripts (edit-tracker, stop-gate)
│   ├── test_json_schemas.py           # JSON configuration structure
│   ├── test_plugin_runtime_contract.py # Plugin runtime contract
│   ├── test_parse_yosys_stat.py       # Yosys synthesis report parsing
│   ├── test_regression_coverage.py    # regression/coverage scripts
│   ├── test_run_conformance.py        # Conformance stream discovery
│   ├── test_run_eval.py               # Encoder output parsing, BD-rate config
│   └── test_run_sim_args.py           # run_sim.sh argument validation
└── integration/                   # EDA tools required (Docker environment)
    ├── conftest.py                # requires_iverilog, requires_verilator, …
    ├── test_docker_build.py       # Docker image build + EDA tool validation (33 tests)
    ├── test_lint_live.py          # Real verilator/verible lint
    ├── test_sim_live.py           # Real iverilog/verilator simulation
    └── test_synth_live.py         # Real yosys synthesis
```

---

## Running the tests

### Prerequisites

```bash
python3 -m venv .venv
".venv/bin/python" -m pip install -r tests/requirements-test.txt
. .venv/bin/activate
```

### Run everything

```bash
# From the project root
python3 -m pytest tests/ -v

# Or via the Makefile
cd tests && make test
```

### Unit tests only

```bash
python3 -m pytest tests/unit/ -v

# Or
cd tests && make unit
```

### Integration tests only (Docker/EDA environment)

```bash
python3 -m pytest tests/integration/ -v

# Or
cd tests && make integration
```

### A single file

```bash
python3 -m pytest tests/unit/test_hooks.py -v
python3 -m pytest tests/unit/test_plugin_runtime_contract.py -v
```

### Parallel (fast)

```bash
python3 -m pytest tests/unit/ -n auto
```

---

## What each suite covers

### 1. Hook script tests (`test_hooks.py`)

Validates the **hook system**, the plugin's central enforcement mechanism.

| Hook | Role | What is tested |
|------|------|----------------|
| `rtl-edit-tracker.sh` | Track RTL file (.sv/.svh/.v/.vh) edits + Phase 6 stale detection | Extension filtering, duplicate suppression, counts, Phase 6 markers |
| `rtl-verify-stop-gate.sh` | Block session stop after an RTL edit until verification completes | Block/allow conditions, cleanup |
| `stop-gate.sh` | Block session stop while autopilot is running | Blocking based on state file presence |
| `rtl-p6-cascade-gate.sh` | Force cascade re-review when RTL changes after Phase 6 | Stale marker, cascade-done, block/allow |
| `rtl-skill-activation.sh` | Create completion state on skill invocation (PreToolUse:Skill) | State file creation, re-entry prevention, criteria loading |
| `rtl-skill-completion-gate.sh` | Block session stop before a skill completes (Stop) | Escalation ladder (`N→2N→last-chance→user escalation`), repeat counting, staleness, cleanup |

**How it works:** hooks read JSON on stdin and print `{"continue": true/false}` JSON
on stdout. The tests run the real shell script through the `run_hook()` helper and
validate the output JSON.

### 2. Python script tests

| Test file | Script under test | What it checks |
|-----------|-------------------|----------------|
| `test_bd_rate.py` | `bd_rate.py` | BD-rate/BD-PSNR numerical accuracy, edge cases |
| `test_parse_yosys_stat.py` | `parse_yosys_stat.py` | Yosys report parsing, latch detection, empty designs |
| `test_compare_output.py` | `compare_output.py` | MD5 comparison, bitexact verdict, missing-file handling |
| `test_run_eval.py` | `run_eval.py` | Encoder output parsing, chroma weighting, custom patterns |
| `test_run_conformance.py` | `run_conformance.py` | Stream discovery, MD5 computation, decoding result structure, profile/level filters |
| `test_aws_batch.py` | `aws_batch_conformance.py` | AWS Batch submit/wait/results (boto3 mocked) |

### 3. Bash script tests

| Test file | Script under test | What it checks |
|-----------|-------------------|----------------|
| `test_run_sim_args.py` | `run_sim.sh` | Simulator argument validation, help output, unsupported options |
| `test_check_conventions.py` | `check_conventions.sh` | RTL coding convention checks (3 bugs documented) |
| `test_build_scripts.py` | `build_encoder.sh`, `build_decoder.sh` | Build argument validation, real compilation |
| `test_regression_coverage.py` | `run_regression.sh`, `merge_coverage.sh` | Regression arguments, coverage merging |

### 4. Structure tests (`test_agent_skill_structure.py`)

Validates the plugin's **declarative structure**.

| Check | Description |
|-------|-------------|
| Agent YAML frontmatter | `name`, `model`, `description` present on all 99 agents |
| Agent name ↔ filename | `agents/rtl-coder.md` declares `name: rtl-coder` |
| `agents/` stays flat | No nested `.md`; a nested file would be registered as a phantom agent |
| Skill SKILL.md exists | Every one of the 97 skill directories has a `SKILL.md` |
| Skill name ↔ directory | `skills/rtl-p4-implement/SKILL.md` declares `name: rtl-p4-implement` |
| Skill description budget | ≤160 chars per skill and ≤15 KB in total — the harness silently truncates once the global budget is exceeded |
| Skill asset paths | Skill-relative asset paths resolve, and no prompt reads a plugin-internal path that is absent at runtime |
| CLAUDE.md cross-references | Core agents/skills actually exist |
| hooks.json structure | PostToolUse and Stop event hook configuration |
| plugin.json structure | Plugin name, version, description |

### 5. JSON schema tests (`test_json_schemas.py`)

| Check | File |
|-------|------|
| hooks.json | Hook events, matchers, command structure |
| plugin.json | Plugin metadata |
| autopilot-state.json | Phase 1-6 state template |
| context-preload | Per-phase context preload structure |
| conformance-config.json | Conformance test configuration |
| domain manifest | Domain package manifest |

### 6. Plugin runtime contract tests (`test_plugin_runtime_contract.py`)

Validates that the plugin behaves as expected inside the real Claude Code runtime.

| Check | Description |
|-------|-------------|
| Hook event contract | `SessionStart/PostToolUse/PreToolUse/Stop` event keys, matchers, hook ordering, timeout ranges |
| Hook path contract | Hook commands follow the `${CLAUDE_PLUGIN_ROOT}/hooks/*.sh` pattern and the scripts exist |
| Manifest consistency | `plugin.json` and `marketplace.json` agree on version/homepage/repository/source/path |
| SessionStart routing contract | Action Skills are user-invocable, Convention Skills are not, internal orchestrator routes stay unexposed |
| Pipeline rule coverage | Every rule declared in CLAUDE.md reaches both the rtl-orchestrate body and the SessionStart injection |
| Agent delegation contract | Every agent named in the SessionStart delegation table exists as `agents/*.md` and does not collide with a skill name |

### 7. Docker build + EDA tool validation (`test_docker_build.py`)

Builds an image from `docker/Dockerfile` and checks that every EDA tool is usable
inside the container.

| Class | Tests | What it checks |
|-------|-------|----------------|
| `TestDockerBuild` | 2 | Image builds, `/workspace` directory present |
| `TestEDAToolsAvailable` | 25 | Per-tool version checks (table below) |
| `TestDockerToolchain` | 6 | Real compile/simulate end-to-end |

**EDA tools validated:**

| Category | Tool | Method |
|----------|------|--------|
| Simulators | Verilator 5.x, Icarus Verilog | `--version`, real SV compile |
| Synthesis | Yosys | `--version`, real synthesis run |
| Lint | Verilator lint, Verible, slang | `--version`, lint mode |
| Formal | SymbiYosys, Z3, Boolector | `--version` / `--help` |
| SystemC | SystemC 3.x headers/libraries | Header presence, real compile + run |
| Python | cocotb, cocotb-bus, cocotbext-axi, cocotb-coverage, numpy | `import` check |
| Build tools | gcc, g++, cmake, make | `--version` |
| Waveform viewer | GTKWave | `which gtkwave` |
| LSP | slang-server | `--version` |

**How to run:**

```bash
# The Docker daemon must be running
python3 -m pytest tests/integration/test_docker_build.py -v --timeout=3600

# Or via the Makefile
cd tests && make test-docker
```

> **Note:** the first build compiles Verilator, slang and others from source and
> takes 10-30 minutes. Later runs are fast thanks to the Docker cache. Without a
> Docker daemon all 33 tests SKIP.

---

## Test architecture principles

### Mock/stub strategy

```
Unit tests                         Integration tests
┌──────────────┐                  ┌──────────────┐
│ Python funcs │  direct import   │  real EDA    │
│ Bash scripts │  subprocess      │  tool runs   │
│ boto3 mock   │  MagicMock       │  Docker env  │
└──────────────┘                  └──────────────┘
   no EDA tools needed               EDA tools required
   runs locally right away           CI/CD or Docker
```

- **Python functions**: imported directly after adding the script directory to `sys.path`
- **Bash scripts**: executed with `subprocess.run()`, validating returncode/stdout/stderr
- **AWS SDK**: the boto3 client is replaced with `unittest.mock.MagicMock`
- **Hook scripts**: the `run_hook()` helper — stdin JSON → shell run → stdout JSON parse

### Bugs found (documented by tests)

| ID | File | Description | Status |
|----|------|-------------|--------|
| BUG-001 | `check_conventions.sh` | `((VIOLATIONS++))` combined with `set -e` caused an early exit | **FIXED** |
| BUG-002 | `check_conventions.sh` | The `grep -n` line-number prefix bypassed the module filter | **FIXED** |
| BUG-003 | `check_conventions.sh` | Rule 5 filtered only the first token, so `unique case (x)` was reported as an instance named `case`; the same pattern never matched a parameterized instantiation | **FIXED** |
| LIM-001 | `parse_yosys_stat.py` | In the legacy `Number of ...` format, wire counts before the section start are not parsed | documented |

---

## CI/CD integration

### GitHub Actions example

```yaml
name: Plugin Tests
on: [push, pull_request]
jobs:
  unit-tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python3 -m pip install -r tests/requirements-test.txt
      - run: python3 -m pytest tests/unit/ -v --tb=short

  integration-tests:
    runs-on: ubuntu-latest
    container:
      image: your-eda-docker-image:latest  # includes iverilog, verilator, yosys
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: python3 -m pip install -r tests/requirements-test.txt
      - run: python3 -m pytest tests/integration/ -v --tb=short
```

---

## Adding a new test

### For a Python script

```python
# tests/unit/test_my_script.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "skills" / "my-skill" / "scripts"))

from my_script import my_function

def test_basic():
    assert my_function("input") == "expected"
```

### For a Bash script

```python
# tests/unit/test_my_bash.py
from tests.conftest import SCRIPTS_DIR, run_script

MY_SCRIPT = SCRIPTS_DIR / "my_script.sh"

def test_help():
    result = run_script(MY_SCRIPT, "--help")
    assert result.returncode == 0
    assert "Usage" in result.stdout
```

### For a hook script

```python
# tests/unit/test_my_hook.py
from tests.conftest import HOOKS_DIR, run_hook

MY_HOOK = HOOKS_DIR / "my-hook.sh"

def test_allows_continue(tmp_project):
    result = run_hook(MY_HOOK, {"cwd": str(tmp_project)})
    assert result["continue"] is True
```

---

## FAQ

**Q: All the integration tests SKIP — why?**
A: The EDA tools (iverilog, verilator, yosys) are not installed. Run them in a
Docker environment or install the tools.

**Q: Do the AWS tests work without boto3?**
A: Yes. The tests replace boto3 with a mock module, so behaviour is validated
without a real AWS connection.

**Q: Can the tests run in parallel?**
A: Install with `".venv/bin/python" -m pip install pytest-xdist`, then run
`".venv/bin/python" -m pytest -n auto` to use as many workers as CPU cores.

**Q: Do the tests break when I add an agent?**
A: `test_agent_skill_structure.py` validates the new agent's YAML frontmatter
automatically. It passes as long as `name`, `model` and `description` are present.

**Q: Some tests SKIP on macOS — why?**
A: `generate_config.sh` self-guards on `BASH_VERSINFO[0] >= 4`, and macOS ships bash
3.2. `tests/conftest.py::find_bash4` detects a bash ≥ 4 and skips those tests when
none is available. Install one with `brew install bash` to run them; Linux CI runs
them unconditionally.
