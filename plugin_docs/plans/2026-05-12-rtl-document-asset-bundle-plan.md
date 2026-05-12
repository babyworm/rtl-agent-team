# rtl-document Asset Bundle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Upgrade `skills/rtl-document/` to the "asset bundle pattern" with deterministic Verible-based parser, snippet-composing renderer, three worked examples, a lean SKILL.md, and CI coverage — matching the `rtl-p5s-func-verify` reference layout.

**Architecture:** Two-stage pipeline. `scripts/extract_module_doc.py` runs Verible CST export to a JSON schema (ports/params/instances/FSM-candidates/convention-violations). `scripts/render_doc.py` composes `templates/module-doc-template.md` with optional snippets and injects `<!-- LLM_FILL: ... -->` markers; LLM replaces markers using `references/doc-conventions.md` and `examples/*.md` as tone anchors.

**Tech Stack:** Python 3 stdlib only (subprocess, json, argparse, pathlib); `verible-verilog-syntax` CLI; pytest for tests; Bash for skill-side glue (already provided by the existing `Bash` allowed-tool).

**Spec:** `plugin_docs/specs/2026-05-12-rtl-document-asset-bundle-design.md`

---

## Scope

This plan covers a single skill upgrade. The remaining 10 candidate skills are out of scope and will be addressed in follow-up plans that replicate the pattern this plan establishes.

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `skills/rtl-document/scripts/extract_module_doc.py` | Create | Run Verible CST export; transform to project JSON schema. |
| `skills/rtl-document/scripts/render_doc.py` | Create | Compose `module-doc-template.md` with optional snippets; emit Markdown with `<!-- LLM_FILL: ... -->` markers. |
| `skills/rtl-document/templates/port-table-snippet.md` | Create | Port-table format reminder. |
| `skills/rtl-document/templates/fsm-section-snippet.md` | Create | FSM table + Mermaid `stateDiagram-v2` skeleton. |
| `skills/rtl-document/templates/block-diagram-snippet.d2` | Create | D2 sub-instance block diagram skeleton. |
| `skills/rtl-document/references/doc-conventions.md` | Create | Naming rules, table format, diagram tool choice, anti-patterns (≤200 lines). |
| `skills/rtl-document/examples/simple_fifo.md` | Create | Small datapath, single clock — minimal baseline (dogfooded). |
| `skills/rtl-document/examples/axi_stream_bridge.md` | Create | Two clock domains, protocol grouping (dogfooded). |
| `skills/rtl-document/examples/cabac_encoder_excerpt.md` | Create | FSM-heavy, sub-instance tree (dogfooded). |
| `skills/rtl-document/SKILL.md` | Rewrite | Replace 107-line body with the §5.4 spec draft (~95 lines). |
| `tests/fixtures/rtl-document/simple_fifo.sv` | Create | Fixture SV — small module. |
| `tests/fixtures/rtl-document/axi_stream_bridge.sv` | Create | Fixture SV — two clock domains. |
| `tests/fixtures/rtl-document/cabac_encoder_excerpt.sv` | Create | Fixture SV — FSM + sub-instances. |
| `tests/fixtures/rtl-document/synth_report.txt` | Create | Fixture synthesis report. |
| `tests/unit/test_extract_module_doc.py` | Create | Parser unit tests against fixtures. |
| `tests/unit/test_render_doc.py` | Create | Renderer unit tests with synthetic JSON. |
| `tests/unit/test_rtl_document_examples.py` | Create | Regression: every example file has zero stray markers. |
| `plugin_docs/plans/2026-03-20-skill-improvement-candidates.md` | Modify | Mark `rtl-document` complete; point future skills at this plan as reference. |

---

## Task 1: Bootstrap directory layout and fixtures

**Files:**
- Create: `skills/rtl-document/scripts/.gitkeep`
- Create: `skills/rtl-document/references/.gitkeep`
- Create: `skills/rtl-document/examples/.gitkeep`
- Create: `tests/fixtures/rtl-document/simple_fifo.sv`
- Create: `tests/fixtures/rtl-document/axi_stream_bridge.sv`
- Create: `tests/fixtures/rtl-document/cabac_encoder_excerpt.sv`
- Create: `tests/fixtures/rtl-document/synth_report.txt`

- [ ] **Step 1: Create directory skeleton**

```bash
mkdir -p skills/rtl-document/{scripts,references,examples}
touch skills/rtl-document/scripts/.gitkeep
touch skills/rtl-document/references/.gitkeep
touch skills/rtl-document/examples/.gitkeep
mkdir -p tests/fixtures/rtl-document
```

- [ ] **Step 2: Write `tests/fixtures/rtl-document/simple_fifo.sv`**

```systemverilog
module simple_fifo #(
  parameter int DATA_WIDTH = 32,
  parameter int DEPTH      = 16
) (
  input  logic                  sys_clk,
  input  logic                  sys_rst_n,
  input  logic                  i_push,
  input  logic [DATA_WIDTH-1:0] i_data,
  input  logic                  i_pop,
  output logic [DATA_WIDTH-1:0] o_data,
  output logic                  o_full,
  output logic                  o_empty
);
  logic [DATA_WIDTH-1:0] mem [0:DEPTH-1];
endmodule
```

- [ ] **Step 3: Write `tests/fixtures/rtl-document/axi_stream_bridge.sv`**

```systemverilog
module axi_stream_bridge #(
  parameter int DATA_WIDTH = 64
) (
  input  logic                  sys_clk,
  input  logic                  sys_rst_n,
  input  logic                  pixel_clk,
  input  logic                  pixel_rst_n,
  // APB control (sys domain)
  input  logic                  i_psel,
  input  logic                  i_penable,
  input  logic [31:0]           i_paddr,
  // AXI-Stream egress (pixel domain)
  output logic [DATA_WIDTH-1:0] o_tdata,
  output logic                  o_tvalid,
  input  logic                  i_tready
);
  async_fifo #(.WIDTH(DATA_WIDTH)) u_ingress_fifo (.*);
  async_fifo #(.WIDTH(DATA_WIDTH)) u_egress_fifo  (.*);
endmodule
```

- [ ] **Step 4: Write `tests/fixtures/rtl-document/cabac_encoder_excerpt.sv`**

```systemverilog
module cabac_encoder_excerpt #(
  parameter int CTX_WIDTH = 7
) (
  input  logic                  sys_clk,
  input  logic                  sys_rst_n,
  input  logic                  i_valid,
  input  logic [CTX_WIDTH-1:0]  i_ctx_idx,
  input  logic                  i_bin,
  output logic [7:0]            o_byte,
  output logic                  o_byte_valid
);
  typedef enum logic [1:0] {
    ST_IDLE   = 2'd0,
    ST_ENCODE = 2'd1,
    ST_FLUSH  = 2'd2
  } state_e;

  state_e state, next_state;

  range_coder        u_range_coder        (.*);
  context_memory     u_context_memory     (.*);
  bypass_encoder     u_bypass_encoder     (.*);

  always_ff @(posedge sys_clk or negedge sys_rst_n) begin
    if (!sys_rst_n) state <= ST_IDLE;
    else            state <= next_state;
  end
endmodule
```

- [ ] **Step 5: Write `tests/fixtures/rtl-document/synth_report.txt`**

