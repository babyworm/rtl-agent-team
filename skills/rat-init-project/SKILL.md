---
name: rat-init-project
description: "This skill should be used when initializing a new RTL project with directory structure, rules, guides, and template files. Triggers on 'init project', 'initialize project', 'new project', 'project init'."
user-invocable: true
---

<Purpose>
Initialize a new RTL design project with the standard directory structure, coding convention
rules, phase guides, and template files required by the 6-Phase pipeline.
This is a per-project operation — run once per new project workspace.
For EDA tool installation and environment verification, use `rat-setup` instead.
</Purpose>

<Use_When>
- Starting a new RTL/FPGA/ASIC design project
- First time using this plugin in a new workspace
- User says "init project", "initialize project", "new project", "project init"
- Agent Step 0 detects missing project structure (.claude/rules/ not found)
</Use_When>

<Do_Not_Use_When>
- Project directories already exist and rules are deployed (check `.claude/rules/rtl-coding-conventions.md`)
- Only need to verify/install EDA tools (use `rat-setup`)
- Designing architecture or writing RTL (use p2-arch-design or rtl-p4-implement)
</Do_Not_Use_When>

<Why_This_Exists>
The 6-Phase pipeline expects a standard directory layout (rtl/, refc/, bfm/, sim/, lint/, syn/, etc.)
and coding convention rules deployed to `.claude/rules/`. Without proper project initialization,
agents fail with missing directory errors and coding conventions are not enforced.
This skill ensures the project workspace is ready before design work begins.
</Why_This_Exists>

<Execution_Policy>
- Non-destructive: never overwrite existing files or directories
- Create only the directories and files that don't already exist
- Generate a project initialization report at the end
- Quick EDA tool status check (informational only — does NOT install tools)
- If required tools are missing, recommend running `/rat-setup` for installation
</Execution_Policy>

<Steps>
1. **Check plugin setup** (advisory, not a hard gate):
   Check `${CLAUDE_PLUGIN_DATA:-$HOME/.config/rtl-agent-team}/.setup-complete` for `rat-setup` completion.
   If marker is missing, advise: "Run `/rtl-agent-team:rat-setup` first to verify EDA tools and configure the plugin environment."
   Proceed anyway — project structure can be created without tools, but warn about missing EDA environment.

1a. **Check project root**: Verify current directory is suitable (has .git or is empty).

2. **Create directory structure** (skip existing):
   ```
   specs/              # Input specifications and datasheets
   refc/               # C reference model (DPI-C compatible)
     include/          # Common ref model headers
     build/            # Build output (.so for DPI-C)
   bfm/                # Bus Functional Models
     include/          # Common BFM headers
   rtl/                # Synthesizable SystemVerilog source
     common/           # Shared utility modules (ICG, synchronizer, CDC primitives)
     include/          # Common defines, packages
     top/              # Top-level module instantiation
   sim/                # Simulation & testbenches
     top/              # Tier 4: integration tests
     formal/           # SVA formal verification (.sby configs)
   lint/               # Lint flow
     scripts/          # Lint scripts (run_lint.sh)
     reports/          # Per-module lint results
   syn/                # Synthesis flow
     scripts/          # Synthesis scripts (run_syn.sh)
     reports/          # Per-module synthesis results
   docs/               # Design documentation
     phase-1-research/   # Phase 1 artifacts
     phase-2-architecture/ # Phase 2 artifacts
     phase-3-uarch/      # Phase 3 artifacts
     phase-4-rtl/        # Phase 4 artifacts
     phase-5-verify/     # Phase 5 artifacts
     decisions/          # Architecture Decision Records (ADR)
   reviews/            # Phase gate review reports (Markdown)
     phase-1-research/
     phase-2-architecture/
     phase-3-uarch/
     phase-4-rtl/
     phase-5-verify/
     phase-6-review/    # Phase 6 review deliverables
   .rat/
     state/            # Plugin state files (auto-managed)
   ```
   Note: Per-module subdirectories under `refc/`, `bfm/`, `rtl/`, `sim/` are created
   during Phase 2 (architecture) when module decomposition is decided.

