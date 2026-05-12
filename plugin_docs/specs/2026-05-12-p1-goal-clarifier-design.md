---
title: P1 Goal-Clarifier Integration
date: 2026-05-12
status: draft
owners: babyworm
relates_to:
  - skills/p1-spec-research/SKILL.md
  - agents/spec-analyst.md
  - agents/p1-research-orchestrator.md
inspiration:
  - .claude/plugins/cache/omc/oh-my-claudecode/4.13.7/skills/self-improve/si-goal-clarifier.md
---

# P1 Goal-Clarifier Integration — Design Spec

## 1. Context & Motivation

The `p1-spec-research` skill currently dispatches `p1-research-orchestrator`,
which in turn invokes `spec-analyst`. `spec-analyst` is a *read-only document
analyser*: it transforms an existing spec into `iron-requirements.json` and
`open-requirements.json`. It already understands ambiguity (`"Ambiguity
score > 0.5 → CANNOT become iron"`), but it cannot *interview* the user when
the input is missing or vague.

The OMC `self-improve` skill exposes a complementary pattern via
`si-goal-clarifier.md`: a structured **interview loop** that scores user
intent across 4 dimensions and asks the lowest-scoring one until ambiguity
drops below 20%. The pattern's strengths are:

- **Scored dimensions** make the next question deterministic (not vibe-driven).
- **Pre-scan** (silent codebase read) before any question → evidence-based prompts.
- **Fast-path** skips interview when input is already complete.
- **One-question-per-round** keeps cognitive load low for the user.
- **Hard cap (12 rounds)** prevents runaway interviews.

Goal: bring that pattern to RTL design as a **Phase 0** stage inside
`p1-spec-research`, producing a structured `goal.md` that becomes the input
to `spec-analyst`. The two agents become **complementary**:

- `goal-clarifier` (NEW): interactive, ambiguity-driven interview from a vague seed.
- `spec-analyst` (EXISTING): deterministic structuring of the resulting `goal.md`
  into iron/open requirements + IO + timing schemas.

## 2. Goals & Non-goals

| Goals | Non-goals |
|-------|-----------|
| Add a Phase 0 goal-clarifier stage to `p1-spec-research`. | Replacing `spec-analyst` — it remains the iron/open structurer. |
| Auto-detect when to invoke the clarifier (no extra flag for the common case). | Modifying P2/P3 or downstream phases. |
| Establish 4 RTL-domain dimensions (Functionality / PPA Target / Scope / Verification) with measurable 0-100 scoring. | Building a graphical UI — clarifier uses AskUserQuestion only. |
| Reuse the asset-bundle pattern from `rtl-document` for `goal-clarifier`'s assets. | Replacing the existing `superpowers:brainstorming` skill. |
| Produce `docs/phase-1-research/goal.md` and feed it to `spec-analyst`. | Auto-chaining beyond Phase 1 (orchestrator handles that). |
| Cap at 12 rounds, exit on ambiguity ≤ 20%, fast-path on rich input. | Persisting interview state across sessions (single-session loop). |

## 3. Architecture

### 3.1 New agent + skill change overview

```
skills/p1-spec-research/SKILL.md          # MODIFIED: Phase 0 step added
agents/goal-clarifier.md                  # NEW: interview agent
agents/p1-research-orchestrator.md        # MODIFIED: clarifier→spec-analyst chain
skills/p1-spec-research/
├── references/goal-dimensions.md         # NEW: 4 RTL dimensions definition + examples
├── templates/goal.md                     # NEW: structured output template
└── scripts/score_ambiguity.py            # NEW: pure helper for scoring + ambiguity calc
```

### 3.2 Phase 0 placement and trigger

