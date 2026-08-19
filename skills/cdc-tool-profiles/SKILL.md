---
name: cdc-tool-profiles
description: "Internal reference: cdc tool profiles (agent-loaded; do not invoke)."
user-invocable: false
---

# CDC & Structural Analysis Tool Profiles

## Quantitative + Qualitative Gate Philosophy

svlens provides **quantitative measurements** (scores, violation counts, complexity metrics)
to add consistency to the LLM's **qualitative judgment**. Phase gate decisions require BOTH:

1. **Quantitative**: svlens tool reports (JSON) — violation counts, health scores, complexity metrics
2. **Qualitative**: LLM assessment of design intent, context, and risk

Neither alone is sufficient. A zero-violation svlens report does not auto-pass a gate if the LLM
identifies architectural concerns. Conversely, the LLM cannot override quantitative violations
without documented justification (waiver with rationale).

When **commercial tools** are available, they serve as the **signoff authority**. svlens provides
supplementary crosscheck data — useful for early-stage CI, pre-signoff screening, and adding
quantitative rigor to LLM-driven reviews.

## Common Contract
- Prefer wrapper: `lint/scripts/run_cdc.sh`
- Output classes:
  - `VIOLATION`
  - `CAUTION`
  - `CONVENTION`
  - `INFO`
  - `WAIVED`
- Gate fail when unwaived `VIOLATION` exists.

## Open-Source Baseline: svlens (https://github.com/babyworm/svlens)

svlens is a unified structural analysis toolkit with three modes sharing one elaboration:

### svlens cdc — Clock Domain Crossing Analysis
- `lint/scripts/run_cdc.sh --tool structural --top <top> -f rtl/filelist_top.f --outdir lint/cdc`
  (structural mode auto-runs svlens crosscheck when installed)
- `lint/scripts/run_cdc.sh --tool svlens --top <top> -f rtl/filelist_top.f --outdir lint/cdc`
  (standalone mode)
- 8 synchronizer patterns (2-FF, 3-FF, gray, handshake, async FIFO, MUX, pulse, Johnson)
- Quality checks: reconvergence, glitch path, fan-out-before-sync, reset sync, non-2^N FIFO
- Outputs: md + json + sdc + waiver yaml
- Key JSON fields: `summary.violations`, `summary.cautions`, per-crossing `severity` + `sync_type`

### svlens conn — Port Connectivity Analysis
- `svlens conn --format all --top <top> -f rtl/filelist_top.f -o sim/conn/reports`
- Width mismatch, type mismatch, dangling output, undriven input detection
- Protocol completeness (`--check-protocol`), naming convention (`--check-convention`)
- Expected connectivity validation (`--expect connectivity_spec.yaml`)
- Key JSON fields: `analysis.overall_score`, `analysis.module_health`, `summary.errors`

### svlens metrics — RTL Transformation Complexity
- `svlens metrics --format all --top <top> -f rtl/filelist_top.f -o sim/metrics/reports`
- Output-rooted and FF-D-rooted backward transformation cones
- FF-to-FF combinational complexity with provenance levels
- Key JSON fields: per-root `logic_depth_est`, `raw_node_count`, `source_inputs`
- Interpretation: `logic_depth_est` > 15-20 = timing risk, `source_inputs` > 20 = complex convergence

### svlens all — Combined Mode
- `svlens all --format all --top <top> -f rtl/filelist_top.f -o sim/svlens/reports`
- Single elaboration, three output directories: `conn/`, `cdc/`, `metrics/`
- Produces `svlens_summary.json` with aggregated results
- Baseline diff support: `--diff baseline/` for regression detection

### Installation
```bash
git clone https://github.com/babyworm/svlens.git ~/tools/svlens
cd ~/tools/svlens
./scripts/setup-deps.sh --prefix ~/.local
cmake -B build -DCMAKE_PREFIX_PATH=~/.local
cmake --build build -j$(nproc)
cmake --install build --prefix ~/.local
```

## Commercial Profiles
- `spyglass` (binary: `sg_shell`, config key: `sg_shell`, script flag: `--tool spyglass`):
  - `lint/scripts/run_cdc.sh --tool spyglass --top <top> -f rtl/filelist_top.f --outdir lint/cdc`
  - Note: `rat_config.json` uses `sg_shell` as tool key; runner scripts accept `--tool spyglass`
- `vc_cdc` (binary: `vc_static_shell`, script flag: `--tool vc_cdc`):
  - `lint/scripts/run_cdc.sh --tool vc_cdc --top <top> -f rtl/filelist_top.f --outdir lint/cdc`
  - Note: `vc_cdc` is the Synopsys **app** name; VC SpyGlass CDC runs inside the VC
    Static shell, so the executable is `vc_static_shell`
- `questa_cdc`:
  - `lint/scripts/run_cdc.sh --tool questa_cdc --top <top> -f rtl/filelist_top.f --outdir lint/cdc`

## Invocation Reference

The exact binaries and batch switches the runner uses. These are the shapes each
vendor documents; changing them silently breaks the stage.

| Tool | Invocation | Why this shape |
|------|------------|----------------|
| `structural` / `svlens` | `svlens cdc --format all -o <outdir>` | — |
| `spyglass` | `sg_shell -tcl <tcl>` | — |
| `vc_cdc` | `vc_static_shell -f <tcl> -batch` | `vc_cdc` is an app name, not an executable. `-batch` makes the shell quit on an unexpected error instead of dropping to a prompt |
| `questa_cdc` | `qverify -c -do <do> -od <outdir>` | `-c` selects CLI/batch. Without `-od` the session database lands in the default location while the runner reports under `--outdir` |

## Normalized Result Fields
- `tool`
- `violations_count`
- `cautions_count`
- `info_count`
- `report_path`
- `replay_path`