```
=== Area Report ===
Total cell area: 12450.30 um^2

=== Timing Report ===
WNS: 0.21 ns
TNS: -3.40 ns
Number of violating paths: 2
```

- [ ] **Step 6: Commit**

```bash
git add skills/rtl-document/scripts/.gitkeep skills/rtl-document/references/.gitkeep skills/rtl-document/examples/.gitkeep tests/fixtures/rtl-document/
git commit -m "test(rtl-document): bootstrap directory + SV/synth fixtures"
```

---

## Task 2: `extract_module_doc.py` — skeleton + Verible invocation

**Files:**
- Create: `skills/rtl-document/scripts/extract_module_doc.py`
- Create: `tests/unit/test_extract_module_doc.py`

- [ ] **Step 1: Write the failing test for CLI skeleton**

`tests/unit/test_extract_module_doc.py`:

```python
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "rtl-document" / "scripts" / "extract_module_doc.py"
FIXTURES = ROOT / "tests" / "fixtures" / "rtl-document"


def _run(args, env=None):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True, text=True, env=env
    )


def test_cli_help_exits_zero():
    r = _run(["--help"])
    assert r.returncode == 0
    assert "--rtl" in r.stdout
    assert "--out" in r.stdout


def test_missing_verible_returns_exit_code_2(tmp_path, monkeypatch):
    # Simulate verible-not-on-PATH: clear PATH.
    env = os.environ.copy()
    env["PATH"] = ""
    out = tmp_path / "x.json"
    r = _run(["--rtl", str(FIXTURES / "simple_fifo.sv"), "--out", str(out)], env=env)
    assert r.returncode == 2
    assert "verible" in r.stderr.lower()
```

- [ ] **Step 2: Run tests and verify they fail**

```bash
python3 -m pytest tests/unit/test_extract_module_doc.py -v
```

Expected: 2 failures with "FileNotFoundError" for the script.

- [ ] **Step 3: Implement minimal `extract_module_doc.py`**

`skills/rtl-document/scripts/extract_module_doc.py`:

```python
#!/usr/bin/env python3
"""Extract deterministic structure from a SystemVerilog module using Verible.

Output schema (top-level keys):
  module_name, file, parameters, ports, instances, fsm_candidates,
  clock_domains, convention_violations, synth_summary

Exit codes:
  0  success
  2  verible-verilog-syntax not on PATH
  3  SV parse error
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

VERIBLE_BIN = "verible-verilog-syntax"


def find_verible() -> str | None:
    return shutil.which(VERIBLE_BIN)


def main() -> int:
    p = argparse.ArgumentParser(description="Extract RTL module structure via Verible.")
    p.add_argument("--rtl", required=True, help="Path to <module>.sv")
    p.add_argument("--syn-report", help="Optional path to syn/synth_report.txt")
    p.add_argument("--out", help="Output JSON path (default: stdout)")
    args = p.parse_args()

    verible = find_verible()
    if verible is None:
        print(f"error: {VERIBLE_BIN} not found on PATH; install verible or use rtl-explorer fallback",
              file=sys.stderr)
        return 2

    # Stubbed: real CST processing comes in Task 3+.
    payload = {
        "module_name": Path(args.rtl).stem,
        "file": args.rtl,
        "parameters": [],
        "ports": [],
        "instances": [],
        "fsm_candidates": [],
        "clock_domains": [],
        "convention_violations": [],
    }
    text = json.dumps(payload, indent=2)
    if args.out:
        Path(args.out).write_text(text)
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
python3 -m pytest tests/unit/test_extract_module_doc.py -v
```

Expected: 2 passing.

- [ ] **Step 5: Commit**

```bash
git add skills/rtl-document/scripts/extract_module_doc.py tests/unit/test_extract_module_doc.py
git commit -m "feat(rtl-document): extractor CLI skeleton + verible-missing exit 2"
```

---

## Task 3: `extract_module_doc.py` — port and parameter extraction

**Files:**
- Modify: `skills/rtl-document/scripts/extract_module_doc.py`
- Modify: `tests/unit/test_extract_module_doc.py`

- [ ] **Step 1: Add failing tests for ports and parameters**

Append to `tests/unit/test_extract_module_doc.py`:

```python
VERIBLE_AVAILABLE = shutil.which("verible-verilog-syntax") is not None
needs_verible = pytest.mark.skipif(not VERIBLE_AVAILABLE, reason="verible not installed")


@needs_verible
def test_simple_fifo_ports(tmp_path):
    out = tmp_path / "simple_fifo.json"
    r = _run(["--rtl", str(FIXTURES / "simple_fifo.sv"), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    data = json.loads(out.read_text())
    assert data["module_name"] == "simple_fifo"
    names = [p["name"] for p in data["ports"]]
    assert names == [
        "sys_clk", "sys_rst_n", "i_push", "i_data", "i_pop", "o_data", "o_full", "o_empty"
    ]
    # clock/reset tagged correctly
    by_name = {p["name"]: p for p in data["ports"]}
    assert by_name["sys_clk"]["kind"] == "clock"
    assert by_name["sys_clk"]["domain"] == "sys"
    assert by_name["sys_rst_n"]["kind"] == "reset"
    assert by_name["i_push"]["kind"] == "data"
    assert by_name["i_data"]["dir"] == "input"
    assert by_name["o_full"]["dir"] == "output"


@needs_verible
def test_simple_fifo_parameters(tmp_path):
    out = tmp_path / "x.json"
    _run(["--rtl", str(FIXTURES / "simple_fifo.sv"), "--out", str(out)])
    data = json.loads(out.read_text())
    pnames = {p["name"]: p for p in data["parameters"]}
    assert pnames["DATA_WIDTH"]["default"] == "32"
    assert pnames["DEPTH"]["default"] == "16"
```

- [ ] **Step 2: Run tests and verify they fail**

```bash
python3 -m pytest tests/unit/test_extract_module_doc.py -v
```

Expected: 2 new failures (assertion mismatch on empty arrays).

- [ ] **Step 3: Implement port and parameter extraction**

Replace the stubbed `payload` block in `extract_module_doc.py` with:

```python
import re

PORT_RE = re.compile(
    r"^\s*(input|output|inout)\s+(?:logic|wire|reg)?\s*"
    r"(\[[^\]]+\])?\s*"
    r"([A-Za-z_][A-Za-z_0-9$\\]*)\s*[,)]",
)
PARAM_RE = re.compile(
    r"parameter\s+(?:int|logic|bit)?\s*([A-Z_][A-Z_0-9]*)\s*=\s*([^,)\n]+)"
)
CLOCK_RE = re.compile(r"^(.+)_clk$")
RESET_RE = re.compile(r"^(.+)_rst_n$")


def _classify(name: str) -> tuple[str, str | None]:
    m = CLOCK_RE.match(name)
    if m:
        return "clock", m.group(1)
    m = RESET_RE.match(name)
    if m:
        return "reset", m.group(1)
    return "data", None


def _verible_json(verible: str, rtl: str) -> dict:
    r = subprocess.run(
        [verible, "--export_json", rtl],
        capture_output=True, text=True, check=False,
    )
    if r.returncode != 0:
        return {"_error": r.stderr}
    return json.loads(r.stdout)


def _parse_text(rtl_path: Path) -> dict:
    """Fallback regex-based parser; used both standalone and to augment CST when fields missing."""
    text = rtl_path.read_text()
    module_name = rtl_path.stem
    m = re.search(r"module\s+([A-Za-z_][A-Za-z_0-9]*)\s*[#(]", text)
    if m:
        module_name = m.group(1)
    ports = []
    domains: set[str] = set()
    for line in text.splitlines():
        pm = PORT_RE.match(line)
        if pm:
            direction, width, name = pm.group(1), pm.group(2), pm.group(3)
            kind, domain = _classify(name)
            if domain:
                domains.add(domain)
            width_int = 1
            if width:
                wm = re.match(r"\[\s*([^:]+)\s*-\s*1\s*:\s*0\s*\]", width)
                if wm:
                    width_int = wm.group(1).strip()
            ports.append({
                "name": name, "dir": direction, "width": width_int,
                "domain": domain or "?", "kind": kind,
            })
    params = [
        {"name": pm.group(1).strip(), "type": "int", "default": pm.group(2).strip()}
        for pm in PARAM_RE.finditer(text)
    ]
    return {
        "module_name": module_name,
        "file": str(rtl_path),
        "parameters": params,
        "ports": ports,
        "instances": [],
        "fsm_candidates": [],
        "clock_domains": sorted(domains),
        "convention_violations": [],
    }


# In main():
def main() -> int:
    # ... argparse same as before ...
    verible = find_verible()
    if verible is None:
        print(f"error: {VERIBLE_BIN} not found on PATH; install verible or use rtl-explorer fallback",
              file=sys.stderr)
        return 2
    cst = _verible_json(verible, args.rtl)
    if "_error" in cst:
        print(f"error: SV parse failure:\n{cst['_error']}", file=sys.stderr)
        return 3
    payload = _parse_text(Path(args.rtl))
    # (CST integration deepened in Task 4+; regex parser already meets the schema.)
    text = json.dumps(payload, indent=2)
    if args.out:
        Path(args.out).write_text(text)
    else:
        print(text)
    return 0
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
python3 -m pytest tests/unit/test_extract_module_doc.py -v
```

Expected: 4 passing (2 prior + 2 new). On systems without verible the 2 verible-gated tests skip.

- [ ] **Step 5: Commit**

```bash
git add skills/rtl-document/scripts/extract_module_doc.py tests/unit/test_extract_module_doc.py
git commit -m "feat(rtl-document): extract ports + parameters with clock/reset classification"
```

---

## Task 4: `extract_module_doc.py` — instances, FSM candidates, parse errors

**Files:**
- Modify: `skills/rtl-document/scripts/extract_module_doc.py`
- Modify: `tests/unit/test_extract_module_doc.py`

- [ ] **Step 1: Add failing tests**

```python
@needs_verible
def test_axi_bridge_instances(tmp_path):
    out = tmp_path / "x.json"
    _run(["--rtl", str(FIXTURES / "axi_stream_bridge.sv"), "--out", str(out)])
    data = json.loads(out.read_text())
    inst_names = sorted(i["name"] for i in data["instances"])
    assert inst_names == ["u_egress_fifo", "u_ingress_fifo"]
    assert sorted(data["clock_domains"]) == ["pixel", "sys"]


@needs_verible
def test_cabac_fsm_candidates(tmp_path):
    out = tmp_path / "x.json"
    _run(["--rtl", str(FIXTURES / "cabac_encoder_excerpt.sv"), "--out", str(out)])
    data = json.loads(out.read_text())
    assert len(data["fsm_candidates"]) >= 1
    fsm = data["fsm_candidates"][0]
    assert fsm["state_register"] == "state"
    assert sorted(fsm["states"]) == ["ST_ENCODE", "ST_FLUSH", "ST_IDLE"]


@needs_verible
def test_parse_error_returns_exit_3(tmp_path):
    bad = tmp_path / "bad.sv"
    bad.write_text("module bad ( oops\n")  # unterminated
    out = tmp_path / "x.json"
    r = _run(["--rtl", str(bad), "--out", str(out)])
    assert r.returncode == 3
    assert "parse" in r.stderr.lower() or "syntax" in r.stderr.lower()
```

- [ ] **Step 2: Run tests and verify they fail**

```bash
python3 -m pytest tests/unit/test_extract_module_doc.py -v
```

Expected: 3 new failures.

- [ ] **Step 3: Extend `_parse_text` with instances and FSM**

Add to `extract_module_doc.py`:

```python
INSTANCE_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z_0-9]*)\s*(?:#\([^)]*\))?\s+(u_[A-Za-z_0-9]+)\s*\(",
    re.MULTILINE,
)
ENUM_RE = re.compile(
    r"typedef\s+enum\b[^{]*\{(?P<body>[^}]+)\}\s*(?P<type>[A-Za-z_][A-Za-z_0-9]*)\s*;",
    re.DOTALL,
)
STATE_REG_RE = re.compile(
    r"(?P<type>[A-Za-z_][A-Za-z_0-9]*)\s+(?P<name>[A-Za-z_][A-Za-z_0-9]*)\s*,\s*next_\w+\s*;",
)
```

Update `_parse_text` body to populate `instances` and `fsm_candidates`:

```python
def _parse_text(rtl_path: Path) -> dict:
    text = rtl_path.read_text()
    # ... existing module_name, ports, params ...
    instances = [
        {"name": m.group(2), "module": m.group(1)}
        for m in INSTANCE_RE.finditer(text)
        if m.group(1) not in {"module", "input", "output", "inout", "logic", "wire", "reg"}
    ]
    enums = {m.group("type"): [s.split("=")[0].strip()
                               for s in m.group("body").split(",")
                               if s.strip()]
             for m in ENUM_RE.finditer(text)}
    fsm_candidates = []
    for sr in STATE_REG_RE.finditer(text):
        states = enums.get(sr.group("type"))
        if states:
            fsm_candidates.append({
                "state_register": sr.group("name"),
                "type_name": sr.group("type"),
                "states": states,
            })
    return {
        # ... module_name, file, parameters, ports as before ...
        "instances": instances,
        "fsm_candidates": fsm_candidates,
        # clock_domains, convention_violations as before ...
    }
```

- [ ] **Step 4: Wire `_verible_json` error to exit 3**

In `main()`, after `_verible_json`:

```python
if "_error" in cst:
    print(f"error: SV parse failure:\n{cst['_error']}", file=sys.stderr)
    return 3
```

(Already in place from Task 3 — confirm.)

- [ ] **Step 5: Run tests and verify they pass**

```bash
python3 -m pytest tests/unit/test_extract_module_doc.py -v
```

Expected: 7 passing total.

- [ ] **Step 6: Commit**

```bash
git add skills/rtl-document/scripts/extract_module_doc.py tests/unit/test_extract_module_doc.py
git commit -m "feat(rtl-document): instance + FSM-candidate + parse-error exit handling"
```

---

## Task 5: `extract_module_doc.py` — convention violations + synthesis summary

**Files:**
- Modify: `skills/rtl-document/scripts/extract_module_doc.py`
- Modify: `tests/unit/test_extract_module_doc.py`

- [ ] **Step 1: Add failing tests**