```
/rtl-agent-team:p1-spec-research "ARGUMENTS"
    ↓
[trigger check]
    │
    ├─ heuristic: ARGUMENTS is a path to an existing markdown spec
    │             OR docs/phase-1-research/iron-requirements.json already complete
    │             → skip Phase 0
    │
    ├─ heuristic: ARGUMENTS is a short natural-language idea (≤ 500 chars
    │             AND not a file path AND no obvious REQ-* IDs)
    │             → run Phase 0 (goal-clarifier interview)
    │
    └─ heuristic: ARGUMENTS is empty
                  → run Phase 0 (interview starts from a blank slate
                                 with pre-scan of the cwd)
    ↓
Phase 0: goal-clarifier interview (→ docs/phase-1-research/goal.md)
    ↓
Phase 1+: spec-analyst (consumes goal.md as input alongside any raw spec)
    ↓ ...
```

`p1-research-orchestrator` becomes responsible for invoking the trigger
heuristic and conditionally spawning `goal-clarifier` before `spec-analyst`.

### 3.3 Asset-bundle layout (reuse rtl-document pattern)

| Path | Role |
|------|------|
| `agents/goal-clarifier.md` | Interactive interview agent prompt. |
| `skills/p1-spec-research/references/goal-dimensions.md` | 4 RTL dimensions definition, scoring rubric, anti-patterns (~150 lines). |
| `skills/p1-spec-research/templates/goal.md` | Output skeleton with the 4-section structure. |
| `skills/p1-spec-research/scripts/score_ambiguity.py` | Pure helper: input dimension scores → ambiguity %, formatted scoreboard text. |

The `examples/` directory is intentionally **omitted for v1** — the clarifier's
real "examples" are filled `goal.md` files in user projects, not in-plugin
artifacts. (Future enhancement: ship a `goal.md` example alongside the
existing `rtl-document/examples/`.)

## 4. Component Design

### 4.1 `agents/goal-clarifier.md` (NEW)

Adapted from `si-goal-clarifier.md` with RTL-domain customisations.

**Role**: Interview the user, one question per round, until ambiguity ≤ 20%
across 4 RTL dimensions. Write `docs/phase-1-research/goal.md` and hand off
to `spec-analyst`.

**Inputs**:
- `seed` (string): the user's initial idea or "" if empty.
- `cwd` (path): for pre-scan.
- `existing_goal_path` (path | null): if `docs/phase-1-research/goal.md`
  already exists, offer "refine or restart?" at the top.

**Workflow**:

1. **Phase 1 — Pre-scan (silent)**. Walk the cwd, read `README*`, top-level
   `docs/`, any obvious `rtl/` or `tests/` markers, and `package.json` /
   `pyproject.toml` if present. Build a 1-page mental model of what the project
   currently is. No user-facing output yet.

2. **Phase 2 — Fast-path check**. If the seed already encodes all 4
   dimensions clearly (heuristic: ≥ 200 chars, contains a clock frequency
   spec, contains an area or bitexact or coverage clue), score immediately
   and skip to Phase 4.

