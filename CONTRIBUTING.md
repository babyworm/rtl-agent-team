> **한국어 문서**: [CONTRIBUTING_kr.md](./CONTRIBUTING_kr.md)

# Contributing

How to contribute to the RTL Agent Marketplace.
This project follows the [Contributor Covenant Code of Conduct](CODE_OF_CONDUCT.md).

---

## Getting started

### Development environment setup

```bash
# 1. Clone the repository
git clone https://github.com/babyworm/rtl-agent-team.git
cd rtl-agent-team

# 2. Install test dependencies
python3 -m venv .venv
".venv/bin/python" -m pip install -r tests/requirements-test.txt

# 3. Run the tests
".venv/bin/python" -m pytest tests/unit/ -x -q

# 4. Run Claude Code against the local plugin
claude --plugin-dir "$(pwd)"
```

### Filing an issue

- **Bug reports**: use the [Bug Report template](.github/ISSUE_TEMPLATE/bug_report.md)
- **Feature proposals**: use the [Feature Request template](.github/ISSUE_TEMPLATE/feature_request.md)

### Opening a pull request

1. Fork and work on a feature branch
2. Confirm the tests pass: `".venv/bin/python" -m pytest tests/unit/ -x -q`
3. If you touched a hook, confirm shellcheck passes: `shellcheck -s sh hooks/*.sh hooks/lib/*.sh`
4. Work through the checklist in the [PR template](.github/PULL_REQUEST_TEMPLATE.md)
5. Open the PR

---

## Kinds of contribution

There are three broad kinds:
1. **Improving the existing plugin** — add or change agents, skills, references
2. **Adding a domain agent** — integrate a new domain-expert agent
3. **Adding a new plugin** — register an independent plugin in the marketplace

---

## 1. Improving the existing plugin (rtl-agent-team)

### Adding an agent

Create a Markdown file under `agents/`.

**File**: `agents/{agent-name}.md`

```markdown
---
name: {agent-name}
description: One sentence on what the agent does. Include when to use it and what expertise it carries.
model: opus
color: blue
---

<Agent_Prompt>
  <Role>
    Define the agent's role and area of expertise.
  </Role>

  <Why_This_Matters>
    Why this agent is needed, and what goes wrong without it.
  </Why_This_Matters>

  <Constraints>
    - What to do and what not to do
  </Constraints>

  <Tool_Usage>
    Tools to use, with examples
  </Tool_Usage>

  <Output_Format>
    Output format definition
  </Output_Format>

  <Examples>
    <Good>Example of good output</Good>
    <Bad>Example of bad output</Bad>
  </Examples>
</Agent_Prompt>
```

**Frontmatter fields**:

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Required | Same as the filename (without `.md`), kebab-case |
| `description` | Required | One sentence. Claude reads this text when selecting an agent |
| `model` | Required | `opus` (complex analysis), `sonnet` (standard work), `haiku` (simple lookups) |
| `color` | Optional | Display colour in the UI |
| `disallowedTools` | Optional | Tools to forbid (e.g. `Write, Edit` for a read-only agent) |

**Checklist**:
- [ ] Does the `name:` field match the filename?
- [ ] Does `description:` convey the agent's expertise and when to reach for it?
- [ ] Added the agent to the CLAUDE.md delegation table?
- [ ] Updated the agent counts in README.md, README_kr.md and CLAUDE.md?
- [ ] Updated the agent count in the `.claude-plugin/marketplace.json` description?
- [ ] Ran `sh scripts/add-rat-protocol.sh` to insert the audit-output-protocol
      reference directly after the frontmatter (idempotent — files that already
      carry it are skipped). Orchestrator-class agents also need the Step 0
      Context Bootstrap, so preview with `bash scripts/sync_step0.sh --dry-run`
      before syncing.

> `agents/` is scanned **recursively**, and every `.md` file found becomes a
> spawnable agent. Keep the directory flat: shared prompt fragments and sync
> templates belong in `plugin_docs/agent-lib/`. `test_agents_dir_has_no_nested_markdown`
> enforces this.

### Adding a skill

Create `skills/{skill-name}/SKILL.md`.

