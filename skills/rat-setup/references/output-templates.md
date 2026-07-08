# Output Templates & Examples (rat-setup reference)

Exact output templates and example prompts for rat-setup. Read the relevant section only
when producing that specific output or prompt.

## Phase 2 Report

```
## EDA Environment Audit

### Tier 1 — Required Tools
| Tool | Status | Version | Action Needed |
|------|--------|---------|---------------|
| python3 | OK | 3.11.2 | — |
| verilator | MISSING | — | Install required |
| verible/slang (lint) | OK / MISSING | — | At least ONE required |
| svlens (cdc/structural) | OK / MISSING | — | Install required unless commercial CDC present |
| ... | | | |

### Tier 2 — Recommended Tools
| Tool | Status | Version | Benefit |
| ... |

### Tier 3 — Optional Tools
| Tool | Status | When Needed |
| ... |

### Test Infrastructure
| Component | Status |
| ... |

### Commercial Tools (PATH scan)
| Tool | Vendor | Status | Path |
|------|--------|--------|------|
| vcs | Synopsys | OK / NOT FOUND | /path/to/vcs |
| dc_shell | Synopsys | OK / NOT FOUND | — |
| xrun | Cadence | OK / NOT FOUND | — |
| ... |

> Commercial tools not found in PATH may still be available via setup scripts.
> You will be asked about this in the next step.

### Plugin Configuration
| Item | Status |
| Global rules (~/.claude/rules/) | Not deployed |
| ... |

Ready to start: Yes/No (**No** if any required tool is missing)
```

## Q2b Examples

**For detected commercial tools** — confirm correctness:

> **Commercial tools found in your PATH:**
> | # | Tool | Vendor | Path |
> |---|------|--------|------|
> | 1 | vcs | Synopsys | /opt/synopsys/vcs/bin/vcs |
> | 2 | dc_shell | Synopsys | /opt/synopsys/dc/bin/dc_shell |
>
> Are these the versions you want to use? (yes / no — I'll correct individually / skip)

If user says "no", ask which tool to correct and what `env_source` command to use instead.

**For undetected commercial tools** — ask if the user has a setup script:

> **The following commercial tools were not found in PATH.**
> If any of these are installed but require environment setup (e.g., `source setup.sh`
> or `module load`), provide the sourcing command. Otherwise skip.
>
> Available tools:
> | # | Tool | Vendor | Purpose |
> |---|------|--------|---------|
> | 1 | vcs | Synopsys | Simulator |
> | 2 | xrun | Cadence | Simulator |
> | 3 | dc_shell | Synopsys | Synthesis |
> | ... |
>
> Enter sourcing commands (format: `number: command`), or `skip`:
> ```
> 1: source /tools/synopsys/vcs/2024.03/setup.sh
> 3: module load synopsys/dc/2024.03
> ```

## NAND2 Area Extraction

Extract NAND2 area using the same logic as `generate_config.sh`:
```bash
awk -v pat="${nand2_pattern:-NAND2X1}" '
  $0 ~ "cell[[:space:]]*\\("pat"\\)" { found=1 }
  found && /area[[:space:]]*:/ {
    gsub(/[^0-9.]/, "", $NF); print $NF; exit
  }
  found && /^\s*\}/ { found=0 }
' "$liberty_path"
```

Record in env-config.json `technology` section:
```json
"technology": {
  "target": "<user-provided description>",
  "liberty": "<absolute path to .lib>",
  "nand2_cell_pattern": "<pattern or NAND2X1>",
  "nand2_area_um2": <extracted or null>
}
```

## Phase 5 Final Report

```
## RTL Agent Team — Setup Complete

### Tool Status (after installation)
| Tier | Installed | Total | Status |
|------|-----------|-------|--------|
| Required | 7 | 7 | PASS |
| Recommended | 3 | 4 | PARTIAL |
| Optional | 2 | 6 | — |

### Commercial Tools
| Tool | Vendor | Status | env_source |
|------|--------|--------|-----------|
| vcs | Synopsys | OK (via env_source) | source /tools/.../setup.sh |
| dc_shell | Synopsys | SKIPPED | — |
| ... |

### Target Technology
| Item | Value |
|------|-------|
| Technology | TSMC 28nm |
| Liberty | /path/to/lib.lib |
| NAND2 area | 1.26 um2 |

(or "Not configured — Yosys built-in model will be used" if skipped)

### Plugin Configuration
| Item | Status |
|------|--------|
| Global rules | Deployed to ~/.claude/rules/ |
| Test infra | pytest, cocotb, numpy installed |
```

## Setup Marker + Environment Config

```bash
# CLAUDE_PLUGIN_DATA: ~/.claude/plugins/data/rtl-agent-team-rtl-agent-marketplace/
# Fallback: ~/.config/rtl-agent-team/ (for environments where CLAUDE_PLUGIN_DATA is unavailable)
PLUGIN_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.config/rtl-agent-team}"
mkdir -p "$PLUGIN_DIR"

# Setup completion marker
date -u '+%Y-%m-%dT%H:%M:%SZ' > "$PLUGIN_DIR/.setup-complete"

# Machine-wide EDA environment config (tool paths + preferences)
# Persisted for future use by rat-init-project and other tools.
# Not yet consumed — foundation for per-project config seeding.
# Structure mirrors rat_config.json preferences section.
cat > "$PLUGIN_DIR/env-config.json" <<ENVEOF
{
  "generated": "$(date -u '+%Y-%m-%dT%H:%M:%SZ')",
  "tools": {
    "_comment": "Machine-wide EDA tool availability from rat-setup scan.",
    <... insert detected tool status from Phase 1 scan results ...>
  },
  "preferences": {
    "_comment": "Auto-detected preferences (commercial priority). Per-project rat_config.json overrides these.",
    "simulator": "<detected preferred sim>",
    "synthesis": "<detected preferred syn>",
    "lint": "<detected preferred lint>",
    "formal": "<detected preferred formal>",
    "cdc": "<detected preferred cdc>"
  }
}
ENVEOF
```

**Note to orchestrator**: The `<... insert ...>` placeholders above must be replaced
with actual Phase 1 scan results. Use the same detection logic and output format as
`generate_config.sh` (tools section + preferences section). The LLM executing this
skill should construct the JSON from the Bash tool check results collected in Phase 1.