```python
@needs_verible
def test_convention_violation_suffix_port(tmp_path):
    bad = tmp_path / "bad_naming.sv"
    bad.write_text(
        "module bad_naming ( input logic sys_clk, input logic sys_rst_n, "
        "input logic data_i, output logic data_o ); endmodule\n"
    )
    out = tmp_path / "x.json"
    _run(["--rtl", str(bad), "--out", str(out)])
    data = json.loads(out.read_text())
    sigs = {v["signal"] for v in data["convention_violations"]}
    assert sigs == {"data_i", "data_o"}


@needs_verible
def test_synth_summary(tmp_path):
    out = tmp_path / "x.json"
    _run([
        "--rtl", str(FIXTURES / "simple_fifo.sv"),
        "--syn-report", str(FIXTURES / "synth_report.txt"),
        "--out", str(out),
    ])
    data = json.loads(out.read_text())
    assert data["synth_summary"]["area_um2"] == 12450.30
    assert data["synth_summary"]["wns_ns"] == 0.21
    assert data["synth_summary"]["tns_ns"] == -3.40
```

- [ ] **Step 2: Run tests and verify they fail**

```bash
python3 -m pytest tests/unit/test_extract_module_doc.py -v
```

Expected: 2 new failures.

- [ ] **Step 3: Implement convention check and synth summary**

Add to `extract_module_doc.py`:

```python
SUFFIX_VIOLATION_RE = re.compile(r"^[A-Za-z_][A-Za-z_0-9]*_(i|o|io)$")


def _check_violations(ports: list[dict]) -> list[dict]:
    violations = []
    for p in ports:
        if SUFFIX_VIOLATION_RE.match(p["name"]):
            violations.append({
                "signal": p["name"],
                "rule": "Use i_/o_/io_ prefix (not suffix)",
            })
    return violations


def _parse_synth_report(path: Path) -> dict:
    text = path.read_text()
    out: dict = {}
    m = re.search(r"Total cell area:\s*([0-9.]+)", text)
    if m: out["area_um2"] = float(m.group(1))
    m = re.search(r"WNS:\s*(-?[0-9.]+)", text)
    if m: out["wns_ns"] = float(m.group(1))
    m = re.search(r"TNS:\s*(-?[0-9.]+)", text)
    if m: out["tns_ns"] = float(m.group(1))
    m = re.search(r"Number of violating paths:\s*(\d+)", text)
    if m: out["num_violating_paths"] = int(m.group(1))
    return out
```

In `_parse_text` return dict, replace `"convention_violations": []` with:

```python
"convention_violations": _check_violations(ports),
```

In `main()` after `payload = _parse_text(...)`:

```python
if args.syn_report:
    payload["synth_summary"] = _parse_synth_report(Path(args.syn_report))
```

- [ ] **Step 4: Run tests and verify they pass**

```bash
python3 -m pytest tests/unit/test_extract_module_doc.py -v
```

Expected: 9 passing total.

- [ ] **Step 5: Commit**

```bash
git add skills/rtl-document/scripts/extract_module_doc.py tests/unit/test_extract_module_doc.py
git commit -m "feat(rtl-document): convention-violation detection + synth-report parsing"
```

---

## Task 6: `render_doc.py` — skeleton, template-dir composition, markers

**Files:**
- Create: `skills/rtl-document/scripts/render_doc.py`
- Create: `tests/unit/test_render_doc.py`

- [ ] **Step 1: Write the failing test**

`tests/unit/test_render_doc.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "rtl-document" / "scripts" / "render_doc.py"
TEMPLATE_DIR = ROOT / "skills" / "rtl-document" / "templates"


def _run(args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)


def test_help_exits_zero():
    r = _run(["--help"])
    assert r.returncode == 0
    assert "--template-dir" in r.stdout


def test_minimal_render_no_optional_sections(tmp_path):
    payload = {
        "module_name": "simple_fifo",
        "file": "rtl/simple_fifo/simple_fifo.sv",
        "parameters": [{"name": "DATA_WIDTH", "type": "int", "default": "32"}],
        "ports": [
            {"name": "sys_clk",   "dir": "input",  "width": 1,  "domain": "sys", "kind": "clock"},
            {"name": "sys_rst_n", "dir": "input",  "width": 1,  "domain": "sys", "kind": "reset"},
            {"name": "i_data",    "dir": "input",  "width": 32, "domain": "sys", "kind": "data"},
        ],
        "instances": [],
        "fsm_candidates": [],
        "clock_domains": ["sys"],
        "convention_violations": [],
    }
    jpath = tmp_path / "x.json"
    jpath.write_text(json.dumps(payload))
    out = tmp_path / "doc.md"
    r = _run(["--json", str(jpath), "--template-dir", str(TEMPLATE_DIR), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    body = out.read_text()
    # No FSM section
    assert "FSM States" not in body
    # No D2 block diagram
    assert "```d2" not in body
    # Port table present
    assert "i_data" in body
    # LLM_FILL marker for functional description present
    assert "LLM_FILL: functional description" in body


def test_fsm_and_diagram_when_present(tmp_path):
    payload = {
        "module_name": "cabac_encoder",
        "file": "rtl/cabac/cabac.sv",
        "parameters": [],
        "ports": [
            {"name": "sys_clk", "dir": "input", "width": 1, "domain": "sys", "kind": "clock"},
        ],
        "instances": [
            {"name": "u_a", "module": "ma"},
            {"name": "u_b", "module": "mb"},
        ],
        "fsm_candidates": [
            {"state_register": "state", "type_name": "state_e",
             "states": ["ST_IDLE", "ST_ENCODE"]}
        ],
        "clock_domains": ["sys"],
        "convention_violations": [],
    }
    jpath = tmp_path / "x.json"
    jpath.write_text(json.dumps(payload))
    out = tmp_path / "doc.md"
    r = _run(["--json", str(jpath), "--template-dir", str(TEMPLATE_DIR), "--out", str(out)])
    assert r.returncode == 0
    body = out.read_text()
    assert "FSM States" in body
    assert "stateDiagram-v2" in body
    assert "```d2" in body
    assert "u_a" in body and "u_b" in body
    assert "LLM_FILL: FSM state semantics" in body


def test_violation_banner(tmp_path):
    payload = {
        "module_name": "bad",
        "file": "rtl/bad.sv",
        "parameters": [], "ports": [], "instances": [],
        "fsm_candidates": [], "clock_domains": [],
        "convention_violations": [
            {"signal": "data_i", "rule": "Use i_/o_/io_ prefix (not suffix)"}
        ],
    }
    jpath = tmp_path / "x.json"
    jpath.write_text(json.dumps(payload))
    out = tmp_path / "doc.md"
    _run(["--json", str(jpath), "--template-dir", str(TEMPLATE_DIR), "--out", str(out)])
    body = out.read_text()
    assert "Convention Violations" in body
    assert "data_i" in body
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
python3 -m pytest tests/unit/test_render_doc.py -v
```

Expected: 4 failures (script + templates not yet present).

- [ ] **Step 3: Create the four template files**

`skills/rtl-document/templates/port-table-snippet.md` — ensure it exists (note: the main `module-doc-template.md` already exists; leave it for Task 9 which adjusts it to use markers).

```markdown
| Port Name | Direction | Width | Clock Domain | Kind  | Description |
|-----------|-----------|-------|--------------|-------|-------------|
```

`skills/rtl-document/templates/fsm-section-snippet.md`:

```markdown
## FSM States

| State | Encoding | Description | Transitions To |
|-------|----------|-------------|----------------|
{{FSM_ROWS}}