2a. **Inject project CLAUDE.md** (RAT-managed section):
   Run the injection script to create or update the RAT-managed section in the project root CLAUDE.md.
   User content outside `<!-- RAT:START -->` / `<!-- RAT:END -->` tags is never modified.
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/scripts/inject_claude_md.sh" .
   ```
   Idempotent — safe to re-run on every `rat-init-project` invocation.

2b. **Generate project config** (`rat_config.json`):
   Run the config generator to detect available EDA tools and create the project configuration file.
   If `rat_config.json` already exists, only tool availability is refreshed (user-edited fields preserved).
   ```bash
   bash "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/scripts/generate_config.sh" . "$(basename $(pwd))"
   ```
   The config file stores:
   - `tools`: 24 EDA tools across 8 categories (simulators, synthesis, lint, formal, equivalence, cdc, debug, coverage). Each tool has `detected`, `path`, and `env_source` fields. Set `env_source` per-tool for tools needing setup (e.g., `"env_source": "source /tools/synopsys/vcs/setup.sh"`)
   - `preferences`: preferred tool per category (auto-set to first detected commercial tool, user-overridable)
   - `technology`: target library path, SRAM lib, NAND2 cell pattern (auto-extracted from liberty if set)
   - `coverage`: targets (line≥90%, toggle≥80%, FSM≥70%, branch≥80%, functional≥95%), seeds, fail rate
   - `waivers`: custom paths for lint/CDC waiver files
   Users should edit per-tool `env_source`, `technology.liberty`, and `waivers` after generation.

2c. **Deploy rules** (skip if already deployed globally via `rat-setup`):
   For each rule file, check `~/.claude/rules/` first. If the same file exists globally,
   skip the local copy to avoid duplicate injection. Only deploy locally if neither exists.
   Diagram rules are injected into `~/.claude/CLAUDE.md` by `rat-setup` via `<markdown_diagram_rule>` tag.
   If the tag is missing (rat-setup not run), write an inline fallback file.
   ```bash
   mkdir -p .claude/rules
   # RTL rules: skip if global exists (no duplication)
   [ ! -f ~/.claude/rules/rtl-coding-conventions.md ] && [ ! -f .claude/rules/rtl-coding-conventions.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/rules/rtl-coding-conventions.md" .claude/rules/
   [ ! -f ~/.claude/rules/rtl-verification-gate.md ] && [ ! -f .claude/rules/rtl-verification-gate.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/rules/rtl-verification-gate.md" .claude/rules/
   ```
   If `grep -q '<markdown_diagram_rule>' ~/.claude/CLAUDE.md` fails AND `.claude/rules/diagram-rules.md`
   does not exist, use Write tool to create `.claude/rules/diagram-rules.md` with:
   ```markdown
   ---
   paths:
     - "docs/**/*.md"
     - "reviews/**/*.md"
   ---
   # Diagram Policy
   | Diagram Type | Tool | Use For |
   |-------------|------|---------|
   | **Block diagram** | **D2** | Architecture, module hierarchy, HW block decomposition |
   | **Flow / Interaction** | **Mermaid** | Pipeline stages, FSM, data/control flow, sequence diagrams |
   | **ASCII flow diagram** | **Prohibited** | Do NOT use ASCII art — use D2 or Mermaid |
   ```

2d. **Deploy guides** (copy CLAUDE.md to each directory if not already present):
   ```bash
   # Copy guide files as CLAUDE.md into each artifact directory (non-destructive)
   [ ! -f rtl/CLAUDE.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/guides/rtl-guide.md" rtl/CLAUDE.md
   [ ! -f sim/CLAUDE.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/guides/sim-guide.md" sim/CLAUDE.md
   [ ! -f docs/CLAUDE.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/guides/docs-guide.md" docs/CLAUDE.md
   [ ! -f reviews/CLAUDE.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/guides/reviews-guide.md" reviews/CLAUDE.md
   [ ! -f refc/CLAUDE.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/guides/refc-guide.md" refc/CLAUDE.md
   [ ! -f syn/CLAUDE.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/guides/syn-guide.md" syn/CLAUDE.md
   ```

3. **Generate lessons-learned.md** (if docs/lessons-learned.md does not exist):
   Create `docs/lessons-learned.md` with initial header:
   ```markdown
   # Lessons Learned

   > Cross-phase knowledge base. Entries are appended after each bug fix (especially Phase 5→4 feedback).
   > Agents in Phase 4/5 should read this file to avoid repeating known issues.
   >
   > Entry format: LL-{NNN} with sections: Symptom, Root Cause, Fix Applied, Prevention, Related (REQ IDs, module, fix commit, ADR, Phase 5 Sub-phase)

   ---
   ```

4. **Generate filelist templates** (if rtl/ has no .f files):
   - Copy `skills/rat-init-project/templates/filelist.f` to `rtl/filelist_top.f` as starting point.
   - Per-module filelists (`rtl/filelist_{module}.f`) are created during Phase 4 when modules are coded.
   - **Filelist convention (3 types):**
     | Type | Location | Required |
     |------|----------|----------|
     | Module-level | `rtl/filelist_{module}.f` | MUST exist per module |
     | Top-level | `rtl/filelist_top.f` | MUST exist (includes module filelists) |
     | TB/test | in sim/ scope | Dynamic (scripts add at runtime) |

4.5. **Install run_sim.sh** (if scripts/run_sim.sh does not exist):
   Copy `scripts/run_sim.sh` and make executable:
   ```bash
   chmod +x scripts/run_sim.sh
   ```
   This simulator-agnostic script supports iverilog, verilator, vcs, xrun, questa.

4.7. **Install EDA scripts** (if script folders are empty):
   Create lint, synthesis, CDC, and equivalence checking scripts plus the shared tool runner library.
   All scripts use `lib/tool-runner.sh` for transparent Docker fallback when local tools are missing.
   - **Tool runner**: `lib/tool-runner.sh` — `run_tool()` tries local binary first, falls back to persistent Docker container
   - **Lint**: `lint/scripts/run_lint.sh` — verilator/verible/slang + spyglass
   - **Synthesis**: `syn/scripts/run_syn.sh` — yosys + dc_shell (Synopsys) + genus (Cadence)
   - **Equivalence checking**: `syn/scripts/run_formality.sh` (Synopsys) + `syn/scripts/run_conformal.sh` (Cadence)
   - **CDC**: `sim/cdc/run_cdc.sh` — structural quick check + spyglass/vc_cdc/questa_cdc
   - Runtime hook integration: `hooks/rtl-skill-activation.sh` runs
     `skills/rat-init-project/scripts/install_project_templates.sh` automatically when `rat-init-project` starts.

4.9. **Deploy project Makefile** (if project root has no Makefile):
   Copy the unified build system Makefile that wraps all EDA scripts:
   ```bash
   [ ! -f Makefile ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/Makefile" Makefile
   ```
   Open-source tools by default (`make sim`, `make lint`, `make syn`, `make formal`).
   Commercial EDA via `_tool` suffix (`make sim_xrun`, `make lint_spyglass`, `make syn_dc`).
   Run `make help` to see all targets and variables.

4.10. **Deploy UVM regression runner** (if sim/uvm/scripts/ has no run_regression_uvm.sh):
   ```bash
   mkdir -p sim/uvm/scripts
   [ ! -f sim/uvm/scripts/run_regression_uvm.sh ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rtl-p5s-uvm-verify/scripts/run_regression_uvm.sh" sim/uvm/scripts/run_regression_uvm.sh && chmod +x sim/uvm/scripts/run_regression_uvm.sh
   ```
   Multi-seed UVM regression with VCS/Xcelium/Questa, coverage merge, failure halt.
   Referenced by Makefile `uvm_regression` target.

5. **Generate cocotb Makefile template** (if sim/ has no Makefile):
   Copy `skills/rat-init-project/templates/cocotb-makefile` to `sim/top/Makefile` as reference.
   Per-module cocotb Makefiles are created in `sim/{module}/Makefile` during Phase 4-5.

5.5. **Deploy Phase 6 PDF Makefile** (if reviews/phase-6-review/ has no Makefile):
   Copy `skills/rat-init-project/templates/phase6-pdf-makefile` to `reviews/phase-6-review/Makefile`.

5.7. **Generate SV testbench template** (inform user):
   Reference `skills/rtl-p4s-unit-test/templates/sv-testbench-template.sv` for Tier 2 unit tests.
   Replace `{{MODULE_NAME}}` and `{{DOMAIN}}` placeholders when creating per-module TBs.

6. **Generate module template** (if rtl/ has no .sv files):
   Create `rtl/include/template_module.sv` demonstrating project naming conventions:
   ```systemverilog
   // template_module.sv — Template demonstrating project coding conventions
   // Style: lowRISC SV Style Guide + project overrides (i_/o_ prefix, {domain}_clk/rst_n)
   module template_module
     import template_module_pkg::*;
   #(
     parameter int DATA_WIDTH = 32
   ) (
     input  logic                  sys_clk,       // Clock: {domain}_clk format
     input  logic                  sys_rst_n,     // Reset: {domain}_rst_n format
     input  logic [DATA_WIDTH-1:0] i_data,        // Input: i_ prefix
     input  logic                  i_valid,       // Input: i_ prefix
     output logic [DATA_WIDTH-1:0] o_result,      // Output: o_ prefix
     output logic                  o_ready        // Output: o_ prefix
   );
     // Use logic only (no reg/wire), typedef enum for FSM, u_ instance prefix, gen_ generate prefix
   endmodule
   ```

7. **Quick EDA tool status** (informational only, does NOT install):
   Check availability of required tools and report status.
   If any required tool is missing, recommend: "Run `/rtl-agent-team:rat-setup` to install missing tools."

8. **Report project initialization summary**:
   ```
   ## RTL Project Initialization Report
   - Directory structure: [N] directories created, [M] already existed
   - Rules deployed: .claude/rules/ ([2] files + diagram-rules fallback if needed)
   - Guides deployed: [6] CLAUDE.md files
   - Templates: filelist, Makefile, EDA scripts, module template
   - Coding conventions: lowRISK SV Style + project overrides
     - Port prefix: i_/o_/io_ (NOT suffix _i/_o)
     - Clock: {domain}_clk (e.g., sys_clk)
     - Reset: {domain}_rst_n (e.g., sys_rst_n)
   - EDA tools: [X/Y] required tools available
   - Missing tools: [list] → run /rtl-agent-team:rat-setup to install
   - Project ready: Yes/No
   ```
</Steps>

<Tool_Usage>
```
# Directory creation (Bash CLI)
Bash: mkdir -p specs refc/include refc/build bfm/include rtl/common rtl/include rtl/top sim/top sim/formal sim/cdc sim/cdc/reports lint/scripts lint/reports syn/scripts syn/reports syn/constraints docs/phase-{1-research,2-architecture,3-uarch,4-rtl,5-verify,7-exploration} docs/decisions reviews/phase-{1-research,2-architecture,3-uarch,4-rtl,5-verify,6-review,7-exploration} .rat/state .rat/scratch

# Rules deployment (skip if already global, non-destructive)
Bash: mkdir -p .claude/rules
Bash: [ ! -f ~/.claude/rules/rtl-coding-conventions.md ] && [ ! -f .claude/rules/rtl-coding-conventions.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/rules/rtl-coding-conventions.md" .claude/rules/ || true
Bash: [ ! -f ~/.claude/rules/rtl-verification-gate.md ] && [ ! -f .claude/rules/rtl-verification-gate.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/rules/rtl-verification-gate.md" .claude/rules/ || true
# Diagram rules: if <markdown_diagram_rule> tag missing from ~/.claude/CLAUDE.md,
# use Write tool to create .claude/rules/diagram-rules.md with inline content (see Step 2a)

# Guide deployment (non-destructive, copy as CLAUDE.md)
Bash: [ ! -f rtl/CLAUDE.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/guides/rtl-guide.md" rtl/CLAUDE.md || true
Bash: [ ! -f sim/CLAUDE.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/guides/sim-guide.md" sim/CLAUDE.md || true
Bash: [ ! -f docs/CLAUDE.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/guides/docs-guide.md" docs/CLAUDE.md || true
Bash: [ ! -f reviews/CLAUDE.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/guides/reviews-guide.md" reviews/CLAUDE.md || true
Bash: [ ! -f refc/CLAUDE.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/guides/refc-guide.md" refc/CLAUDE.md || true
Bash: [ ! -f syn/CLAUDE.md ] && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/guides/syn-guide.md" syn/CLAUDE.md || true

# Quick tool status (informational)
Bash: verilator --version 2>&1 || echo "NOT_FOUND"
Bash: python3 -c "import cocotb; print(cocotb.__version__)" 2>&1 || echo "NOT_FOUND"
Bash: verible-verilog-lint --version 2>&1 || echo "NOT_FOUND"
Bash: slang --version 2>&1 || echo "NOT_FOUND"

# Template generation (copy from plugin templates)
Bash: cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/filelist.f" rtl/filelist_top.f
Bash: cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/cocotb-makefile" sim/top/Makefile
Bash: mkdir -p lib && cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/lib/tool-runner.sh" lib/tool-runner.sh
Bash: cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/run_lint.sh" lint/scripts/run_lint.sh
Bash: cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/run_syn.sh" syn/scripts/run_syn.sh
Bash: cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/run_cdc.sh" sim/cdc/run_cdc.sh
Bash: cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/run_formality.sh" syn/scripts/run_formality.sh
Bash: cp "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/run_conformal.sh" syn/scripts/run_conformal.sh
Bash: mkdir -p reviews/phase-6-review && cp -n "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/templates/phase6-pdf-makefile" reviews/phase-6-review/Makefile
Bash: chmod +x lib/tool-runner.sh lint/scripts/run_lint.sh syn/scripts/run_syn.sh sim/cdc/run_cdc.sh syn/scripts/run_formality.sh syn/scripts/run_conformal.sh
Bash: chmod +x scripts/run_sim.sh
# Hook-safe bootstrap (non-destructive, idempotent)
Bash: bash "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/scripts/install_project_templates.sh" "$PWD"
Write: rtl/include/template_module.sv — convention reference template (i_/o_ prefix, sys_clk/sys_rst_n)
```

**All EDA tools are executed via Bash CLI directly. No MCP tool servers for EDA.**
</Tool_Usage>

<Escalation_And_Stop_Conditions>
- Directory creation permission denied → report error, suggest user fix permissions
- Existing project detected (rtl/ has .sv files in subdirectories) → warn user, ask whether to skip template generation
- No write access to project directory → halt, cannot create structure
- Required EDA tools missing → recommend `/rtl-agent-team:rat-setup` (do NOT attempt installation here)
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] All required directories exist
- [ ] Rules deployed to .claude/rules/ (2 rule files + diagram-rules fallback if needed)
- [ ] Guides deployed as CLAUDE.md (6 files)
- [ ] Template files created for empty directories
- [ ] Module template (rtl/include/template_module.sv) demonstrates naming conventions
- [ ] EDA scripts installed (lint, synthesis, CDC, equivalence, tool-runner)
- [ ] Quick tool status reported
- [ ] Missing tools → recommended /rat-setup
- [ ] Project initialization report displayed to user
</Final_Checklist>