```markdown
---
name: {skill-name}
description: "Describes the situation in which this skill should be used."
---

<Purpose>
The skill's purpose
</Purpose>

<Use_When>
- Situation 1
- Situation 2
</Use_When>

<Do_Not_Use_When>
- Situations to avoid
</Do_Not_Use_When>

<Steps>
1. Execution step
2. ...
</Steps>

<Tool_Usage>
Agent delegation examples (Task calls)
</Tool_Usage>

<Examples>
<Good>Example of a good result</Good>
<Bad>Example of a bad result</Bad>
</Examples>

<Final_Checklist>
- [ ] Completion criteria
</Final_Checklist>
```

**Skill subdirectories** (optional):

```
skills/{skill-name}/
├── SKILL.md              # Skill definition (required)
├── templates/            # Output templates, JSON schemas, …
└── examples/             # Example inputs and outputs
```

Address a skill's own bundled assets **skill-relative** (`references/x.md`), which
resolves against the skill directory. An asset owned by a *different* skill must be
addressed `{plugin_root}`-absolute
(`{plugin_root}/skills/<owner>/references/x.md`) — `test_skill_relative_assets_resolve`
checks that every skill-relative path names a file the skill actually bundles.

**Checklist**:
- [ ] Does `description:` give Claude enough to route automatically? Keep it within
      160 characters — the harness silently truncates skill descriptions once the
      global budget is exceeded, and a description-less skill stops being routable
- [ ] Added the pattern to the skill routing table in CLAUDE.md?
- [ ] Updated the skill counts in README.md, README_kr.md and CLAUDE.md?
- [ ] If the skill produces a review artifact, added it to `review-checklist.md`?
- [ ] If the skill changes phase inputs or outputs, updated the Context Preload
      section of the corresponding orchestrator?

### Adding a reference document

Add detailed references under `references/{topic}.md`. References are the bottom
layer of the three-tier documentation model — agents read them only when needed.

### Files that must be updated after a change

Adding or removing an agent or skill requires updating the counts and lists in:

| File | What to update |
|------|----------------|
| `skills/rtl-orchestrate/SKILL.md` | Skill routing table + Action Skill→Orchestrator→Policy mapping + SessionStart export block (single source of truth) |
| `scripts/sync_orchestrator_inject.sh` | Syncs the `rtl-orchestrate` export block into the `hooks/rtl-orchestrator-inject.sh` generated block |
| `hooks/rtl-orchestrator-inject.sh` | Condensed SessionStart routing (never hand-edit the generated block) |
| `README.md`, `README_kr.md`, `CLAUDE.md` | Agent/skill counts, structure description, agent team table |
| `.claude-plugin/marketplace.json` | Counts in the plugin description |
| `skills/rat-auto-design/references/review-checklist.md` | Update when a review artifact is added or removed |
| `agents/*-orchestrator.md` (Context Preload section) | Update the inline preload list when per-phase input/output artifacts change |

Nothing in the `rtl-orchestrate` body reaches the runtime on its own — the skill
carries both `user-invocable: false` and `disable-model-invocation: true`. Anything
the runtime must know has to travel through the `SESSIONSTART_HOOK_EXPORT` block.

Always run the following after a routing or delegation change:

```bash
sh scripts/sync_orchestrator_inject.sh
".venv/bin/python" -m pytest -q tests/unit/test_agent_skill_structure.py tests/unit/test_hooks.py tests/unit/test_plugin_runtime_contract.py
```

### Local testing vs. marketplace deployment

`claude --plugin-dir "$(pwd)"` reads the working tree directly. Local testing needs
no commit, no push, no marketplace refresh and no plugin cache reinstall.

Only deployment to the marketplace requires explicitly staging the files you
reviewed and refreshing the cache. Replace `agents/{agent-name}.md`,
`skills/{skill-name}/SKILL.md` and `tests/unit/{test-name}.py` below with the paths
you actually reviewed.

**Background**: a Claude Code session running a marketplace-installed plugin loads
skills from the copy under `~/.claude/plugins/cache/`. Only a session started with
`--plugin-dir` reads the working directory directly.

```
Working directory (~/works/rtl-agent-team/)
  ↓  git push
GitHub (babyworm/rtl-agent-team)
  ↓  claude plugin marketplace update rtl-agent-marketplace
Marketplace (~/.claude/plugins/marketplaces/rtl-agent-marketplace/)
  ↓  claude plugin update rtl-agent-team
Cache (~/.claude/plugins/cache/.../0.1.0/)
  ↓  session restart
System skill list (loaded at runtime)
```

**Commands to run when deploying**:

```bash
# 1. Stage only the reviewed paths and re-read the staged diff
git status --short
git add -- agents/{agent-name}.md skills/{skill-name}/SKILL.md tests/unit/{test-name}.py
git diff --cached --check
git diff --cached
git commit -m "Add or rename reviewed skills"
git push

# 2. Refresh the marketplace (git pull from GitHub)
claude plugin marketplace update rtl-agent-marketplace

# 3. Reinstall the plugin (forces a cache refresh)
claude plugin uninstall --keep-data rtl-agent-team@rtl-agent-marketplace
claude plugin install rtl-agent-team@rtl-agent-marketplace

# 4. Restart the Claude Code session (changes apply in a new session)
```

> **Caution**: `claude plugin update` is a no-op when the version is unchanged.
> Use `uninstall` → `install` when verifying a marketplace build.
> Skipping step 3 leaves the marketplace current while the cache stays stale, so
> the skill references in CLAUDE.md no longer match the registered system names.

---

## 2. Adding a domain agent

How to add an expert agent for a new hardware design domain (DDR controllers, PCIe,
audio codecs, and so on).

### Naming rules

Domain agents use a `{domain}-` prefix:

| Domain | Prefix | Example |
|--------|--------|---------|
| Video codec | `vcodec-` | `vcodec-syntax-entropy-expert` |
| Video processing | `vproc-` | `vproc-color-format-expert` |
| DDR / memory | `ddr-` | `ddr-timing-expert` |
| PCIe | `pcie-` | `pcie-ltssm-expert` |
| Audio | `audio-` | `audio-dsp-expert` |

### Domain packages (optional)

With three or more expert agents, grouping them into a **domain package** is
recommended.

**Directory structure**:

```
domain-packages/{domain}/
├── manifest.json          # Agent list, standards, coordination workflow
├── knowledge/             # Domain knowledge (standard summaries, algorithms, …)
├── conformance/           # Conformance test data
└── templates/             # Domain-specific code templates
```

**manifest.json structure**:

```json
{
  "domain": "{domain}",
  "version": "1.0.0",
  "description": "Domain description",

  "standards": [
    {
      "id": "Standard ID",
      "full_name": "Full standard name",
      "url": "Standard document URL"
    }
  ],

  "agents": [
    {
      "id": "{domain}-{role}-expert",
      "file": "agents/{domain}-{role}-expert.md",
      "role": "Role description",
      "expertise": ["Area 1", "Area 2"]
    }
  ],

  "agent_coordination": {
    "phase_1_research": {
      "primary_domain_agents": ["Agent list"],
      "workflow": "Workflow description"
    }
  }
}
```

### The Chief agent pattern

With four or more domain experts, adding a **Chief agent** is recommended.

A Chief agent's job:
- Cross-review the sub-domain experts' output
- Identify inter-block dependencies
- Converge on quality through iterated review (3 rounds enforced by default)

Reference: `agents/vcodec-chief-standard-expert.md`

### Checklist

- [ ] Agent file created (`agents/{domain}-{role}-expert.md`)
- [ ] Agent frontmatter `name:` matches the filename
- [ ] Added to the CLAUDE.md delegation table
- [ ] Domain category added to the README.md agent team table
- [ ] (3+ agents) Domain package `domain-packages/{domain}/manifest.json` created
- [ ] (4+ agents) Chief agent recommended
- [ ] New domain added to the routing tables of existing skills (p1-spec-research, domain-consult, …)
- [ ] Agent/skill counts updated (README.md, `.claude-plugin/marketplace.json`)

---

## 2.5 Video codec standard onboarding (H.264 / H.265 / AV1 / VVC …)

A guide to adding a new video codec standard to the domain package. Unlike adding a
plain domain agent (§2), a codec standard needs a set of knowledge files, expert
prompt synchronization, routing updates and test gates together.

### Support tiers

| Tier | Scope | Example |
|------|-------|---------|
| **full** | Analysis + RD eval + conformance + expert prompts | H.264, H.265 |
| **analysis_only** | Analysis only (knowledge + expert `<Domain_Knowledge>` updates) | AV1 (initial) |
| **roadmap** | Planning stage (manifest entry only, no knowledge files) | VVC |

### Standard support matrix (manifest.json)

Maintain the `standard_support_matrix` field in
`domain-packages/video-codec/manifest.json`:

```json
"standard_support_matrix": {
  "H.264": {
    "tier": "full",
    "agent_coverage": ["syntax", "prediction", "tq", "filter", "chief", "arch", "perf"],
    "conformance_available": true,
    "rd_eval_available": true,
    "owner": "rtl-agent-team",
    "maturity": "stable"
  }
}
```

### Minimum knowledge file set

Create the following per standard under `domain-packages/video-codec/knowledge/`:

| File | Required (full) | Required (analysis_only) | Contents |
|------|:---------------:|:------------------------:|----------|
| `{std}-spec-summary.md` | O | O | Standard algorithm block summary + clause references |
| `{std}-function-map.md` | O | - | Reference SW function → spec clause mapping |
| `{std}-fixed-point.md` | O | - | Fixed-point arithmetic rules (bit widths, rounding) |
| `{std}-throughput.md` | O | - | Throughput tables per resolution/frame rate |
| `{std}-conformance-notes.md` | O | - | Conformance test vectors and verification caveats |

> `{std}` is lowercase hyphenated: `h264`, `h265`, `av1`, `vvc`
>
> **Shared files are allowed**: knowledge common to several standards (for example
> `fixed-point-conventions.md`, `throughput-tables.md`) may stay in one shared file
> rather than being split per standard. In that case give the manifest's
> `standard_id` an array value (e.g. `"standard_id": ["H.264", "H.265"]`).

### Synchronizing expert prompt scope

Adding a standard means updating the `<Domain_Knowledge>` section of these eight
experts:

1. `vcodec-syntax-entropy-expert` — entropy coding algorithms of the new standard
2. `vcodec-intra-pred-expert` — intra prediction algorithms
3. `vcodec-me-expert` — motion estimation / MV prediction algorithms
4. `vcodec-mc-expert` — motion compensation algorithms
5. `vcodec-transform-quant-expert` — transform / quantization algorithms
6. `vcodec-filter-recon-expert` — in-loop filter algorithms
7. `vcodec-chief-standard-expert` — add the new standard to cross-block dependencies
8. `vcodec-architecture-expert` — add the new standard to HW architecture patterns

### Routing synchronization

Three places must be updated together:

1. `skills/domain-consult/SKILL.md` — add the new standard's keywords to the routing table
2. `skills/rtl-orchestrate/SKILL.md` — SSOT routing block (the hook export source)
3. `hooks/rtl-orchestrator-inject.sh` — run `sh scripts/sync_orchestrator_inject.sh`

### Separating non-codec video processing

Codec performance analysis (`video-processing-expert`) and general image processing
(color space, HDR, ISP) are managed as separate domains:

- **`domain-packages/video-codec/`** — `video-processing-expert` stays here (codec throughput expert)
- **`domain-packages/video-processing/`** — non-codec image processing experts (active, 3 agents: color-format, denoise, image-processing)

Routing is already separated (see `domain-consult/SKILL.md`).

### Skill compatibility matrix

| Skill | H.264 | H.265 | AV1 | VVC |
|-------|:-----:|:-----:|:---:|:---:|
| `codec-rd-eval` (encoder RD) | O | O | - | - |
| `codec-conformance-eval` (decoder) | O | O | - | - |
| `rtl-conformance-test` (RTL) | O | O | - | - |

Update this table when a standard is added.

### Test gates

Five test suites must pass as a merge condition:

1. **manifest schema pass** — `test_json_schemas.py::TestDomainManifest`
2. **routing keyword coverage pass** — `test_expert_quality.py::TestRoutingKeywordCoverage` (vcodec + vproc routing)
3. **expert contract pass** — `test_expert_quality.py::TestExpertQualityContract` + `TestVprocExpertQuality`
4. **knowledge version consistency pass** — `test_expert_quality.py::TestKnowledgeVersionConsistency`
5. **vproc manifest consistency pass** — `test_expert_quality.py::TestVprocManifestConsistency`

### Definition of done

An "add a new standard" PR must contain at least these five changes:

- [ ] `manifest.json` — standards array + standard_support_matrix + knowledge_base entries
- [ ] `knowledge/` — minimum knowledge file set (per tier)
- [ ] Routing — domain-consult + rtl-orchestrate + hook inject synchronized
- [ ] Tests — all five test gates pass
- [ ] README.md — supported standards list updated

---

## 3. Adding a new plugin

How to add an independent plugin to this marketplace.

### A plugin inside this repo

Add the plugin under `plugins/`.

