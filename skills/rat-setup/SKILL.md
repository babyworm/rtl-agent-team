---
name: rat-setup
description: "One-time EDA toolchain setup wizard: verify or install tools, build Docker EDA image. Triggers: 'setup tools', 'install tools', 'EDA setup'."
user-invocable: true
---

<Purpose>
Interactive one-time environment setup wizard for the RTL Agent Team plugin.
Audits EDA tools, test infrastructure, and plugin configuration.
Guides the user through installation choices with categorized questions.
For per-project directory structure and rules deployment, use `rat-init-project` instead.
</Purpose>

<Use_When>
- First time installing the plugin on a new machine
- Verifying EDA toolchain is properly installed
- Installing missing required EDA tools
- User says "setup tools", "install tools", "EDA setup", "check tools"
- User says "docker image", "make docker", "EDA environment container"
- Recommended by `rat-init-project` when required tools are missing
</Use_When>

<Do_Not_Use_When>
- Initializing a new project workspace (use `rat-init-project`)
- Tools are already verified and working
- Only need to run a specific EDA tool (use the tool-specific skill)
</Do_Not_Use_When>

<Why_This_Exists>
The 6-Phase pipeline depends on EDA CLI tools (Verilator, verible/slang, cocotb, etc.).
Without proper tool installation, design and verification agents fail with tool-not-found errors.
This skill ensures the EDA environment is ready before any design work begins.
</Why_This_Exists>

<Execution_Policy>
- Interactive: ask the user before installing anything or changing configuration
- Report tool status honestly: installed version or "NOT FOUND"
- If any **required** tool is missing, mark setup as **NOT READY** and explicitly require installation
- Default to user-local installs under `~/.local/bin`, `~/.local`, or `~/tools` (LLM has no sudo access)
- For `global` mode, print sudo commands for the user to run manually
- Never overwrite existing user configuration without confirmation
</Execution_Policy>

Paths below are relative to this skill's base directory (announced at invocation as "Base directory for this skill").

<Reference_Files>
| Path | Read When |
|------|-----------|
| `references/tool-check-commands.md` | Before Phase 1 Discovery — exact Bash CLI check commands for every tier. |
| `references/install-commands.md` | After Q1 collects a remediation choice for a missing Tier 1 tool. |
| `references/docker-environment.md` | User chooses `docker` mode, or asks about the Docker EDA image. |
| `references/output-templates.md` | Producing the Phase 2 report, Q2b prompts, NAND2 extraction, or the Phase 5 final report. |
</Reference_Files>

<Steps>

## Phase 1: Discovery (silent scan — no questions yet)

Read `references/tool-check-commands.md` for the exact Bash CLI commands, then
run all checks in parallel via the Bash tool (never MCP) and collect results.

### 1a. EDA Tool Audit

Categorize tools into three tiers:

**Tier 1 — Required** (pipeline cannot function without these):
- python3 — cocotb runtime, hook JSON parsing
- gcc/g++ — Reference model build (C11/C++17)
- make — Build system
- verilator — Simulation + Lint
- cocotb — Functional verification
- systemc — SystemC/TLM-2.0 (ref model, BFM)
- lint tool — `verible-verilog-lint` AND/OR `slang`; at least ONE required
- cdc tool — `svlens` OR a commercial CDC tool (`sg_shell`/`vc_cdc`/`questa_cdc`); at least ONE
  required. svlens also supplements lint (width/type/dangling checks via `svlens conn`) when
  verible/slang are missing

**Tier 2 — Recommended** (significantly improves workflow):
- jq — Hook JSON parser (robust state gating)
- sv-renamer — SV identifier rename + semantic diff
- sv_to_ipxact — SV → IP-XACT XML auto-generation
- slang-server — SV Language Server (LSP for Claude Code)
- verible (if slang only) — Style lint + formatting
- slang (if verible only) — Deep semantic lint

**Tier 3 — Optional** (needed for specific phases):
- iverilog — Fallback simulator
- yosys — Synthesis (Phase 5B+)
- sby — Formal verification (SymbiYosys)
- gtkwave — Waveform viewer
- docker — EDA tool fallback container
- sv2v — SV→Verilog for formal tools

### 1b. Test Infrastructure Audit
- pytest — Plugin unit test runner
- cocotb-bus — Bus protocol models
- numpy — BD-rate calculations
- hjson — Config file parsing

### 1c. Plugin Configuration State

```bash
# Check if global rules are deployed
test -d ~/.claude/rules && ls ~/.claude/rules/ 2>/dev/null
# Check Claude Code settings
test -f ~/.claude/settings.json && cat ~/.claude/settings.json
# Check if plugin is registered
test -f ~/.claude/plugins.json && cat ~/.claude/plugins.json
```

### 1d. Commercial Tool Scan

