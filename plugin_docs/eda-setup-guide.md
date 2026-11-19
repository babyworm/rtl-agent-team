# EDA Tool Setup Guide

This guide covers how to configure EDA tools for use with the RTL Agent Team plugin.
`/rtl-agent-team:rat-setup` uses the user's target host, existing configuration and
measured capability gaps to prepare local or remote tools. For commercial EDA,
the LLM discovers the site and writes `rat_config.json`; users need not transcribe
paths or author JSON. Installation follows the user's authorized scope.

## Tool Integration Architecture

```
                /rtl-agent-team:rat-setup
                            |
              +-----------+---+-----------+
              |                           |
     Open-Source Tools            Commercial Tools
     (scoped install)             (site discovery)
              |                           |
        verilator, yosys,          VCS, DC, Xcelium,
        slang, cocotb, ...         Genus, SpyGlass, ...
              |                           |
              +------+------+------+------+
                     |             |
              generate_config.sh   |
                     |             |
               rat_config.json  <--+
                     |
                 config.mk
                     |
          run_sim.sh / run_syn.sh / run_lint.sh / ...
```

### Three integration paths

| Path | Tools | Setup | Configuration |
|------|-------|-------|---------------|
| **Auto-install** | Verilator, Verible, slang, svlens, cocotb, Yosys, SystemC, ... | `/rtl-agent-team:rat-setup` handles everything | Automatic |
| **Commercial** | VCS, DC, Xcelium, Genus, SpyGlass, Questa, Formality, VC-CDC, Questa CDC, ... | LLM discovers the named site and verifies selected tools | Named site profile → project `rat_config.json` |
| **Docker fallback** | All open-source tools bundled | Build from the standalone plugin clone root | Transparent via `lib/tool-runner.sh` |

---

## Open-Source Tools

Run `/rtl-agent-team:rat-setup` and follow the interactive wizard. It detects missing tools,
offers installation choices (`local` / `global` / `docker` / `skip`), and verifies
the result. No manual configuration needed.

### Phase-scoped readiness

Use `scripts/eda_runner.py capabilities --root <project> --phase p1|p2|p3|p4|p5a|p5b|all`.
P1 requires no EDA tools; P2/P3 require a C/C++ build toolchain; P4/P5A require a
suitable simulator and linter; P5B requires synthesis. Add `--bfm` for a SystemC/TLM
model, `--multiclock` for CDC, and `--signoff` for PrimeTime and technology.db.
Cocotb is required only for its selected verification path, not for commercial UVM.
Remote readiness is unprobed until `--probe-remote` measures the execution host. Docker probes
run inside the selected image. Executable presence does not establish a license
or a passed silicon check.

---

## Commercial Tool Configuration

### LLM-assisted SSH setup

Tell `/rtl-agent-team:rat-setup` the intended SSH execution host. The LLM reuses an
existing named profile or discovers the host, selects a
remote Python >=3.9, checks the chosen tools, prepares project configuration and
runs the smallest relevant real operation. Unknown site environment commands or
technology choices remain open; known values are not asked again.

Profiles live under `${CLAUDE_PLUGIN_DATA:-$HOME/.config/rtl-agent-team}/sites/`.
Each project selects a site; no host is a plugin-wide default. Credentials and jump
hosts remain in SSH configuration. Existing user paths, preferences, libraries,
queues and output settings are preserved. A private workspace is proposed when
none is supplied. Use `--dry-run` to inspect configuration without writing it.
Keep real profiles, connection details and raw qualification reports outside the
plugin repository. Only synthetic site fixtures belong in public docs/tests/evals.

The installed helper is `scripts/eda_setup.py` (also deployed to project `lib/`).
It provides `discover`, `probe --record`, and `configure`; the complete conditional
workflow is in [the setup reference](../skills/rat-setup/references/remote-site-setup.md).
`eda_runner.py capabilities --probe-remote` reports executable/framework readiness,
with `license_checked: false`. A version probe does not prove license checkout.
Failed probes are bound to their tool/environment configuration and prevent a
known broken candidate from being selected automatically.

Commercial EDA tools (Synopsys, Cadence, Siemens) are typically installed by IT
or a CAD team and require environment setup (PATH, library paths, environment variables)
before they can be invoked. The plugin handles this through the `env_source` field
in `rat_config.json`.

### How `env_source` works

Tool entries support path, env_source, env_shell, detected, and optional license_wait_args:

