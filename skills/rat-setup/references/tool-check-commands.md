# Tool Check Commands (rat-setup reference)

Exact Bash CLI commands for Phase 1 Discovery. Run ALL of these in parallel via the Bash
tool (never MCP). Corresponds to the Tier 1/2/3, Test Infrastructure, Commercial Tool, and
Plugin Configuration checks described in `SKILL.md` Phase 1.

## Tier 1 — Required

```bash
Bash: python3 --version 2>&1 || echo "NOT_FOUND"
Bash: g++ --version 2>&1 | head -1 || echo "NOT_FOUND"
Bash: make --version 2>&1 | head -1 || echo "NOT_FOUND"
Bash: verilator --version 2>&1 || echo "NOT_FOUND"
Bash: python3 -c "import cocotb; print(cocotb.__version__)" 2>&1 || echo "NOT_FOUND"
Bash: pkg-config --modversion systemc 2>/dev/null || (test -n "$SYSTEMC_HOME" && test -f "$SYSTEMC_HOME/lib-linux64/libsystemc.a" && echo "$SYSTEMC_HOME (found via SYSTEMC_HOME)") || echo "NOT_FOUND"
Bash: verible-verilog-lint --version 2>&1 || echo "NOT_FOUND"
Bash: slang --version 2>&1 || echo "NOT_FOUND"
Bash: svlens --version 2>&1 || echo "NOT_FOUND"  # CDC/structural analysis (Tier 1 — or any commercial CDC from Phase 1d)
```

## Tier 2 — Recommended

```bash
Bash: jq --version 2>&1 || echo "NOT_FOUND"
Bash: slang-server --version 2>&1 || echo "NOT_FOUND"
```

## Tier 3 — Optional

```bash
Bash: iverilog -V 2>&1 | head -1 || echo "NOT_FOUND"
Bash: yosys --version 2>&1 || echo "NOT_FOUND"
Bash: sby --help 2>&1 | head -1 || echo "NOT_FOUND"
Bash: gtkwave --version 2>&1 || echo "NOT_FOUND"
Bash: docker --version 2>&1 || echo "NOT_FOUND"
Bash: sv2v --version 2>&1 || echo "NOT_FOUND"
```

## Test Infrastructure

```bash
Bash: python3 -m pytest --version 2>&1 || echo "NOT_FOUND"
Bash: python3 -c "import cocotb_bus; print(cocotb_bus.__version__)" 2>&1 || echo "NOT_FOUND"
Bash: python3 -c "import numpy; print(numpy.__version__)" 2>&1 || echo "NOT_FOUND"
Bash: python3 -c "import hjson; print(hjson.__version__)" 2>&1 || echo "NOT_FOUND"
```

## Commercial Tools (Phase 1d)

| Tool | Check Command | Vendor | Category |
|------|--------------|--------|----------|
| vcs | `vcs -ID 2>&1 \| head -1` | Synopsys | Simulator |
| xrun | `xrun -version 2>&1 \| head -1` | Cadence | Simulator |
| vsim | `vsim -version 2>&1 \| head -1` | Siemens | Simulator |
| dc_shell | `which dc_shell 2>/dev/null` | Synopsys | Synthesis |
| genus | `which genus 2>/dev/null` | Cadence | Synthesis |
| sg_shell | `which sg_shell 2>/dev/null` | Synopsys | Lint/CDC |
| vc_cdc | `which vc_cdc 2>/dev/null` | Synopsys | CDC |
| questa_cdc | `which questa_cdc 2>/dev/null` | Siemens | CDC |
| fm_shell | `which fm_shell 2>/dev/null` | Synopsys | Equivalence |
| lec | `which lec 2>/dev/null` | Cadence | Equivalence |
| verdi | `which verdi 2>/dev/null` | Synopsys | Debug |
| simvision | `which simvision 2>/dev/null` | Cadence | Debug |

Record for each: detected (true/false), path, version string (if available). Separate
detected tools from undetected for Phase 3 Q2b.

## Plugin Configuration State

```bash
Bash: ls ~/.claude/rules/ 2>/dev/null || echo "NO_RULES"
Bash: docker images -q rtl-eda-tools 2>/dev/null | head -1 || echo "NO_IMAGE"
```

**All EDA tools are executed via Bash CLI directly. No MCP tool servers for EDA.**