Probe commonly used commercial EDA tools (optional, but significantly enhance the pipeline
when available): `vcs`, `xrun`, `vsim` (simulators); `dc_shell`, `genus` (synthesis);
`sg_shell`, `vc_cdc`, `questa_cdc` (lint/CDC); `fm_shell`, `lec` (equivalence); `verdi`,
`simvision` (debug).

Check commands, vendors, and categories: `references/tool-check-commands.md`.
Record for each: detected (true/false), path, version string (if available). Separate
detected tools from undetected for Phase 3 Q2b.

---

## Phase 2: Report (show categorized results)

Present results in a clear categorized table: Tier 1/2/3 tool status, Test Infrastructure,
Commercial Tools (PATH scan), Plugin Configuration, and a final "Ready to start: Yes/No"
line (**No** if any required tool is missing).

Exact template with example values:
`references/output-templates.md` (§ Phase 2 Report).

---

## Phase 3: Interactive Decisions (AskUserQuestion for each category)

Only ask questions for items that need action. Skip categories where everything is already satisfied.

### Q1: Required tool remediation (if any Tier 1 tool is missing)

If required tools are missing, installation is required before real design work can begin.

**CDC tool special rule**: The Tier 1 `cdc tool` requirement is satisfied if ANY of
the following is present: `svlens`, `sg_shell`, `vc_cdc`, `questa_cdc`. Check Phase 1d
results first — if a commercial CDC tool is detected, mark the cdc tool requirement as
satisfied and skip svlens from the missing list. Otherwise, include svlens in the
missing required tools list and install it (open-source, no license required).

**Lint tool rule**: The Tier 1 `lint tool` requirement is satisfied if at least one of
`verible-verilog-lint` or `slang` is present. If neither is present AND svlens is also
missing, install BOTH svlens (for CDC) and at least one lint tool. If svlens is present
but lint is missing, still install a lint tool — svlens `conn` mode catches some lint
issues (width/type/dangling) but does not replace style/semantic lint.

Before installing missing required tools, ask the user:

> **Required tools missing: [list]**
> How would you like to install them?
> 1. `local` — install under ~/.local/bin (I'll execute directly, **recommended**)
> 2. `global` — print sudo commands for user to run manually
> 3. `docker` — use Docker EDA image as fallback (requires docker)
> 4. `skip` — skip for now (pipeline will NOT be fully functional)

### Q2: Optional/Recommended Tools (if any Tier 2-3 tools are missing)

> **Optional tools available for installation: [list with purpose]**
> Which would you like to install? (comma-separated numbers, 'all', or 'none')
> 1. jq — robust JSON parsing in hooks
> 2. yosys + sby — synthesis + formal verification
> 3. slang-server — SV LSP integration for Claude Code
> 4. iverilog — fallback simulator
> 5. gtkwave — waveform viewer

### Q2b: Commercial Tool Configuration

Only ask this if any commercial tools were scanned in Phase 1d. Group tools into two
lists: detected and undetected.

**For detected commercial tools** — confirm correctness: present the detected tools
(# / Tool / Vendor / Path) and ask whether these are the versions the user wants to use
(yes / no — correct individually / skip). If user says "no", ask which tool to correct
and what `env_source` command to use instead.

**For undetected commercial tools** — ask if the user has a setup script: present the
undetected tools (# / Tool / Vendor / Purpose) and ask the user to enter sourcing
commands in `number: command` format, or `skip`.

Exact prompt wording and example tables:
`references/output-templates.md` (§ Q2b Examples).

After collecting responses, verify each provided `env_source` by running:
```bash
bash -c "$env_source && command -v $tool" 2>/dev/null
```
Report results: if the tool is now found, mark as OK. If still not found, warn the user
and offer to re-enter or skip.

### Q2c: Synthesis Target Library (optional)

> **Synthesis target library configuration.**
> Providing a Liberty timing library (.lib) enables accurate gate-count estimation
> and is required for commercial synthesis (DC/Genus).
> Yosys works without a Liberty file using built-in models.
>
> 1. Provide path to Liberty file (.lib)
> 2. `skip` — no library (Yosys built-in model only)
>
> If providing a path, optionally specify:
> - Technology description (e.g., "TSMC 28nm", "Sky130")
> - NAND2 cell name pattern if different from default (default: `NAND2X1`)

If user provides a Liberty path, validate file exists:
```bash
test -f "$liberty_path" && echo "OK" || echo "File not found"
```

### Q3: Plugin Global Configuration

> **Plugin conventions can be deployed globally for access in ALL projects.**
> This makes RTL conventions available even without running `rat-init-project` per project.
> Deploy global configuration? (yes/no)
>
> What will be deployed:
> - `~/.claude/rules/rtl-coding-conventions.md` — port naming (i_/o_), clock/reset conventions
> - `~/.claude/rules/rtl-verification-gate.md` — mandatory lint→TB→sim after RTL changes
> - `~/.claude/CLAUDE.md` — diagram convention block (if not already present)

#### Diagram Rule Injection

Check if `~/.claude/CLAUDE.md` already contains `<markdown_diagram_rule>` tag.
- If tag found → skip (already deployed)
- If tag NOT found → append the following block:

```markdown
<markdown_diagram_rule>
## Diagram Policy

| Diagram Type | Tool | Use For |
|-------------|------|---------|
| **Block diagram** | **D2** | Architecture, module hierarchy, HW block decomposition |
| **Flow / Interaction** | **Mermaid** | Pipeline stages, FSM, data/control flow, sequence diagrams |
| **ASCII flow diagram** | **Prohibited** | Do NOT use ASCII art — use D2 or Mermaid |

D2: architecture diagrams (`.d2` code blocks), per-module internal structure.
Mermaid: FSM (`stateDiagram-v2`), data flow (`flowchart`), sequences (`sequenceDiagram`).
</markdown_diagram_rule>
```

Implementation:
```bash
if ! grep -q '<markdown_diagram_rule>' ~/.claude/CLAUDE.md 2>/dev/null; then
  # Append diagram rule block to ~/.claude/CLAUDE.md
  # Use Read tool to get current content, then Edit/Write to append
fi
```

### Q4: Test Infrastructure (if pytest/cocotb deps missing)

> **Test dependencies missing: [list]**
> Install via pip? (yes/no)
> ```
> python3 -m pip install --user pytest cocotb cocotb-bus numpy hjson
> ```

---

**IMPORTANT: After receiving all Q1-Q5 answers, immediately proceed to Phase 4 execution
in the same response. Do NOT pause or wait for user confirmation between Phase 3 and Phase 4.
The user has already made their decisions — execute them without an extra turn boundary.**

## Phase 4: Execute (based on user answers)

### 4a. Tool Installation

Execute installation commands based on Q1/Q2 answers.
- `local` mode: LLM executes directly (no sudo)
- `global` mode: print sudo commands for user to run manually
- `docker` mode: build Docker image if not present

**Actively look up the latest stable version** from official upstream sources before
giving install commands for fast-moving tools such as Verilator and SystemC. Exact
per-mode install scripts: `references/install-commands.md`.

### 4b. Commercial Tool Configuration (if Q2b answered)

For each tool where the user provided an `env_source` command or corrected a path,
record the information in the machine-wide env-config.json:

```bash
PLUGIN_DIR="${CLAUDE_PLUGIN_DATA:-$HOME/.config/rtl-agent-team}"
mkdir -p "$PLUGIN_DIR"
```

Store collected commercial tool sourcing commands in the `tools` section
of `$PLUGIN_DIR/env-config.json`. These values will be seeded into
per-project `rat_config.json` when `rat-init-project` runs `generate_config.sh`.

For each provided `env_source`, verify the tool is accessible:
```bash
bash -c "$env_source && command -v $tool" 2>/dev/null
```

Report verification results (Tool / env_source / Status: OK or FAILED). If a tool is not
found after sourcing, warn but proceed — the user can fix `env_source` later in
`rat_config.json` and re-run `generate_config.sh`.

### 4b-tech. Target Library Configuration (if Q2c answered)

If the user provided a Liberty file path:
1. Validate the file exists.
2. Extract NAND2 area using the same logic as `generate_config.sh` — exact awk script:
   `references/output-templates.md` (§ NAND2 Area Extraction).
3. Record the technology name, liberty path, NAND2 cell pattern, and extracted area in
   env-config.json's `technology` section (exact JSON shape in the same reference).
4. Report result: technology name, liberty path, extracted NAND2 area (or "not found in lib").

### 4c. Plugin Config Deployment (if Q3 = yes)

**RTL rules → `~/.claude/rules/`** (path-scoped, RTL files only):
```bash
mkdir -p ~/.claude/rules
# Non-destructive: only copy if target does not exist
[ ! -f ~/.claude/rules/rtl-coding-conventions.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/rules/rtl-coding-conventions.md" ~/.claude/rules/
[ ! -f ~/.claude/rules/rtl-verification-gate.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/rules/rtl-verification-gate.md" ~/.claude/rules/
```

**Diagram rule → `~/.claude/CLAUDE.md`** (tagged block, all projects):
```bash
# Only inject if tag not already present
if ! grep -q '<markdown_diagram_rule>' ~/.claude/CLAUDE.md 2>/dev/null; then
  # Read current ~/.claude/CLAUDE.md, append <markdown_diagram_rule> block via Edit/Write
fi
```
See Q3 section for the exact block content.

### 4d. Test Infra Installation (if Q4 = yes)

```bash
python3 -m pip install --user pytest cocotb cocotb-bus numpy hjson
```

---

## Phase 5: Verify & Final Report

Re-check installed tools and present final status: Tool Status by tier
(installed/total/PASS-PARTIAL), Commercial Tools, Target Technology, Plugin Configuration.

Exact template with example values:
`references/output-templates.md` (§ Phase 5 Final Report).

### Setup Marker + Environment Config (advisory)

Write setup completion marker and machine-wide EDA environment config to
`${CLAUDE_PLUGIN_DATA}` (persistent plugin data directory, survives plugin updates).
The actual enforcement gate remains `.claude/rules/rtl-coding-conventions.md` (project-level).

Exact bash (marker + env-config.json heredoc template):
`references/output-templates.md` (§ Setup Marker + Environment Config).

**Note to orchestrator**: The env-config.json `tools`/`preferences` placeholders must be
replaced with actual Phase 1 scan results, using the same detection logic and output
format as `generate_config.sh`.

### Next Steps
- Run `/rtl-agent-team:rat-init-project` in your project directory to initialize project structure
- Run `/rtl-agent-team:rat-tutorial` for a guided walkthrough of the pipeline

</Steps>

<Tool_Usage>
All EDA tools are executed via Bash CLI directly (never MCP). Run every Tier 1/2/3, test
infrastructure, commercial-tool, and plugin-config check command in parallel — the exact
commands live in `references/tool-check-commands.md`.

Interactive questions (Q1-Q4) use AskUserQuestion.
</Tool_Usage>

<Install_Instructions>
When tools are missing, provide installation commands based on the user's choice of
`local` (default), `global`, `docker`, or macOS (Homebrew). Before installing fast-moving
tools (Verilator, SystemC), resolve the latest stable version from upstream sources.
RHEL/CentOS-family distros may need a newer GCC toolset activated before source builds.

Exact commands for all modes: `references/install-commands.md`.
</Install_Instructions>

<Advanced>
## Docker EDA Image Details

Only needed when the user chooses the `docker` install mode (Q1) or asks about the
Docker EDA image build args, run commands, or included tool versions.

Read `references/docker-environment.md` for the build/run commands and
the included-tools version table.
</Advanced>

<Escalation_And_Stop_Conditions>
- Required tool not found → report with install commands, require installation
- Neither verible nor slang found → report as REQUIRED
- Only one of verible/slang → proceed with WARNING recommending the other
- Neither svlens nor commercial CDC tool (sg_shell/vc_cdc/questa_cdc) found → report as REQUIRED (svlens is open-source default)
- svlens missing but commercial CDC tool present → mark CDC requirement satisfied, still offer svlens install as open-source supplement
- Before installing → ask user: local (default) / global / docker / skip
- Before installing fast-moving tools → verify latest stable version from upstream
- Before deploying global rules → confirm with user (never overwrite existing)
- `jq` not found → report as recommended (hooks fall back to python/sed)
- Python version < 3.9 → report incompatibility
- Commercial tool detected → confirm with user before recording (Q2b)
- Commercial tool not detected → offer env_source entry, verify in subshell (Q2b)
- User-provided env_source fails verification → warn, allow re-entry or skip
- Liberty file path not found → warn, allow re-entry or skip (Q2c)
- NAND2 pattern not found in Liberty → warn, record liberty path with null area
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All EDA tools checked via Bash CLI (parallel) and categorized by tier
- [ ] Test infrastructure (pytest, cocotb-bus, numpy, hjson) checked
- [ ] Plugin config state (~/.claude/rules/) checked
- [ ] Categorized audit report displayed before asking questions
- [ ] Missing required tools trigger interactive Q1 (local/global/docker/skip)
- [ ] Optional tools offered selectively via Q2
- [ ] Global rule deployment offered via Q3 (non-destructive)
- [ ] Test infra installation offered via Q4
- [ ] Lint tool gate: at least one of verible/slang installed
- [ ] CDC tool gate: svlens OR commercial CDC (sg_shell/vc_cdc/questa_cdc) installed
- [ ] Fast-moving tools version-pinned from official upstream
- [ ] Docker EDA image status checked
- [ ] Commercial tools scanned (Phase 1d) and reported in Phase 2
- [ ] Detected commercial tools confirmed with user (Q2b)
- [ ] Undetected commercial tools: user offered env_source entry (Q2b)
- [ ] User-provided env_source commands verified via subshell test
- [ ] Target Liberty path collected or skipped (Q2c)
- [ ] If Liberty provided: NAND2 area extraction attempted
- [ ] Commercial tool + technology config written to env-config.json
- [ ] Final verification re-check after installation
- [ ] Next steps shown (rat-init-project, rat-tutorial)
</Final_Checklist>