```mermaid
stateDiagram-v2
{{FSM_TRANSITIONS}}
```
```

`skills/rtl-document/templates/block-diagram-snippet.d2`:

```d2
# {{MODULE_NAME}} sub-instances
{{INSTANCE_NODES}}
```

- [ ] **Step 4: Update the main `module-doc-template.md`**

Replace the existing `skills/rtl-document/templates/module-doc-template.md` with a marker-driven version:

```markdown
# {{MODULE_NAME}}

> Auto-generated from `{{FILE}}`. Replace every `<!-- LLM_FILL: ... -->` marker.

## Overview

<!-- LLM_FILL: functional description (100-200 chars) -->

{{CONVENTION_BANNER}}

## Parameters

{{PARAMETERS_TABLE}}

## Ports

{{PORTS_TABLE}}

## Clock Domains

{{CLOCK_DOMAINS_TABLE}}

{{FSM_SECTION}}

{{INSTANCES_SECTION}}

{{BLOCK_DIAGRAM_SECTION}}

{{SYNTH_SUMMARY_SECTION}}

## Design Notes

<!-- LLM_FILL: design rationale / integration notes -->
```

- [ ] **Step 5: Implement `render_doc.py`**

```python
#!/usr/bin/env python3
"""Compose docs/rtl/<module>.md from extractor JSON + templates."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _read(p: Path) -> str:
    return p.read_text()


def _ports_table(ports: list[dict]) -> str:
    rows = ["| Port Name | Direction | Width | Clock Domain | Kind | Description |",
            "|-----------|-----------|-------|--------------|------|-------------|"]
    for p in ports:
        rows.append(f"| {p['name']} | {p['dir']} | {p['width']} | "
                    f"{p.get('domain','?')} | {p['kind']} | <!-- LLM_FILL: port description --> |")
    return "\n".join(rows)


def _params_table(params: list[dict]) -> str:
    if not params:
        return "_None._"
    rows = ["| Parameter | Type | Default | Description |",
            "|-----------|------|---------|-------------|"]
    for p in params:
        rows.append(f"| {p['name']} | {p.get('type','?')} | {p['default']} | "
                    "<!-- LLM_FILL: parameter description --> |")
    return "\n".join(rows)


def _clock_table(domains: list[str]) -> str:
    if not domains:
        return "_None._"
    rows = ["| Domain | Clock | Reset | Usage |",
            "|--------|-------|-------|-------|"]
    for d in domains:
        rows.append(f"| {d} | {d}_clk | {d}_rst_n | <!-- LLM_FILL: clock domain usage --> |")
    return "\n".join(rows)


def _fsm_section(fsm_candidates: list[dict], template_dir: Path) -> str:
    if not fsm_candidates:
        return ""
    tmpl = _read(template_dir / "fsm-section-snippet.md")
    fsm = fsm_candidates[0]
    rows = [f"| {s} | _enum_ | <!-- LLM_FILL: state semantics --> | <!-- LLM_FILL: transitions --> |"
            for s in fsm["states"]]
    transitions = "\n".join(f"  {s}" for s in fsm["states"])
    return tmpl.replace("{{FSM_ROWS}}", "\n".join(rows)) \
               .replace("{{FSM_TRANSITIONS}}", transitions)


def _instances_section(instances: list[dict]) -> str:
    if not instances:
        return ""
    rows = ["## Sub-Module Instances", "",
            "| Instance | Module | Purpose |",
            "|----------|--------|---------|"]
    for i in instances:
        rows.append(f"| {i['name']} | {i['module']} | <!-- LLM_FILL: instance purpose --> |")
    return "\n".join(rows)


def _block_diagram(instances: list[dict], module_name: str, template_dir: Path) -> str:
    if len(instances) < 2:
        return ""
    tmpl = _read(template_dir / "block-diagram-snippet.d2")
    nodes = "\n".join(f"  {i['name']}: {i['module']}" for i in instances)
    body = tmpl.replace("{{MODULE_NAME}}", module_name) \
               .replace("{{INSTANCE_NODES}}", nodes)
    return f"## Block Diagram\n\n```d2\n{body}\n```"


def _synth_summary(s: dict | None) -> str:
    if not s:
        return ""
    rows = ["## Synthesis Summary", ""]
    if "area_um2" in s:
        rows.append(f"- Area: **{s['area_um2']:.2f} um^2**")
    if "wns_ns" in s:
        rows.append(f"- WNS: **{s['wns_ns']:.3f} ns**")
    if "tns_ns" in s:
        rows.append(f"- TNS: **{s['tns_ns']:.3f} ns**")
    return "\n".join(rows)


def _convention_banner(viol: list[dict]) -> str:
    if not viol:
        return ""
    rows = ["> ### Convention Violations",
            ">",
            "> | Signal | Rule |",
            "> |--------|------|"]
    for v in viol:
        rows.append(f"> | {v['signal']} | {v['rule']} |")
    return "\n".join(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--json", required=True)
    p.add_argument("--template-dir", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    data = json.loads(Path(args.json).read_text())
    template_dir = Path(args.template_dir)
    body = _read(template_dir / "module-doc-template.md")

    body = (body
        .replace("{{MODULE_NAME}}", data["module_name"])
        .replace("{{FILE}}", data["file"])
        .replace("{{CONVENTION_BANNER}}", _convention_banner(data.get("convention_violations", [])))
        .replace("{{PARAMETERS_TABLE}}", _params_table(data.get("parameters", [])))
        .replace("{{PORTS_TABLE}}", _ports_table(data.get("ports", [])))
        .replace("{{CLOCK_DOMAINS_TABLE}}", _clock_table(data.get("clock_domains", [])))
        .replace("{{FSM_SECTION}}", _fsm_section(data.get("fsm_candidates", []), template_dir))
        .replace("{{INSTANCES_SECTION}}", _instances_section(data.get("instances", [])))
        .replace("{{BLOCK_DIAGRAM_SECTION}}", _block_diagram(data.get("instances", []), data["module_name"], template_dir))
        .replace("{{SYNTH_SUMMARY_SECTION}}", _synth_summary(data.get("synth_summary")))
    )

    # Collapse stray blank lines (no more than two consecutive).
    import re
    body = re.sub(r"\n{3,}", "\n\n", body)
    Path(args.out).write_text(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Run tests and verify they pass**

```bash
python3 -m pytest tests/unit/test_render_doc.py -v
```

Expected: 4 passing.

- [ ] **Step 7: Commit**

```bash
git add skills/rtl-document/scripts/render_doc.py skills/rtl-document/templates/ tests/unit/test_render_doc.py
git commit -m "feat(rtl-document): render_doc.py with template-dir composition + LLM_FILL markers"
```

---

## Task 7: `references/doc-conventions.md`

**Files:**
- Create: `skills/rtl-document/references/doc-conventions.md`

- [ ] **Step 1: Write `doc-conventions.md`** (≤200 lines)

```markdown
# RTL Documentation Conventions

A quick reference for filling `<!-- LLM_FILL: ... -->` markers and choosing
visual elements in `docs/rtl/{module}.md`. Stays under 200 lines so it can be
consulted in one read.

## 1. Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Port direction prefix | `i_`, `o_`, `io_` (NOT suffix) | `i_data`, `o_valid` |
| Clock port | `clk` (single) or `{domain}_clk` | `sys_clk`, `pixel_clk` |
| Reset port | `rst_n` (single) or `{domain}_rst_n` (active-low async) | `sys_rst_n` |
| Instance | `u_*` prefix | `u_range_coder` |
| Parameter | `UPPER_SNAKE_CASE` | `DATA_WIDTH` |
| Localparam | `L_*` prefix, `UPPER_SNAKE_CASE` | `L_FIFO_DEPTH` |
| FSM state | `ST_*` prefix, `UPPER_SNAKE_CASE` | `ST_IDLE`, `ST_ENCODE` |

If a violation is recorded in the generated doc's banner, do not rewrite the
RTL — surface it for the human RTL engineer.

## 2. Table formats

### Port table column order

`Port Name | Direction | Width | Clock Domain | Kind | Description`

`Kind` is one of `clock`, `reset`, `data`, `protocol`. The renderer fills
`clock` and `reset` automatically based on naming; `data` is the default;
`protocol` should be applied by the LLM when filling marker descriptions for
AXI/AHB/APB signals.

### Parameter table

`Parameter | Type | Default | Description`

### Instance table

`Instance | Module | Purpose`

## 3. Diagram tool choice

- **Block diagrams** (sub-instance hierarchy, data flow between blocks) →
  **D2**. Match the project's `<markdown_diagram_rule>`.
- **FSM** → **Mermaid `stateDiagram-v2`**.
- **Flow / sequence** → **Mermaid `flowchart`** or `sequenceDiagram`.
- Do not mix D2 and Mermaid for the same diagram type within a single doc.

## 4. Length guidance

- Overview: 100-200 characters. One or two sentences. State the module's
  responsibility, not its implementation.
- Per-state description: 1-2 lines. What the state does and what triggers
  the transition out of it.
- Per-port description: 1 line. Skip if the port name already conveys the
  meaning (e.g., `i_valid`).
- Design Notes: optional. Use only when the module has a non-obvious
  property a reader of the code would not see immediately (e.g., "the
  internal counter wraps at DATA_WIDTH-2 to avoid the W-1 edge case").

## 5. Anti-patterns

- Leaving `<!-- LLM_FILL: ... -->` markers in the committed doc — fail.
- Leaving `{{PLACEHOLDER}}` strings — fail (the renderer should have
  replaced them; if any remain, fix the renderer or the JSON instead).
- Restating the port name in its description ("i_valid — input valid signal").
- Inventing port descriptions when no comment or naming clue exists. Leave
  the cell blank rather than fabricating.
- Writing "TODO" inside the doc body. If something cannot be documented yet,
  remove the corresponding section and note absence in the document footer.
```

- [ ] **Step 2: Commit**

```bash
git add skills/rtl-document/references/doc-conventions.md
git commit -m "docs(rtl-document): references/doc-conventions.md"
```

---

## Task 8: Generate three worked examples (dogfooding)

**Files:**
- Create: `skills/rtl-document/examples/simple_fifo.md`
- Create: `skills/rtl-document/examples/axi_stream_bridge.md`
- Create: `skills/rtl-document/examples/cabac_encoder_excerpt.md`

- [ ] **Step 1: Generate `simple_fifo.md`**

If verible is installed:

```bash
python3 skills/rtl-document/scripts/extract_module_doc.py \
  --rtl tests/fixtures/rtl-document/simple_fifo.sv \
  --syn-report tests/fixtures/rtl-document/synth_report.txt \
  --out /tmp/simple_fifo.json
python3 skills/rtl-document/scripts/render_doc.py \
  --json /tmp/simple_fifo.json \
  --template-dir skills/rtl-document/templates/ \
  --out skills/rtl-document/examples/simple_fifo.md
```

If verible is not installed: hand-author from the SV fixture using
`templates/module-doc-template.md` directly (this is the fallback the SKILL.md
documents).

- [ ] **Step 2: Replace every `<!-- LLM_FILL: ... -->` marker**

Open `skills/rtl-document/examples/simple_fifo.md` and fill each marker.
Use `doc-conventions.md` length guidance. After editing, verify no markers
remain:

```bash
! grep -q "LLM_FILL" skills/rtl-document/examples/simple_fifo.md
```

Expected: empty output (no match).

- [ ] **Step 3: Generate `axi_stream_bridge.md`** (same pipeline)

```bash
python3 skills/rtl-document/scripts/extract_module_doc.py \
  --rtl tests/fixtures/rtl-document/axi_stream_bridge.sv \
  --out /tmp/axi_stream_bridge.json
python3 skills/rtl-document/scripts/render_doc.py \
  --json /tmp/axi_stream_bridge.json \
  --template-dir skills/rtl-document/templates/ \
  --out skills/rtl-document/examples/axi_stream_bridge.md
```

Fill markers; ensure both `sys` and `pixel` clock domains appear in the
Clock Domains table; group AXI ports together in the Description column.

- [ ] **Step 4: Generate `cabac_encoder_excerpt.md`** (same pipeline)

```bash
python3 skills/rtl-document/scripts/extract_module_doc.py \
  --rtl tests/fixtures/rtl-document/cabac_encoder_excerpt.sv \
  --out /tmp/cabac_encoder_excerpt.json
python3 skills/rtl-document/scripts/render_doc.py \
  --json /tmp/cabac_encoder_excerpt.json \
  --template-dir skills/rtl-document/templates/ \
  --out skills/rtl-document/examples/cabac_encoder_excerpt.md
```

Fill markers; FSM section shows all three states (ST_IDLE / ST_ENCODE /
ST_FLUSH) with semantics; D2 block diagram lists range_coder, context_memory,
bypass_encoder.

- [ ] **Step 5: Verify all three are marker-free**

```bash
for f in skills/rtl-document/examples/*.md; do
  if grep -q "LLM_FILL" "$f"; then
    echo "FAIL: stray marker in $f"; exit 1
  fi
done
echo "OK"
```

Expected: "OK".

- [ ] **Step 6: Commit**

```bash
git add skills/rtl-document/examples/
git commit -m "docs(rtl-document): three worked examples (simple_fifo, axi_stream_bridge, cabac_encoder)"
```

---

## Task 9: Regression test for examples and pipeline smoke

**Files:**
- Create: `tests/unit/test_rtl_document_examples.py`

- [ ] **Step 1: Write the failing test**

```python
import json
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "skills" / "rtl-document" / "examples"
SCRIPTS = ROOT / "skills" / "rtl-document" / "scripts"
TEMPLATES = ROOT / "skills" / "rtl-document" / "templates"
FIXTURES = ROOT / "tests" / "fixtures" / "rtl-document"

VERIBLE_AVAILABLE = shutil.which("verible-verilog-syntax") is not None


def test_examples_have_no_stray_markers():
    files = list(EXAMPLES.glob("*.md"))
    assert len(files) == 3, f"expected 3 examples, found {len(files)}"
    for f in files:
        body = f.read_text()
        assert "LLM_FILL" not in body, f"{f.name} still has unfilled markers"
        assert "{{" not in body, f"{f.name} still has placeholder braces"


def test_examples_required_sections():
    expected = {
        "simple_fifo.md":         ["Ports", "Parameters"],
        "axi_stream_bridge.md":   ["Ports", "Clock Domains"],
        "cabac_encoder_excerpt.md": ["FSM States", "Sub-Module Instances"],
    }
    for name, sections in expected.items():
        body = (EXAMPLES / name).read_text()
        for s in sections:
            assert s in body, f"{name} missing '{s}'"


@pytest.mark.skipif(not VERIBLE_AVAILABLE, reason="verible not installed")
def test_pipeline_smoke(tmp_path):
    j = tmp_path / "s.json"
    md = tmp_path / "s.md"
    subprocess.run(
        [sys.executable, str(SCRIPTS / "extract_module_doc.py"),
         "--rtl", str(FIXTURES / "simple_fifo.sv"),
         "--out", str(j)],
        check=True,
    )
    data = json.loads(j.read_text())
    assert data["module_name"] == "simple_fifo"
    subprocess.run(
        [sys.executable, str(SCRIPTS / "render_doc.py"),
         "--json", str(j),
         "--template-dir", str(TEMPLATES),
         "--out", str(md)],
        check=True,
    )
    body = md.read_text()
    assert "i_data" in body
    assert "LLM_FILL" in body  # raw render still has markers; LLM fills later
```

- [ ] **Step 2: Run tests and verify they pass**

```bash
python3 -m pytest tests/unit/test_rtl_document_examples.py -v
```

Expected: 3 passing (verible-gated test may skip).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_rtl_document_examples.py
git commit -m "test(rtl-document): examples marker-integrity + pipeline smoke"
```

---

## Task 10: SKILL.md rewrite

**Files:**
- Rewrite: `skills/rtl-document/SKILL.md`

- [ ] **Step 1: Replace the SKILL.md body with the §5.4 spec draft**

Copy the full SKILL.md draft from
`plugin_docs/specs/2026-05-12-rtl-document-asset-bundle-design.md` §5.4 into
`skills/rtl-document/SKILL.md`, verbatim. (The draft is reproduced inline
below for convenience; if it diverges from §5.4 during implementation, treat
the spec as the source of truth.)

```markdown
---
name: rtl-document
description: This skill should be used when the user asks to "document this RTL module", "generate module docs", "create port table for X", "RTL documentation pass", "refresh RTL docs after change", or when a new RTL module needs Markdown documentation with port/parameter/instance tables and a synthesis summary.
user-invocable: true
argument-hint: "[module-name | --all]"
allowed-tools: Bash, Read, Write, Edit, Task, Grep, Glob
---

<Purpose>
Generate per-module Markdown documentation for SystemVerilog RTL — port table, parameter table, instance table, FSM section, and synthesis summary. Output: docs/rtl/{module}.md.
</Purpose>

<Use_When>
- A new RTL module needs documentation.
- Module documentation has become stale after RTL changes.
- A pre-release documentation pass is required.
- The user asks to "document this module", "generate port table", or "refresh RTL docs".
</Use_When>

<Do_Not_Use_When>
- Architecture specification writing is needed → use p2-arch-design.
- IP-XACT XML generation is needed → use rtl-ipxact-gen.
- Synthesis-only reporting is needed → use rtl-synth-check.
</Do_Not_Use_When>

<Why_This_Exists>
RTL documentation written by hand drifts from implementation. Auto-extraction from SV source keeps port tables, parameter lists, and instance trees accurate. The skill splits work between a deterministic parser (objective structure) and the LLM (functional description, FSM semantics, design rationale), making the contract surface explicit and regression-debuggable.
</Why_This_Exists>

## Prerequisites

- RTL files exist under `rtl/**/*.sv`.
- Optional: synthesis report at `syn/synth_report.txt` for area/timing summary.

If the prerequisite is missing: WARNING — recommend running `/rtl-agent-team:rtl-p4-implement` first. Proceed with available artifacts; the orchestrator adapts scope.

<Assets>
| Path | Role |
|------|------|
| `templates/module-doc-template.md` | Main Markdown skeleton (Overview/Params/Ports/Clocks/Instances/Diagram). |
| `templates/port-table-snippet.md` | Port-table format with `i_/o_/io_` prefix, `{domain}_clk`/`{domain}_rst_n`, kind column. |
| `templates/fsm-section-snippet.md` | FSM table plus Mermaid `stateDiagram-v2` skeleton. |
| `templates/block-diagram-snippet.d2` | D2 block diagram for sub-instance hierarchy. |
| `scripts/extract_module_doc.py` | Verible-based deterministic extractor — emits JSON for ports/params/instances/FSM/conventions. |
| `scripts/render_doc.py` | JSON + template → `docs/rtl/{module}.md` with `<!-- LLM_FILL: ... -->` markers. |
| `references/doc-conventions.md` | Naming rules, table format, diagram-tool choice, anti-patterns. |
| `examples/simple_fifo.md` | Small datapath, single domain — minimal baseline. |
| `examples/axi_stream_bridge.md` | AXI4-Stream + APB control, two clock domains — protocol grouping. |
| `examples/cabac_encoder_excerpt.md` | FSM-heavy + sub-instance tree — full template usage. |
</Assets>

<Responsibility_Boundary>
- **Scripts** handle deterministic extraction: module name, ports, parameters, instances, FSM-candidate states, clock-domain inference from naming, convention violations.
- **LLM** handles interpretive content: functional description, FSM state semantics, design rationale, integration notes.
- `<!-- LLM_FILL: ... -->` markers in rendered output mark the contract surface. Replace each marker; never delete.
</Responsibility_Boundary>

<Execution>
1. Run `python3 skills/rtl-document/scripts/extract_module_doc.py --rtl rtl/{module}/{module}.sv [--syn-report syn/synth_report.txt] --out /tmp/{module}.json`. If exit code 2 (verible missing), fall back to manual extraction via `rtl-explorer` (see Tool_Usage).
2. Run `python3 skills/rtl-document/scripts/render_doc.py --json /tmp/{module}.json --template-dir skills/rtl-document/templates/ --out docs/rtl/{module}.md`. The script composes `module-doc-template.md` with the optional snippets — `port-table-snippet.md` when ports exist, `fsm-section-snippet.md` when `fsm_candidates` is non-empty, `block-diagram-snippet.d2` when there are two or more instances.
3. Read `skills/rtl-document/references/doc-conventions.md` once for naming/format/diagram rules.
4. Open at least one matching `skills/rtl-document/examples/*.md` for tone reference — pick the example whose complexity (small / multi-domain / FSM-heavy) is closest to the target module.
5. Replace every `<!-- LLM_FILL: ... -->` marker in `docs/rtl/{module}.md`. Apply to all such markers in the file — do not stop after the first.
6. Report the generated file path to the user.

Apply steps 1-6 to every requested module. When `--all` is passed, fan out using one task per module in parallel.
</Execution>

<Tool_Usage>
Manual-extraction fallback (when verible is unavailable):
```
Task(subagent_type="rtl-agent-team:rtl-explorer",
     prompt="Document RTL module per skills/rtl-document/. Read rtl/{module}/{module}.sv, extract ports/parameters/instances/FSM, apply project naming conventions, and fill the LLM_FILL markers in docs/rtl/{module}.md.")
```

Synthesis summary:
```
Task(subagent_type="rtl-agent-team:synthesis-reporter",
     prompt="Summarize syn/synth_report.txt and syn/timing_report.txt for the docs/rtl/{module}.md synthesis section.")
```
</Tool_Usage>

<Examples>
<example index="1">
<scenario>Small datapath module, no FSM, single clock domain.</scenario>
<reference>skills/rtl-document/examples/simple_fifo.md</reference>
<expected_output>Port table only; FSM and D2 sections omitted by render_doc.py because the JSON has empty fsm_candidates and one instance or fewer.</expected_output>
</example>

<example index="2">
<scenario>AXI-Stream bridge with two clock domains.</scenario>
<reference>skills/rtl-document/examples/axi_stream_bridge.md</reference>
<expected_output>Ports grouped by AXI / APB; Clock Domains table lists both `sys` and `pixel`; D2 block diagram shows the async-FIFO bridge.</expected_output>
</example>

<example index="3">
<scenario>FSM-heavy codec module with multiple sub-instances.</scenario>
<reference>skills/rtl-document/examples/cabac_encoder_excerpt.md</reference>
<expected_output>FSM table with Mermaid `stateDiagram-v2`; D2 block diagram for the sub-instance tree; functional description references the relevant standard section.</expected_output>
</example>
</Examples>

<Escalation_And_Stop_Conditions>
- `extract_module_doc.py` returns SV parse error → report file:line; do not fabricate ports. Ask the user to fix the syntax first.
- FSM register cannot be inferred → JSON has `fsm_candidates: []`. Add an FSM section manually only when a state machine clearly exists and the state register is identifiable.
- Synthesis report absent → omit the Synthesis Summary section; note the absence in the document footer.
- Port name violates convention (e.g., `data_i` suffix) → record in `convention_violations` and surface the violation at the top of the generated doc. Do not rewrite the RTL.
</Escalation_And_Stop_Conditions>

## Output

- `docs/rtl/{module}.md` — per-module documentation.
- `/tmp/{module}.json` — intermediate extraction (transient; not committed).

<Final_Checklist>
- [ ] `docs/rtl/{module}.md` exists for every requested module.
- [ ] Port table lists every port with `i_/o_/io_` prefix; clock/reset rows tagged `kind=clock|reset`.
- [ ] Parameters use `UPPER_SNAKE_CASE`.
- [ ] Instance table uses `u_` prefix.
- [ ] All `<!-- LLM_FILL: ... -->` markers replaced.
- [ ] RTL source not modified.
- [ ] Synthesis Summary included when `syn/synth_report.txt` exists.
- [ ] Convention violations flagged at the top of the doc when any were found.
</Final_Checklist>
```

- [ ] **Step 2: Verify line count is within target**

```bash
wc -l skills/rtl-document/SKILL.md
```

Expected: 90-100 lines.

- [ ] **Step 3: Verify all referenced files exist**

```bash
for f in templates/module-doc-template.md templates/port-table-snippet.md \
         templates/fsm-section-snippet.md templates/block-diagram-snippet.d2 \
         scripts/extract_module_doc.py scripts/render_doc.py \
         references/doc-conventions.md \
         examples/simple_fifo.md examples/axi_stream_bridge.md \
         examples/cabac_encoder_excerpt.md; do
  test -f "skills/rtl-document/$f" || { echo "MISSING: $f"; exit 1; }
done
echo "OK"
```

Expected: "OK".

- [ ] **Step 4: Commit**

```bash
git add skills/rtl-document/SKILL.md
git commit -m "feat(rtl-document): lean SKILL.md per asset-bundle pattern"
```

---

## Task 11: Update candidates plan + run full test suite

**Files:**
- Modify: `plugin_docs/plans/2026-03-20-skill-improvement-candidates.md`

- [ ] **Step 1: Mark `rtl-document` complete**

Open `plugin_docs/plans/2026-03-20-skill-improvement-candidates.md` and update
the row for `rtl-document` in the "Priority 1" table — change the Effort
column entry to "✅ done (2026-05-12)" and add a footnote pointing at
`plugin_docs/specs/2026-05-12-rtl-document-asset-bundle-design.md` as the
reference pattern for the remaining 10 candidates.

Append a new section at the end:

```markdown
## Reference Pattern

`rtl-document` (completed 2026-05-12) is the reference implementation of the
"asset bundle pattern". Spec: `plugin_docs/specs/2026-05-12-rtl-document-asset-bundle-design.md`.
Subsequent skill upgrades in this list follow that pattern: parser script with
a JSON schema, snippet-composing renderer, ≤200-line references guide, three
worked examples covering complexity spectrum, and a lean SKILL.md (~95 lines)
applying the Anthropic prompting + plugin-dev skill-development guidelines
documented in §5.3 of the spec.
```

- [ ] **Step 2: Run the full unit test suite**

```bash
python3 -m pytest tests/unit/ --ignore=tests/unit/test_bd_rate.py -x -q
```

Expected: all green.

- [ ] **Step 3: Run any plugin validator hooks that exist**

```bash
sh scripts/sync_orchestrator_inject.sh
# (only needed if SKILL.md routing changed; rtl-document is already in the routing table)
```

- [ ] **Step 4: Verify no markers leaked into committed examples**

```bash
! grep -r "LLM_FILL" skills/rtl-document/examples/
```

Expected: empty output.

- [ ] **Step 5: Commit**

```bash
git add plugin_docs/plans/2026-03-20-skill-improvement-candidates.md
git commit -m "docs(plans): mark rtl-document complete + record reference pattern"
```

---

## Task 12: Final integration sweep

**Files:** None modified. Verification only.

- [ ] **Step 1: End-to-end manual run**

```bash
mkdir -p /tmp/rtl-document-e2e/rtl/simple_fifo
cp tests/fixtures/rtl-document/simple_fifo.sv /tmp/rtl-document-e2e/rtl/simple_fifo/
cp tests/fixtures/rtl-document/synth_report.txt /tmp/rtl-document-e2e/

cd /tmp/rtl-document-e2e
python3 $OLDPWD/skills/rtl-document/scripts/extract_module_doc.py \
  --rtl rtl/simple_fifo/simple_fifo.sv \
  --syn-report synth_report.txt \
  --out /tmp/simple_fifo.json

python3 $OLDPWD/skills/rtl-document/scripts/render_doc.py \
  --json /tmp/simple_fifo.json \
  --template-dir $OLDPWD/skills/rtl-document/templates/ \
  --out docs/rtl/simple_fifo.md  # this should fail because the dir doesn't exist

mkdir -p docs/rtl
python3 $OLDPWD/skills/rtl-document/scripts/render_doc.py \
  --json /tmp/simple_fifo.json \
  --template-dir $OLDPWD/skills/rtl-document/templates/ \
  --out docs/rtl/simple_fifo.md

test -f docs/rtl/simple_fifo.md && echo "E2E OK"
cd $OLDPWD
rm -rf /tmp/rtl-document-e2e
```

Expected: "E2E OK" and the rendered file contains `i_data`, no `{{...}}`
placeholders, and `<!-- LLM_FILL: ... -->` markers (because no LLM fill ran).

- [ ] **Step 2: Confirm SKILL.md word count is within target**

```bash
wc -w skills/rtl-document/SKILL.md
```

Expected: 600-800 words (target ≤ 1,000; ideal range).

- [ ] **Step 3: Confirm all checklist items met**

- [ ] `rtl-document` has all four asset categories (`templates/`, `scripts/`,
      `references/`, `examples/`) populated.
- [ ] Three examples exist and contain no markers.
- [ ] Unit tests pass locally and in CI.
- [ ] SKILL.md body ≤ 1,000 words.
- [ ] Spec reference and `skill-improvement-candidates` plan updated.

- [ ] **Step 4: No commit (verification-only task)**

---