```json
"vcs": {
  "detected": false,
  "path": "",
  "env_source": ""
}
```

| Field | Purpose | Who fills it |
|-------|---------|-------------|
| `detected` | Whether the tool was found during last scan | `generate_config.sh` (automatic) |
| `path` | Absolute path to the tool binary | `generate_config.sh` (automatic) or user |
| `env_source` | Shell command to set up the tool environment | **User** (manual) |

`env_source` is trusted project input: the generator and runner evaluate it in the configured bash/csh/tcsh environment. Keep this field project-owned and never populate it from untrusted data.

When `generate_config.sh` runs, it:
1. Reads `env_source` for each tool
2. Executes trusted project input positionally in a subshell, suppressing setup
   banners before probing the tool: `bash -c 'eval "$1" >/dev/null 2>&1 && command -v -- "$2"' _ "$env_source" "$tool"`
3. If the tool is found after sourcing, marks `detected: true` and records `path`

**The key insight**: you only need to fill in `env_source` with the command that makes
the tool available in your shell. The detection and path recording happen automatically.

### Environment setup patterns

There are three common ways commercial tools are set up. Use whichever matches
your site's configuration.

#### Pattern 1: Source a setup script

Most vendors provide a `setup.sh` or `env.sh` script:

```json
"env_source": "source /path/to/vendor/tool/version/setup.sh"
```

#### Pattern 2: Module system (`module load`)

HPC/server environments often use Environment Modules or Lmod:

```json
"env_source": "module load synopsys/vcs/2024.03"
```

#### Pattern 3: Direct PATH export

If you know exactly where the tool binary lives:

```json
"env_source": "export PATH=/path/to/tool/bin:$PATH"
```

Or simply set `path` directly and leave `env_source` empty:

```json
"vcs": {
  "detected": false,
  "path": "/opt/synopsys/vcs/U-2023.03/bin/vcs",
  "env_source": ""
}
```

### Configuration examples by vendor

Below are examples showing typical `env_source` values. Replace paths with
your actual installation locations.

#### Synopsys

```json
"tools": {
  "simulators": {
    "vcs": {
      "detected": false, "path": "",
      "env_source": "source /tools/synopsys/vcs/U-2023.03/setup.sh"
    }
  },
  "synthesis": {
    "dc_shell": {
      "detected": false, "path": "",
      "env_source": "source /tools/synopsys/dc/U-2023.03/setup.sh"
    }
  },
  "lint": {
    "sg_shell": {
      "detected": false, "path": "",
      "env_source": "source /tools/synopsys/spyglass/T-2023.06/setup.sh"
    }
  },
  "equivalence": {
    "fm_shell": {
      "detected": false, "path": "",
      "env_source": "source /tools/synopsys/formality/U-2023.03/setup.sh"
    }
  },
  "debug": {
    "verdi": {
      "detected": false, "path": "",
      "env_source": "source /tools/synopsys/verdi/U-2023.03/setup.sh"
    }
  },
  "coverage": {
    "urg": {
      "detected": false, "path": "",
      "env_source": "source /tools/synopsys/vcs/U-2023.03/setup.sh"
    }
  }
}
```

> **Note**: VCS and URG are typically bundled together, so they share the same `env_source`.

#### Cadence

```json
"tools": {
  "simulators": {
    "xrun": {
      "detected": false, "path": "",
      "env_source": "source /tools/cadence/xcelium/23.09/setup.sh"
    }
  },
  "synthesis": {
    "genus": {
      "detected": false, "path": "",
      "env_source": "source /tools/cadence/genus/23.1/setup.sh"
    }
  },
  "equivalence": {
    "lec": {
      "detected": false, "path": "",
      "env_source": "source /tools/cadence/conformal/23.1/setup.sh"
    }
  },
  "debug": {
    "simvision": {
      "detected": false, "path": "",
      "env_source": "source /tools/cadence/xcelium/23.09/setup.sh"
    }
  },
  "coverage": {
    "imc": {
      "detected": false, "path": "",
      "env_source": "source /tools/cadence/xcelium/23.09/setup.sh"
    }
  }
}
```

> **Note**: Xcelium, SimVision, and IMC are usually from the same package.

#### Siemens (Mentor)

```json
"tools": {
  "simulators": {
    "vsim": {
      "detected": false, "path": "",
      "env_source": "source /tools/siemens/questa/2024.1/setup.sh"
    }
  },
  "coverage": {
    "vcover": {
      "detected": false, "path": "",
      "env_source": "source /tools/siemens/questa/2024.1/setup.sh"
    }
  }
}
```

