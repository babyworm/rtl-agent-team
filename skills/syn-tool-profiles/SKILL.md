---
name: syn-tool-profiles
description: "Internal reference: syn tool profiles (agent-loaded; do not invoke)."
user-invocable: false
---

# Synthesis Tool Profiles

## Common Contract
- Prefer wrapper: `syn/scripts/run_syn.sh`
- Synthesis is mandatory at block/top gate levels.
- Normalize output into:
  - `tool`, `status`, `area`, `timing_summary`, `log_path`, `replay_path`
- Multicore: DC/Genus scripts request `--max-cores` (default 8) via
  `set_host_options` / `set_db max_cpus_per_server`. Tools auto-limit to the
  licensed/physical maximum, so over-requesting is safe (graceful degradation).
- Memory wrappers: behavioral SRAM (`sram_sp/tp/dp`) keeps its 2-D array under
  `synopsys translate_off`, so DC/Genus skip it. With no compiled macro linked,
  `run_syn.sh` blackboxes the wrapper (`set_dont_touch` + `set_disable_timing`) and
  WARNs. Select a process with `--mem-process` and link the macro with `--mem-lib`
  for real timing/area. See the synth-memory-blackbox design spec.

## Output Directory Structure (DC-standard)
```
syn/
├── db/      — Binary databases (.ddc, .db, .genus_db)
├── vnet/    — Gate-level netlists (.v, .json)
├── svf/     — Setup Verification Flow (.svf, DC only)
├── scr/     — Generated scripts (.tcl, .ys) + replay/
├── rpt/     — Reports (area, timing, power, qor)
├── log/     — Synthesis logs
├── temp/    — Cache and temporary files
└── work/    — Tool work directories
```

## Open-Source Baseline
- `yosys`:
  - `syn/scripts/run_syn.sh --tool yosys --top <top> -f rtl/filelist_top.f`
  - Optional lib mapping:
    - `syn/scripts/run_syn.sh --tool yosys --top <top> -f rtl/filelist_top.f --liberty <lib>`

## Commercial Profiles
- `dc_shell`:
  - `syn/scripts/run_syn.sh --tool dc_shell --top <top> -f rtl/filelist_top.f`
  - Optional:
    - `--liberty <tech.lib> --sdc <design.sdc> --script <dc.tcl> --max-cores <n>`
    - Memory: `--mem-process <NAME> --mem-lib <macro.db> --mem-module <name> --mem-strict`
  - Outputs: `.ddc` → `syn/db/`, netlist → `syn/vnet/`, `.svf` → `syn/svf/`, `.synopsys_dc.setup` → `syn/scr/`
- `genus`:
  - `syn/scripts/run_syn.sh --tool genus --top <top> -f rtl/filelist_top.f`
  - Optional:
    - `--liberty <tech.lib> --sdc <design.sdc> --script <genus.tcl> --max-cores <n>`
    - Memory: `--mem-process <NAME> --mem-lib <macro.db> --mem-module <name> --mem-strict`
  - Outputs: `.genus_db` → `syn/db/`, netlist → `syn/vnet/`
- `vivado` (FPGA):
  - `syn/scripts/run_syn.sh --tool vivado --top <top> --script <vivado.tcl>`
  - `--script` is **mandatory**: part number, XDC and IP handling are
    project-specific, so there is no generic non-project recipe to auto-generate.
    The Tcl must carry its own `synth_design -top <top> -part <part>` flow.
  - `-f`, `--liberty` and the `--mem-*` options do not apply — the Tcl owns source
    and constraint loading.

## Invocation Reference

The exact binaries and batch switches the runner uses. These are the shapes each
vendor documents; changing them silently breaks the stage.

| Tool | Invocation | Why this shape |
|------|------------|----------------|
| `yosys` | `yosys -s <ys>` | — |
| `dc_shell` | `dc_shell -64bit -f <tcl>` | Synopsys shells spell the switch `-64bit` |
| `genus` | `genus -batch -files <tcl>` | Without `-batch` Genus keeps an interactive shell alive after sourcing. `-64` is an RTL-Compiler-era switch — Genus is 64-bit only and newer releases reject it |
| `vivado` | `vivado -mode batch -source <tcl> -nojournal -nolog` | Batch mode exits when the script finishes; Tcl mode would return to a prompt. Suppressing the journal/log keeps parallel runs from colliding |

## Tool Availability Tiers

| Tier | Tools | Capabilities | sv2v Handling |
|------|-------|-------------|---------------|
| 1 (commercial) | dc_shell, genus | Full synthesis + timing + area + PPA | Not needed (native SV support) |
| 2 (oss) | yosys | Latch detection, unmapped cells, basic area estimate | Script handles internally (Layer 2) |
| 3 (none) | — | Synthesis skipped with WARNING | N/A |

Use `get_synthesis_tier()` from `lib/tool-runner.sh` to determine tier at runtime.

**sv2v Policy**: sv2v is a **Layer 2 concern** — `run_syn.sh` handles it internally for Yosys.
Agent prompts and policy skills MUST NOT instruct manual sv2v execution.
Canonical source stays SystemVerilog; tool adaptation is the script's responsibility.

**`--skip-if-unavailable` flag**: When passed to `run_syn.sh`, tool absence or license failure
produces WARNING + clean exit (exit 0) instead of hard failure. Use in optional synthesis contexts
(Stream B smoke test, V8 estimation without commercial tools).

## Gate Criteria
- `FAIL`: tool fatal error, netlist generation failure, or unusable report
- `PASS`: synthesis completes and required summary artifacts are generated
- `SKIPPED`: tool not available and `--skip-if-unavailable` was set (non-blocking)
