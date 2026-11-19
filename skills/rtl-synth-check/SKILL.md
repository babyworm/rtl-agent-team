---
name: rtl-synth-check
description: "Synthesis and constraint checks using configured tools and technology. Use for 'synth check', 'area/timing estimate', 'generate SDC'."
user-invocable: true
---

Synthesize the requested lint-clean RTL scope with the selected technology and
`preferences.synthesis`. Do not assume Yosys, NanGate45, a 28nm process, a fixed
clock, or a universal NAND2 area. Preserve the user's explicit target and overrides.

Use constraint-writer when clock/IO constraints need producing from a settled
specification. Save syn/constraints/design.sdc before timing-driven synthesis.
An absent timing requirement is not permission to invent one. An area-only or
unconstrained estimate must name that scope. `references/sdc-best-practices.md`
contains tool-specific SDC details when needed.

Run the wrapper through eda-runner for the actual tool invocation:

```bash
syn/scripts/run_syn.sh --tool auto --top {top} -f {filelist}
```

The runner consumes configured tool paths, environments and execution backend.
DC requires technology.db; Genus uses the configured Liberty library. Missing
libraries block mapped synthesis. `--allow-unmapped` is only for an explicit
exploratory run; its UNMAPPED result is not signoff. A required gate cannot pass
as SKIPPED. Do not run sv2v separately: the Yosys wrapper owns that conversion.
Read `references/yosys-commands.md` only for a Yosys-specific issue.

Outputs are syn/log/, syn/rpt/, syn/vnet/, and syn/rpt/syn_result.json (tool, log,
mapping status and process completion). Parse reports directly, without a report
agent:

```bash
"${RAT_PYTHON:-python3}" {plugin_root}/scripts/parse_synthesis.py --root {project} --tool {selected-tool} --log {synthesis-log}
```

The Yosys parser writes syn/summary.json; DC/Genus use the report directory. Report
latches, unsupported/unmapped cells, the library and constrained scope. NAND2
 equivalents require mapped area and technology.nand2_area_um2. Keep an estimate,
a completed tool process, and actual silicon signoff distinct.