#### Module system example (all vendors)

```json
"vcs":      { "detected": false, "path": "", "env_source": "module load synopsys/vcs/2024.03" },
"dc_shell": { "detected": false, "path": "", "env_source": "module load synopsys/dc/2024.03" },
"xrun":     { "detected": false, "path": "", "env_source": "module load cadence/xcelium/23.09" },
"genus":    { "detected": false, "path": "", "env_source": "module load cadence/genus/23.1" },
"vsim":     { "detected": false, "path": "", "env_source": "module load siemens/questa/2024.1" }
```

### After editing `rat_config.json`

The generator script `generate_config.sh` lives **inside the plugin directory**
(it is not copied into the project workspace). To refresh detection status after
editing `rat_config.json`, use **either** of these two paths:

**Option A — Re-run `rat-init-project` (recommended, simplest)**:
```
/rtl-agent-team:rat-init-project
```
The skill is idempotent and will re-run the generator while preserving user-owned
fields. Usable explicit `path` overrides remain unchanged; stale or unusable paths
are refreshed when the tool is found in the current environment.

**Option B — Invoke the plugin's generator directly**:
```bash
bash "${CLAUDE_PLUGIN_ROOT}/skills/rat-init-project/scripts/generate_config.sh" . "$(basename "$(pwd)")"
```
Use this when you want to refresh `rat_config.json` without going through the
full `rat-init-project` flow. `CLAUDE_PLUGIN_ROOT` is set by the Claude Code
runtime when the plugin is active.

Both paths will:
1. Read and evaluate your trusted `env_source` values (preserved across re-runs)
2. Attempt detection by sourcing each environment
3. Update `detected` and `path` fields
4. Regenerate `config.mk` with preferred tool selections

---

## Technology Configuration

The `technology` section in `rat_config.json` configures synthesis target:

```json
"technology": {
  "target": "TSMC 28nm",
  "liberty": "path/to/standard_cell.lib",
  "sram_lib": "path/to/sram.lib",
  "nand2_cell_pattern": "NAND2X1",
  "nand2_area_um2": null
}
```

| Field | Purpose | Example |
|-------|---------|---------|
| `target` | Human-readable technology description | `"TSMC 28nm"`, `"Sky130"` |
| `liberty` | Path to Liberty timing library (`.lib`) | `"libs/sky130_fd_sc_hd__tt_025C_1v80.lib"` |
| `sram_lib` | Path to SRAM macro library (optional) | `"libs/sram_32x256.lib"` |
| `nand2_cell_pattern` | Cell name pattern for NAND2 area extraction | `"NAND2X1"` (default) |
| `nand2_area_um2` | NAND2 gate area in um2 (auto-extracted from liberty) | `1.26` |

### How it's used

- **`run_syn.sh`**: uses `liberty` as `target_library` for DC/Genus, or Liberty mapping for Yosys
- **`generate_config.sh`**: extracts NAND2 area from the Liberty file automatically
- **Synthesis agents**: report area in NAND2 gate equivalents using `nand2_area_um2`

### Open-source alternative (no commercial PDK)

If you don't have a commercial PDK, you can use the NanGate45 open-source library
for estimation purposes:

```json
"technology": {
  "target": "NanGate45 (academic proxy)",
  "liberty": "libs/NanGate_15nm_OCL.lib",
  "nand2_cell_pattern": "NAND2_X1",
  "nand2_area_um2": null
}
```

Yosys synthesis works without any Liberty file — it uses a built-in gate model.
The `liberty` field is only needed for gate-count estimation and commercial synthesis.

---

## `rat_config.json` Field Reference

Full field reference for the project configuration file.

### `project`

| Field | Type | Description |
|-------|------|-------------|
| `name` | string | Project name (auto-filled from directory name) |
| `top_module` | string | Top-level module name |
| `filelist` | string | Path to RTL filelist (default: `rtl/filelist_top.f`) |

### `tools`

Tool categories: `simulators`, `synthesis`, `lint`, `formal`, `cdc`, `equivalence`, `debug`, `coverage`.

Each tool entry has the same structure:

| Field | Type | Description |
|-------|------|-------------|
| `detected` | boolean | Auto-filled by `generate_config.sh` |
| `path` | string | Binary path (auto-filled, or user-provided) |
| `env_source` | string | Shell command to set up tool environment (**user-provided**) |

### `preferences`