```
plugins/{plugin-name}/
├── .claude-plugin/
│   └── plugin.json        # Plugin manifest (when strict: true)
├── agents/                # (optional) agents
├── skills/                # (optional) skills
└── hooks/                 # (optional) hooks
```

**Register it in `.claude-plugin/marketplace.json`**:

```json
{
  "name": "{plugin-name}",
  "source": "./plugins/{plugin-name}",
  "description": "Plugin description",
  "version": "1.0.0",
  "category": "development",
  "tags": ["tag1", "tag2"]
}
```

### Lightweight plugins (without plugin.json)

Simple plugins such as LSP or MCP servers can be defined directly in
`.claude-plugin/marketplace.json` with `strict: false`.

```json
{
  "name": "{plugin-name}",
  "source": "./plugins/{plugin-name}",
  "description": "Plugin description",
  "version": "1.0.0",
  "strict": false,
  "lspServers": { ... },
  "mcpServers": { ... }
}
```

### A plugin in an external repo

Register a plugin that lives in another repository.

```json
{
  "name": "{plugin-name}",
  "source": {
    "source": "github",
    "repo": "owner/repo"
  },
  "description": "Plugin description",
  "version": "1.0.0"
}
```

Reference: the `systemverilog-lsp` entry in `.claude-plugin/marketplace.json`.

When pinning a github-source sub-plugin, use the **commit sha**, not the annotated
tag-object sha: `git rev-parse <tag>` returns the tag object for annotated tags,
while `git rev-parse <tag>^{commit}` always returns the commit. Verify with
`git cat-file -t <sha>` — it must print `commit`.

### Checklist

- [ ] Plugin source prepared (same repo: `plugins/`; external: separate repo)
- [ ] Entry added to the `plugins` array in `.claude-plugin/marketplace.json`
- [ ] JSON validated (`python3 -c "import json; json.load(open('.claude-plugin/marketplace.json'))"`)
- [ ] New plugin added to the README.md Marketplace table
- [ ] Install tested: `/plugin install {plugin-name}`

---

## Coding conventions

### Language standards

| Language | Standard | Used for |
|----------|----------|----------|
| **SystemVerilog (RTL)** | IEEE 1800-2009 | Synthesizable RTL. 2012+ features are forbidden in RTL |
| **SystemVerilog (verification)** | IEEE 1800-2012 | SVA, UVM TB. checker, interface class and similar are allowed |
| **C** | C11 (`-std=c11`) | Reference model (DPI-C compatible). `gcc -Wall -Wextra -Werror` |
| **C++** | C++17 (`-std=c++17`) | BFM (SystemC/TLM), DPI. C++20 is forbidden |

- iverilog flag: `-g2012` (parses with 2009 backward compatibility)
- Nothing synthesis-relevant was added after 2012 (2017 is errata only; 2023 tool support is early)

### iverilog compatibility

iverilog supports base SystemVerilog syntax with `-g2012`, but some features are missing:

| Construct | iverilog support | Alternative |
|-----------|------------------|-------------|
| `logic`, `always_ff`, `always_comb` | supported | — |
| `typedef enum` | supported | — |
| `typedef struct packed` | supported | — |
| `typedef union packed` | supported | — |
| `interface` / `modport` | unsupported | port list |
| unpacked `struct` / `union` | unsupported | individual signals or a packed version |

Coding agents must not generate unsupported constructs.
They must not rewrite such constructs when a user added them or when they already
exist in the codebase.

### RTL naming rules

| Item | Rule |
|------|------|
| Port prefix | `i_`, `o_`, `io_` (NOT the suffixes `_i`, `_o`) |
| Clock | `clk` (single) or `{domain}_clk` (multiple) — NOT `clk_i` |
| Reset | `rst_n` (single) or `{domain}_rst_n` (multiple) — active-low asynchronous |
| Naming | `snake_case` or `ALL_CAPS` only (no CamelCase) |
| Parameter | `ALL_CAPS` (`DATA_WIDTH`) |
| Instance | `u_` prefix (`u_fifo`) |
| FSM state | `typedef enum logic` + `UPPER_SNAKE_CASE` (`ST_IDLE`) |
| UVM member handle | `m_` prefix allowed (industry practice). `u_` is reserved for RTL instances |

Details: `skills/systemverilog/references/coding-style-guide.md`, `skills/systemverilog/SKILL.md`