3. **Phase 3 — Interview rounds**. Each round:
   1. Score all 4 dimensions (LLM judgment, 0-100 with a rubric from
      `references/goal-dimensions.md`).
   2. Compute ambiguity = 100 - mean(dimensions).
   3. Display scoreboard:
      ```
      === Round {n} ===
      Functionality:  {score}/100
      PPA Target:     {score}/100
      Scope:          {score}/100
      Verification:   {score}/100
      Ambiguity:      {score}%
      ```
   4. Ask ONE question targeting the lowest-scoring dimension. The question
      MUST cite an artefact from the pre-scan when possible (e.g., "Your
      README mentions a 200 MHz target — does this IP need to meet that
      same clock?").
   5. Update scores from the user's answer.
   6. Exit when ambiguity ≤ 20% (i.e., all four dimensions ≥ 80).

4. **Phase 4 — Write goal**. Render `docs/phase-1-research/goal.md` from
   `templates/goal.md` with the elicited values. Each section is a fill-in,
   not a marker — the clarifier already has the answers.

5. **Phase 5 — Handoff**. Print a one-paragraph summary and return control
   to `p1-research-orchestrator`. The orchestrator then dispatches
   `spec-analyst` with the goal file as input alongside any user-supplied
   spec document.

**Caps**:
- Soft cap: 8 rounds. Re-evaluate whether to escalate to the user with
  "ambiguity is N% after 8 rounds — want to lock and proceed?".
- Hard cap: 12 rounds. Forcibly write `goal.md` with whatever ambiguity
  remains and add a header `STATUS: ambiguity=N%` for downstream agents
  to see.

### 4.2 `skills/p1-spec-research/references/goal-dimensions.md` (NEW)

≤200 lines. Sections:

1. **The 4 dimensions and their scoring rubrics** — for each dimension, a
   table of what 0 / 25 / 50 / 75 / 100 looks like with RTL-specific
   examples (e.g., "PPA Target = 100: clock target stated in MHz + area
   budget in mm² or gate count + power class").
2. **Mapping to downstream phases** — Functionality→P1 spec, PPA→P2 arch,
   Scope→P3 block boundaries, Verification→P5 test plan.
3. **Question templates per dimension** — 3-5 RTL-domain question seeds for
   each dimension that the clarifier can adapt with pre-scan evidence.
4. **Anti-patterns** — when the clarifier should refuse to invent context
   (matches the spec-analyst constraint: "Never invent requirements").

### 4.3 `skills/p1-spec-research/templates/goal.md` (NEW)

```markdown
# Project Goal

> Produced by goal-clarifier on YYYY-MM-DD. Feeds into spec-analyst.

## Functionality
- **What this IP does**: <one paragraph>
- **IO contract** (informal): <ports / interfaces summary>
- **Algorithm or standard**: <name + version if applicable>

## PPA Target
- **Clock target**: <X MHz on Y process>
- **Area budget**: <gates / mm² / SRAM bits>
- **Power class**: <e.g., < 50 mW @ Y MHz>
- **Latency / throughput**: <cycles per token, tokens/s>

## Scope
- **In scope**: <module list / boundary>
- **Out of scope**: <explicit exclusions>
- **Dependencies**: <upstream / downstream IP>

## Verification
- **Coverage target**: <%line / %toggle / %FSM>
- **Reference oracle**: <C model / JM / vendor / none>
- **Bitexact requirement**: <yes / no / per-block>
- **Performance verification**: <cycle-accurate vs functional>

## Open Questions
<!-- The clarifier may leave 0-2 unresolved items here.
     Each becomes an OPEN-1-NNN candidate for spec-analyst. -->

---
STATUS: ambiguity=N%
ROUNDS: M
```

### 4.4 `skills/p1-spec-research/scripts/score_ambiguity.py` (NEW)

Pure helper. CLI:

```bash
python3 scripts/score_ambiguity.py \
  --functionality 85 --ppa 70 --scope 90 --verification 60
# stdout:
# === Scoreboard ===
# Functionality:  85/100
# PPA Target:     70/100
# Scope:          90/100
# Verification:   60/100
# Ambiguity:      24%
# Lowest:         Verification (60)
# Exit decision:  CONTINUE  (target ≤ 20%)
```

JSON mode (for the agent to consume):

```bash
python3 scripts/score_ambiguity.py --json \
  --functionality 85 --ppa 70 --scope 90 --verification 60
# {"ambiguity": 24, "lowest": "verification", "lowest_score": 60, "exit": false}
```

Pure stdlib. The agent uses this both for display formatting and for the
exit decision so the scoring logic is testable in isolation.

### 4.5 Modifications to existing files

**`skills/p1-spec-research/SKILL.md`** — add a `<Phase_Workflow>` block (or
extend existing prose) declaring Phase 0 before Phase 1. Update `<Assets>`
to list the new references/templates/scripts. Keep the body lean (no
duplication with the agent prompts).

**`agents/p1-research-orchestrator.md`** — add a Step 0a:

> If the seed is sparse (auto-detect heuristic), spawn `goal-clarifier`
> with the seed and cwd. After it writes `docs/phase-1-research/goal.md`,
> proceed to spec-analyst with that file as the structured input.

The trigger heuristic itself is short enough to embed inline; no extra
script needed.

## 5. Trigger heuristic — Auto-detect logic

Implemented inside `p1-research-orchestrator`:

```python
# Pseudocode for clarity; the orchestrator carries this as prose.
def needs_clarifier(arguments: str, cwd: Path) -> bool:
    a = arguments.strip()
    # 1. Empty input → always clarify.
    if not a:
        return True
    # 2. Path to an existing readable text file → skip (let spec-analyst read it).
    if (cwd / a).is_file() and (cwd / a).suffix in {".md", ".txt", ".rst"}:
        return False
    # 3. Already-rich seed (≥ 500 chars, contains MHz/MB/Coverage signals) → skip.
    if len(a) >= 500 and any(s in a.lower() for s in
                              ["mhz", "ns ", "coverage", "bitexact", "um^2", "mm^2"]):
        return False
    # 4. Otherwise: short natural-language idea → clarify.
    return True
```

The orchestrator records the trigger decision and rationale in its
audit-output protocol entry so downstream debugging is straightforward.

## 6. Output schema (`docs/phase-1-research/goal.md`)

Already shown in §4.3. The trailing `STATUS:` and `ROUNDS:` lines are
parseable by `score_ambiguity.py` for downstream consumption (e.g.,
spec-analyst can warn "input goal has ambiguity=35%, expect more
OPEN-1-NNN items").

## 7. Integration with `spec-analyst`

The orchestrator passes the goal file's path to `spec-analyst` as
additional context. `spec-analyst`'s existing prompt does not need a
contract change — it already accepts free-form spec input. The clarifier's
output becomes one of its source documents alongside any raw user-supplied
spec.

The ambiguity headline `STATUS: ambiguity=N%` is *informational* for
spec-analyst. If N is high (e.g., > 30%), spec-analyst is expected to
produce more OPEN-1-NNN items than usual; this is acceptable because the
P1 review loop will then convert them to iron through follow-up rounds.

## 8. Testing strategy

Interactive interview agents are not directly testable in unit form. We
test what we *can*:

1. **`score_ambiguity.py` unit tests** — input dimensions, expected
   ambiguity %, expected lowest dimension, JSON output schema.
2. **`templates/goal.md` schema** — a test loads the template, fills it
   with sample dimensions, and asserts the rendered file parses cleanly
   (sections present, STATUS line present).
3. **Trigger heuristic** — extracted into a small `_needs_clarifier()`
   helper inside an orchestrator-adjacent script (or inline test fixture)
   and asserted against 6 cases (empty, path-to-md, path-to-nonexistent,
   short idea, long-rich seed, long-vague seed).
4. **Reference doc lint** — `references/goal-dimensions.md` must stay ≤
   200 lines, must contain a section for each of the 4 dimensions, and
   must contain at least one "anti-pattern" entry. Single test asserts
   these structural properties.

No test attempts to drive the interview agent itself.

## 9. Migration & rollout

- One PR with: agent + skill changes + references + templates + script +
  4 test groups. Single feature branch `feat/p1-goal-clarifier`.
- No behaviour change for existing P1 runs that provide a full spec
  document (fast-path skip).
- New behaviour only fires when the seed is sparse, so existing pipelines
  remain unaffected.

## 10. Open questions

- **Q1: Should `goal.md` be checked into git or kept as a working
  artefact?** Default proposal: checked in under `docs/phase-1-research/`
  alongside `iron-requirements.json`, matching the rest of the phase's
  artefacts.
- **Q2: Should the clarifier be re-runnable after spec-analyst has
  finished?** Default proposal: yes — if iron-requirements is regenerated
  later, the clarifier can re-interview to update `goal.md` first.
- **Q3: Should the 4-dimension scoring be exposed to other phases (e.g.,
  P2 arch can re-score "PPA" after architecture decisions)?** Default
  proposal: not for v1. Re-score is a v2 feature.

## 11. Success criteria

1. New agent + skill assets pass the test groups in §8.
2. `p1-spec-research` triggered with a vague seed (`"do something with
   AXI"`) produces `docs/phase-1-research/goal.md` with non-empty content
   in all four dimensions.
3. `p1-spec-research` triggered with a complete `spec.md` path skips the
   interview (fast-path).
4. SKILL.md body stays ≤ 1500 words (well under the 1500-2000 plugin-dev
   guideline).
5. No regression in the existing P1 test suite or downstream phase entry
   warnings.