Auto-determined preferred tool per category (commercial tools get priority).
Override by editing directly — this controls which tool `Makefile` targets invoke by default.

| Field | Priority order |
|-------|---------------|
| `simulator` | vcs → xrun → vsim → verilator → iverilog |
| `synthesis` | dc_shell → genus → yosys |
| `lint` | sg_shell → slang → verilator → verible |
| `formal` | jg → vcf → sby |
| `cdc` | sg_shell → svlens → structural |
| `equivalence` | fm_shell → lec |

### `technology`

See [Technology Configuration](#technology-configuration) above.

### `coverage`

| Field | Type | Description |
|-------|------|-------------|
| `targets.line` | number | Line coverage target % (default: 90) |
| `targets.toggle` | number | Toggle coverage target % (default: 80) |
| `targets.fsm` | number | FSM coverage target % (default: 70) |
| `targets.branch` | number | Branch coverage target % (default: 80) |
| `targets.functional` | number | Functional coverage target % (default: 95) |
| `seeds` | string | Space-separated regression seed list |
| `max_fail_rate` | number | Maximum allowed failure rate % |

### `waivers`

Paths to lint/CDC waiver files (tool-specific):

| Field | Tool |
|-------|------|
| `verilator` | Verilator lint waivers |
| `verible` | Verible lint waivers |
| `spyglass_lint` | SpyGlass lint waivers |
| `spyglass_cdc` | SpyGlass CDC waivers |
| `cdc` | General CDC waivers |

---

## Docker Fallback (Open-Source Only)

The Docker image bundles all open-source EDA tools. It does **not** include
commercial tools (those require your own licenses and installations).

```bash
# Build from a standalone rtl-agent-team clone root.
cd /path/to/rtl-agent-team

# Build once
docker build -t rtl-eda-tools docker/

# Run with an RTL project mounted
docker run -it --rm \
  --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --mount "type=bind,src=/absolute/path/to/rtl-project,dst=/workspace" \
  --workdir /workspace rtl-eda-tools
```

The `lib/tool-runner.sh` library provides transparent Docker fallback:
when a tool is not found locally, it automatically runs the command inside
a persistent Docker container. No configuration needed — just build the image.

---

## Troubleshooting

### Tool detected but wrong version

Override `path` to point to the desired version:

```json
"vcs": {
  "detected": true,
  "path": "/tools/synopsys/vcs/U-2023.03/bin/vcs",
  "env_source": "source /tools/synopsys/vcs/U-2023.03/setup.sh"
}
```

### `env_source` set but tool still not detected

1. Test your sourcing command manually:
   ```bash
   bash -c "source /your/setup.sh && which vcs"
   ```
2. If this works but the plugin's `generate_config.sh` still fails
   (see "After editing `rat_config.json`" above for invocation paths),
   check that the setup script doesn't require interactive input or TTY
   allocation.
3. Some `module load` systems need initialization first:
   ```json
   "env_source": "source /etc/profile.d/modules.sh && module load synopsys/vcs/2024.03"
   ```

### Multiple versions of the same tool

Only one version per tool key is supported. If you need to switch versions,
update `env_source` and re-run the generator (either `/rtl-agent-team:rat-init-project`
or the plugin path shown in "After editing `rat_config.json`" above).

### Preferences not matching expectations

`preferences` are auto-determined with commercial-first priority.
Override manually in `rat_config.json` or `config.mk`:

```json
"preferences": {
  "simulator": "verilator",
  "synthesis": "yosys"
}
```

### What regeneration updates

User-owned fields (`env_source`, `technology`, `waivers`, `coverage`, preferences,
and other project settings) are preserved. Tool `detected` and `path` fields are
refreshed: a usable explicit path override is retained, while a stale or unusable
path is replaced when detection finds the tool. Project `config.mk` is regenerated
from the refreshed configuration. These managed updates apply whether invoked via
`/rtl-agent-team:rat-init-project` or the plugin generator directly.

## v2 execution and updates

All wrappers consume tool paths, setup environments, preferences, and bounded
timeouts through the shared runner. See [the execution contract](specs/2026-11-17-eda-runner-contract.md)
for Docker/SSH/LSF, source-bound evidence and result precedence.

Install updates explicitly using install_project_templates.sh --update --dry-run
followed by --update when authorized. Existing managed files update only when
unchanged; user edits and unrecognized legacy copies receive staged proposals.
A bare rtl-verify-done or coverage-exclusion-approved marker is no evidence.
