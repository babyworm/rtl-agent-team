# Tool Check Commands (rat-setup reference)

Command examples for selected capability probes. Run only the checks relevant to
the user's phase and chosen execution site. The sections below group available
examples; they are not mandatory installation tiers. For SSH/LSF use
`remote-site-setup.md` so probes run on the execution host.

## Tier 1 — Required

```bash
Bash: "${RAT_PYTHON:-python3}" --version 2>&1 || echo "NOT_FOUND"
Bash: if command -v g++ >/dev/null 2>&1; then OUTPUT="$(g++ --version 2>&1)"; RC=$?; printf '%s\n' "$OUTPUT" | sed -n '1p'; exit "$RC"; else echo "NOT_FOUND"; fi
Bash: if command -v make >/dev/null 2>&1; then OUTPUT="$(make --version 2>&1)"; RC=$?; printf '%s\n' "$OUTPUT" | sed -n '1p'; exit "$RC"; else echo "NOT_FOUND"; fi
Bash: verilator --version 2>&1 || echo "NOT_FOUND"
Bash: "${RAT_PYTHON:-python3}" -c "import cocotb; print(cocotb.__version__)" 2>&1 || echo "NOT_FOUND"
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
Bash: if command -v iverilog >/dev/null 2>&1; then OUTPUT="$(iverilog -V 2>&1)"; RC=$?; printf '%s\n' "$OUTPUT" | sed -n '1p'; exit "$RC"; else echo "NOT_FOUND"; fi
Bash: yosys --version 2>&1 || echo "NOT_FOUND"
Bash: if command -v sby >/dev/null 2>&1; then OUTPUT="$(sby --help 2>&1)"; RC=$?; printf '%s\n' "$OUTPUT" | sed -n '1p'; exit "$RC"; else echo "NOT_FOUND"; fi
Bash: gtkwave --version 2>&1 || echo "NOT_FOUND"
Bash: docker --version 2>&1 || echo "NOT_FOUND"
Bash: sv2v --version 2>&1 || echo "NOT_FOUND"
```

## Test Infrastructure

```bash
Bash: "${RAT_PYTHON:-python3}" -m pytest --version 2>&1 || echo "NOT_FOUND"
Bash: "${RAT_PYTHON:-python3}" -c "import cocotb_bus; print(cocotb_bus.__version__)" 2>&1 || echo "NOT_FOUND"
Bash: "${RAT_PYTHON:-python3}" -c "import numpy; print(numpy.__version__)" 2>&1 || echo "NOT_FOUND"
Bash: "${RAT_PYTHON:-python3}" -c "import hjson; print(hjson.__version__)" 2>&1 || echo "NOT_FOUND"
```

## Commercial Tools (Phase 1d)

| Tool | Check Command | Vendor | Category |
|------|--------------|--------|----------|
| vcs | `vcs -ID 2>&1` | Synopsys | Simulator |
| xrun | `xrun -version 2>&1` | Cadence | Simulator |
| vsim | `vsim -version 2>&1` | Siemens | Simulator |
| dc_shell | `which dc_shell 2>/dev/null` | Synopsys | Synthesis |
| genus | `which genus 2>/dev/null` | Cadence | Synthesis |
| sg_shell | `which sg_shell 2>/dev/null` | Synopsys | Lint/CDC |
| vc_cdc | `which vc_static_shell 2>/dev/null` | Synopsys | CDC |
| questa_cdc | `which qverify 2>/dev/null` | Siemens | CDC |
| fm_shell | `which fm_shell 2>/dev/null` | Synopsys | Equivalence |
| lec | `which lec 2>/dev/null` | Cadence | Equivalence |
| verdi | `which verdi 2>/dev/null` | Synopsys | Debug |
| simvision | `which simvision 2>/dev/null` | Cadence | Debug |

Record for each: detected (true/false), path, version string (if available). Separate
detected tools from undetected for Phase 3 Q2b.

## Plugin Configuration State

```bash
Bash: ls ~/.claude/rules/ 2>/dev/null || echo "NO_RULES"
Bash: claude plugin list --json 2>/dev/null || echo "PLUGIN_LIST_UNAVAILABLE"
Bash: if command -v docker >/dev/null 2>&1; then OUTPUT="$(docker images -q rtl-eda-tools 2>&1)"; RC=$?; IMAGE_ID="$(printf '%s\n' "$OUTPUT" | sed -n '1p')"; if [ "$RC" -ne 0 ]; then printf '%s\n' "$OUTPUT" >&2; exit "$RC"; elif [ -n "$IMAGE_ID" ]; then echo "$IMAGE_ID"; else echo "NO_IMAGE"; fi; else echo "NO_IMAGE"; fi
```

**All EDA tools are executed via Bash CLI directly. No MCP tool servers for EDA.**
