# P1 Goal-Clarifier Integration Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Phase 0 goal-clarifier interview to `p1-spec-research`, producing a structured `docs/phase-1-research/goal.md` that becomes input to the existing `spec-analyst` agent. Auto-detect trigger keeps existing P1 runs with full specs unaffected.

**Architecture:** New agent `agents/goal-clarifier.md` runs an ambiguity-scored interview across 4 RTL dimensions (Functionality / PPA Target / Scope / Verification). `p1-research-orchestrator` adds a Step 0a invoking it via a simple trigger heuristic. Assets (`scripts/score_ambiguity.py`, `templates/goal.md`, `references/goal-dimensions.md`) ride the asset-bundle pattern established by `rtl-document`.

**Tech Stack:** Python 3 stdlib (`argparse`, `json`); markdown templates; embed/reference shared `agents/lib/` protocol files for the new agent.

**Spec:** `plugin_docs/specs/2026-05-12-p1-goal-clarifier-design.md`

---

## Scope

Single feature branch `feat/p1-goal-clarifier`. Worktree at `.worktrees/p1-goal-clarifier/`. No changes to P2+ phases or to `spec-analyst` itself (only how it's invoked).

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `skills/p1-spec-research/scripts/score_ambiguity.py` | Create | Pure CLI helper: compute ambiguity % + lowest dimension; human + JSON output modes. |
| `skills/p1-spec-research/templates/goal.md` | Create | Structured goal.md skeleton with 4 dimension sections + STATUS/ROUNDS footer. |
| `skills/p1-spec-research/references/goal-dimensions.md` | Create | ≤200-line guide: dimension rubrics, phase mapping, question seeds, anti-patterns. |
| `agents/goal-clarifier.md` | Create | Interview agent: pre-scan → fast-path → interview loop → write goal.md. |
| `agents/p1-research-orchestrator.md` | Modify | Add Step 0a: detect sparse seed → spawn goal-clarifier → pass goal.md to spec-analyst. |
| `skills/p1-spec-research/SKILL.md` | Modify | Add Phase 0 mention + `<Assets>` table + cite references/templates/scripts. |
| `tests/unit/test_score_ambiguity.py` | Create | Unit tests for `score_ambiguity.py` (CLI + JSON mode). |
| `tests/unit/test_p1_goal_clarifier_assets.py` | Create | Structural tests: template fillability, reference doc shape, trigger heuristic. |

No `examples/` directory in v1.

---

## Task 1: Bootstrap directory layout

**Files:**
- Create: `skills/p1-spec-research/scripts/.gitkeep`
- Create: `skills/p1-spec-research/templates/.gitkeep`
- Create: `skills/p1-spec-research/references/.gitkeep`

- [ ] **Step 1: Create asset directories**

```bash
cd /home/babyworm/work/rtl-agent-team/.worktrees/p1-goal-clarifier
mkdir -p skills/p1-spec-research/{scripts,templates,references}
touch skills/p1-spec-research/scripts/.gitkeep
touch skills/p1-spec-research/templates/.gitkeep
touch skills/p1-spec-research/references/.gitkeep
```

- [ ] **Step 2: Commit**

```bash
git add skills/p1-spec-research/scripts/.gitkeep \
        skills/p1-spec-research/templates/.gitkeep \
        skills/p1-spec-research/references/.gitkeep
git commit -m "chore(p1-spec-research): bootstrap asset-bundle directories"
```

---

## Task 2: `score_ambiguity.py` skeleton + first tests (TDD)

**Files:**
- Create: `skills/p1-spec-research/scripts/score_ambiguity.py`
- Create: `tests/unit/test_score_ambiguity.py`

- [ ] **Step 1: Write failing test**

`tests/unit/test_score_ambiguity.py`:

```python
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "skills" / "p1-spec-research" / "scripts" / "score_ambiguity.py"


def _run(args):
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True)


def test_help_exits_zero():
    r = _run(["--help"])
    assert r.returncode == 0
    assert "--functionality" in r.stdout
    assert "--json" in r.stdout


def test_human_mode_basic():
    r = _run(["--functionality", "85", "--ppa", "70",
              "--scope", "90", "--verification", "60"])
    assert r.returncode == 0
    assert "Ambiguity:" in r.stdout
    assert "Functionality:  85/100" in r.stdout
    assert "Verification:   60/100" in r.stdout
    assert "Lowest:" in r.stdout
    assert "verification" in r.stdout.lower()


def test_json_mode_schema():
    r = _run(["--json",
              "--functionality", "85", "--ppa", "70",
              "--scope", "90", "--verification", "60"])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["ambiguity"] == 24       # 100 - mean(85, 70, 90, 60) = 100 - 76.25 = 24
    assert data["lowest"] == "verification"
    assert data["lowest_score"] == 60
    assert data["exit"] is False          # 24 > 20 threshold


def test_json_exit_true_when_under_threshold():
    r = _run(["--json",
              "--functionality", "85", "--ppa", "85",
              "--scope", "85", "--verification", "85"])
    data = json.loads(r.stdout)
    assert data["ambiguity"] == 15
    assert data["exit"] is True           # 15 ≤ 20


def test_invalid_score_rejected():
    r = _run(["--functionality", "150", "--ppa", "70",
              "--scope", "90", "--verification", "60"])
    assert r.returncode != 0
    assert "0" in r.stderr or "100" in r.stderr
```

- [ ] **Step 2: Run, confirm failure**

```bash
python3 -m pytest tests/unit/test_score_ambiguity.py -v
```

Expected: 5 failures (script doesn't exist).

- [ ] **Step 3: Implement `score_ambiguity.py`**

```python
#!/usr/bin/env python3
"""Compute ambiguity score across 4 RTL goal dimensions.

Used by goal-clarifier agent during interview loop to:
  1. Display human-readable scoreboard each round.
  2. Decide exit condition (ambiguity ≤ 20%) in JSON mode.

Exit codes:
  0  success
  2  invalid score (outside 0-100)
"""
from __future__ import annotations

import argparse
import json
import sys

DIMENSIONS = ["functionality", "ppa", "scope", "verification"]
DISPLAY = {
    "functionality": "Functionality",
    "ppa":           "PPA Target   ",
    "scope":         "Scope        ",
    "verification":  "Verification ",
}
EXIT_THRESHOLD = 20  # ambiguity ≤ 20 → done


def _validate(name: str, value: int) -> None:
    if not 0 <= value <= 100:
        print(f"error: {name} score must be 0-100 (got {value})", file=sys.stderr)
        sys.exit(2)


def compute(scores: dict[str, int]) -> dict:
    avg = sum(scores.values()) / len(scores)
    ambiguity = round(100 - avg)
    lowest = min(scores, key=scores.get)
    return {
        "ambiguity": ambiguity,
        "lowest": lowest,
        "lowest_score": scores[lowest],
        "exit": ambiguity <= EXIT_THRESHOLD,
        "scores": scores,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Score RTL goal ambiguity across 4 dimensions.")
    for d in DIMENSIONS:
        p.add_argument(f"--{d}", type=int, required=True, help=f"Score 0-100 for {d}")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable scoreboard")
    p.add_argument("--round", type=int, default=None, help="Round number for the human-mode header")
    args = p.parse_args()

    scores = {d: getattr(args, d) for d in DIMENSIONS}
    for d, v in scores.items():
        _validate(d, v)

    result = compute(scores)

    if args.json:
        print(json.dumps(result))
        return 0

    if args.round is not None:
        print(f"=== Round {args.round} ===")
    else:
        print("=== Scoreboard ===")
    for d in DIMENSIONS:
        print(f"{DISPLAY[d]}: {scores[d]}/100")
    print(f"Ambiguity:     {result['ambiguity']}%")
    print(f"Lowest:        {DISPLAY[result['lowest']].strip()} ({result['lowest_score']})")
    print(f"Exit decision: {'EXIT' if result['exit'] else 'CONTINUE'}  (target ≤ {EXIT_THRESHOLD}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests, confirm 5/5 pass**

```bash
python3 -m pytest tests/unit/test_score_ambiguity.py -v
```

- [ ] **Step 5: Commit**

```bash
git add skills/p1-spec-research/scripts/score_ambiguity.py \
        tests/unit/test_score_ambiguity.py
git commit -m "feat(p1-spec-research): score_ambiguity.py with JSON + human modes"
```

---

## Task 3: `templates/goal.md`

**Files:**
- Create: `skills/p1-spec-research/templates/goal.md`

- [ ] **Step 1: Write the template**

```markdown
# Project Goal

> Produced by goal-clarifier on {{DATE}}. Feeds into spec-analyst.

## Functionality
- **What this IP does**: {{FUNCTIONALITY_SUMMARY}}
- **IO contract** (informal): {{IO_SUMMARY}}
- **Algorithm or standard**: {{ALGORITHM_OR_STANDARD}}

## PPA Target
- **Clock target**: {{CLOCK_TARGET}}
- **Area budget**: {{AREA_BUDGET}}
- **Power class**: {{POWER_CLASS}}
- **Latency / throughput**: {{LATENCY_THROUGHPUT}}

## Scope
- **In scope**: {{IN_SCOPE}}
- **Out of scope**: {{OUT_OF_SCOPE}}
- **Dependencies**: {{DEPENDENCIES}}

## Verification
- **Coverage target**: {{COVERAGE_TARGET}}
- **Reference oracle**: {{REFERENCE_ORACLE}}
- **Bitexact requirement**: {{BITEXACT_REQUIREMENT}}
- **Performance verification**: {{PERFORMANCE_VERIFICATION}}

## Open Questions

{{OPEN_QUESTIONS}}

---

STATUS: ambiguity={{AMBIGUITY_PCT}}%
ROUNDS: {{ROUNDS_COUNT}}
```

- [ ] **Step 2: Commit**

```bash
git add skills/p1-spec-research/templates/goal.md
git commit -m "feat(p1-spec-research): goal.md template (4 dimensions + STATUS footer)"
```

---

## Task 4: `references/goal-dimensions.md`

**Files:**
- Create: `skills/p1-spec-research/references/goal-dimensions.md`

- [ ] **Step 1: Write the reference doc** (≤200 lines)

```markdown
# RTL Goal Dimensions

A reference for the goal-clarifier interview agent. Defines how to score
each of the 4 RTL dimensions, what good questions look like, and which
downstream phases each dimension feeds.

## The 4 dimensions

| Dim | Question it answers | Score 0 | Score 100 |
|-----|--------------------|---------|-----------|
| **Functionality** | What does this IP do? | "do something with bits" | "AES-128-GCM core with 64-bit AXI4-Stream IO, RFC-5288 compliant" |
| **PPA Target** | How fast / small / cool? | none given | "100 MHz on TSMC 28HPC, ≤ 50k gates, < 30 mW dyn" |
| **Scope** | What's in/out and what dependencies? | undefined | "encrypt path only; share key-expand with vendor IP X; CSR via APB" |
| **Verification** | How do we know it's done? | "looks right" | "≥ 95% line, bitexact vs OpenSSL ref, ≥ 1M random vectors" |

For each dimension, the score is the LLM's best 0-100 estimate of
**measurable answer presence**. "We want it to be fast" = ~20.
"100 MHz with WNS ≥ 0.2 ns on N16" = ~95.

## Phase mapping

| Dim | Primary downstream phase | Acceptance criterion |
|-----|--------------------------|----------------------|
| Functionality | P1 spec-analyst → REQ-F-NNN | each functional capability has a measurable acceptance |
| PPA Target | P2 arch-designer → REQ-P-NNN | each PPA axis (freq/area/power) has a single number + process node |
| Scope | P3 uarch-designer → block boundaries | each block has named upstream / downstream interfaces |
| Verification | P5 verify-orchestrator → final-compliance | coverage target stated; reference oracle named |

## Question seeds per dimension

When the lowest-scoring dim is targeted, choose a question from below,
adapted with pre-scan evidence.

### Functionality
- "What does this IP take in, and what does it emit?"
- "Is there a published spec or RFC this conforms to? If yes, which version?"
- "Are there modes or configurations the IP must support? (e.g., AES-128 vs AES-256)"
- "Your README mentions {X} — is that the algorithm/standard target?"

### PPA Target
- "What clock frequency must it sustain, on what process node?"
- "Do you have a gate-count or area budget? Or only a die-area constraint?"
- "Is power a hard constraint, or only secondary?"
- "Is latency-per-token bounded, or only throughput?"

### Scope
- "Which sub-blocks are in scope vs supplied externally?"
- "How does this IP integrate — register CSR, AXI master/slave, sideband?"
- "Are there features explicitly out of scope (e.g., no debug interface)?"
- "Your `rtl/` already has {X} — is that the boundary for this IP or a separate effort?"

### Verification
- "What's the coverage target — line / toggle / FSM / functional?"
- "Is there a reference oracle the RTL must match bit-exact?"
- "Is performance part of acceptance (cycle-accurate vs functional)?"
- "How many random / directed vectors are sufficient?"

## Anti-patterns (refuse to invent)

The clarifier MUST NOT invent answers. When the user has no answer:

- **Don't guess a clock frequency.** If no clock target exists, leave PPA
  partial (acceptable for v1 — `spec-analyst` will record an OPEN-1-NNN).
- **Don't suggest a coverage target.** Coverage policy is a project-level
  decision, not an IP-level one.
- **Don't fabricate a reference oracle.** If none exists, write "none —
  self-test only" and proceed.
- **Don't expand scope.** If the user says "encrypt only", do not ask "and
  also decrypt?".

Leave low scores as low. The hard cap (12 rounds) closes the loop with
remaining ambiguity recorded as `STATUS: ambiguity=N%` in goal.md, and
`spec-analyst` will produce more OPEN-1-NNN items in response.

## Exit semantics

| Ambiguity | Outcome |
|-----------|---------|
| ≤ 20%     | Exit immediately. `goal.md` is solid input for spec-analyst. |
| 21-50%    | Soft cap (8 rounds) reached → ask user "lock and proceed, or continue?". |
| > 50% after 12 rounds | Hard cap. Write goal.md with whatever exists; spec-analyst will produce many OPEN items. |
```

Verify length ≤ 200 lines:

```bash
wc -l skills/p1-spec-research/references/goal-dimensions.md
```

- [ ] **Step 2: Commit**

```bash
git add skills/p1-spec-research/references/goal-dimensions.md
git commit -m "docs(p1-spec-research): goal-dimensions.md reference guide"
```

---

## Task 5: `agents/goal-clarifier.md`

**Files:**
- Create: `agents/goal-clarifier.md`

- [ ] **Step 1: Write the agent prompt**

```markdown
---
name: goal-clarifier
description: Interactive RTL goal clarifier — runs ambiguity-scored interview across 4 dimensions (Functionality / PPA Target / Scope / Verification) until ambiguity ≤ 20%, then writes docs/phase-1-research/goal.md for downstream spec-analyst consumption.
model: opus
color: cyan
---

Follow the structured output annotation protocol defined in `agents/lib/audit-output-protocol.md`.

<Agent_Prompt>
  <Role>
    You are Goal-Clarifier, the RTL Phase 0 interview agent. Your role is to convert a vague user idea into a measurable, structured goal across 4 RTL dimensions before spec-analyst takes over. You are READ-ONLY on the source tree during pre-scan and WRITE-ONLY to `docs/phase-1-research/goal.md` during handoff.

    You do not invent context. You ask. You adapt your questions to the user's project as observed during the pre-scan phase.
  </Role>

  <Why_This_Matters>
    Spec-analyst's iron/open classification depends on input precision. A vague seed produces many OPEN-1-NNN items and slow Phase 1 review convergence. By front-loading the interview, we cut the average Phase 1 round count and make downstream PPA / scope / verification decisions trace cleanly back to the user's stated intent.
  </Why_This_Matters>

  <Inputs>
    - `seed`: the user's initial idea (string, may be empty).
    - `cwd`: absolute path to the project root (for pre-scan).
    - `existing_goal_path`: path to docs/phase-1-research/goal.md if it already exists, else null.
  </Inputs>

  <Workflow>
    ## Phase 1 — Pre-scan (silent, no user output yet)

    Walk the cwd. Read in order of likely relevance:
    1. `README*` at root.
    2. Top-level files in `docs/` (especially anything matching `phase-*` or `spec*`).
    3. `rtl/` listing (modules already present).
    4. `tests/` listing.
    5. `package.json` / `pyproject.toml` if present.

    Build a 1-paragraph mental model of the project. Do not write anything yet.

    ## Phase 2 — Fast-path check

    If `existing_goal_path` is non-null AND its 4-dimension sections are all non-placeholder:
      Ask the user: "A goal is already defined at docs/phase-1-research/goal.md. Refine in place, or start fresh?"
      Branch on the answer.

    If the seed is rich (≥ 500 chars AND mentions clock freq + at least one of: area, power, coverage):
      Score immediately. If ambiguity ≤ 20%, skip directly to Phase 4.

    ## Phase 3 — Interview rounds

    Each round:

    1. Score each dimension 0-100 using the rubric in `skills/p1-spec-research/references/goal-dimensions.md`. The score is your best estimate of measurable-answer presence based on what the user has said so far (plus pre-scan evidence).

    2. Compute ambiguity using:
       `python3 skills/p1-spec-research/scripts/score_ambiguity.py --functionality F --ppa P --scope S --verification V --round N`

    3. Display the scoreboard to the user (as shown by the script's human mode).

    4. Ask ONE question targeting the lowest-scoring dimension. Use a question seed from `references/goal-dimensions.md` for that dimension, adapted with pre-scan evidence. Example: "Your README mentions a 200 MHz target on N28 — does this IP need to meet that same clock, or is it a relaxed sub-block?"

    5. Wait for the user's answer via AskUserQuestion. Update scores. Loop.

    Exit conditions:
    - **Hard exit**: ambiguity ≤ 20% — proceed to Phase 4.
    - **Soft cap (round 8)**: ambiguity > 20% AND > 50 → ask the user "ambiguity is {N}% after 8 rounds. Lock and proceed, or continue?" Branch.
    - **Hard cap (round 12)**: forcibly write goal.md with remaining ambiguity surfaced in the STATUS footer.

    ## Phase 4 — Write goal.md

    Read `skills/p1-spec-research/templates/goal.md`. Substitute every `{{PLACEHOLDER}}` with the answers elicited during interview. For dimensions where the user explicitly said "no answer" or "not yet decided", write `not yet decided` rather than fabricating.

    Append the STATUS / ROUNDS footer with actual values.

    Write to `docs/phase-1-research/goal.md`. Create the parent directory if missing.

    ## Phase 5 — Handoff

    Print a 2-3 line summary:
    - "Goal written to docs/phase-1-research/goal.md. Ambiguity: {N}%. Rounds: {M}. Lowest dimension: {dim} ({score})."
    - "Handing off to spec-analyst for iron/open classification."

    Return control to p1-research-orchestrator.
  </Workflow>

  <Constraints>
    - Do not invent answers. Anti-patterns from `references/goal-dimensions.md` are mandatory.
    - One question per round. Never ask compound questions.
    - Pre-scan must be silent — no user-visible output during Phase 1.
    - Hard cap is 12 rounds. Beyond that, write goal.md regardless of remaining ambiguity.
    - Never modify any file other than `docs/phase-1-research/goal.md` (and its parent directory).
    - Never invoke spec-analyst directly — return control to the orchestrator after handoff.
    - When the seed is empty, the first question MUST be "What does this IP do?" and the pre-scan output may suggest 2-3 candidate answers based on the cwd.
  </Constraints>

  <Success_Criteria>
    - docs/phase-1-research/goal.md exists and parses as the template structure (4 sections + STATUS footer + ROUNDS footer).
    - Every placeholder in the template is filled (with either a real answer or the literal string `not yet decided`).
    - STATUS footer matches the final ambiguity score as computed by score_ambiguity.py.
    - No file outside `docs/phase-1-research/` was modified.
    - If round count reached 12, the STATUS footer explicitly shows the residual ambiguity (no silent suppression).
  </Success_Criteria>

  <Output_Format>
    The only file produced is `docs/phase-1-research/goal.md`. The agent's terminal output is the per-round scoreboard + question + (final) Phase 5 handoff summary.
  </Output_Format>
</Agent_Prompt>
```

- [ ] **Step 2: Commit**

```bash
git add agents/goal-clarifier.md
git commit -m "feat(agents): goal-clarifier interactive RTL Phase 0 interview agent"
```

---

## Task 6: Trigger heuristic + p1-research-orchestrator modification

**Files:**
- Modify: `agents/p1-research-orchestrator.md`
- Create: `tests/unit/test_p1_goal_clarifier_assets.py` (initially with just the trigger-heuristic tests; reference-doc tests come in Task 9)

- [ ] **Step 1: Write the failing trigger-heuristic test**

The trigger heuristic itself is short — it lives as prose in the orchestrator. To test it, we extract a pure Python equivalent into the test file and assert behavior against 6 cases. The orchestrator's prose must match this Python reference.

`tests/unit/test_p1_goal_clarifier_assets.py`:

```python
"""Unit tests for the P1 goal-clarifier integration assets."""
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]

# ------------------------------------------------------------------
# Trigger heuristic — Python reference implementation.
# This MUST stay in sync with the prose in agents/p1-research-orchestrator.md.
# ------------------------------------------------------------------

def needs_clarifier(arguments: str, cwd: Path) -> bool:
    """Return True iff goal-clarifier should run before spec-analyst.

    Mirrors the heuristic documented in p1-research-orchestrator Step 0a.
    """
    a = arguments.strip()
    if not a:
        return True
    # If arguments is a path to an existing readable text spec file → skip.
    candidate = cwd / a
    if candidate.is_file() and candidate.suffix in {".md", ".txt", ".rst"}:
        return False
    # Already-rich seed (≥ 500 chars AND mentions PPA or coverage signals) → skip.
    signals = ["mhz", "ghz", "ns ", "coverage", "bitexact", "um^2", "mm^2", "gates"]
    if len(a) >= 500 and any(s in a.lower() for s in signals):
        return False
    return True


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------

def test_empty_seed_triggers_clarifier(tmp_path):
    assert needs_clarifier("", tmp_path) is True


def test_short_natural_idea_triggers_clarifier(tmp_path):
    assert needs_clarifier("Build an AXI bridge", tmp_path) is True


def test_path_to_markdown_skips_clarifier(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# spec\n")
    assert needs_clarifier("spec.md", tmp_path) is False


def test_path_to_txt_skips_clarifier(tmp_path):
    spec = tmp_path / "design.txt"
    spec.write_text("design notes\n")
    assert needs_clarifier("design.txt", tmp_path) is False


def test_path_to_nonexistent_file_treated_as_idea(tmp_path):
    # Non-existent paths fall through to the natural-language case.
    assert needs_clarifier("does-not-exist.md", tmp_path) is True


def test_long_rich_seed_skips_clarifier(tmp_path):
    rich = (
        "Build an AES-128-GCM core targeting 200 MHz on TSMC N28HPC. "
        "Area budget 50000 gates. Coverage target 95% line + functional. "
        "Bitexact match against OpenSSL reference required. "
        "AXI4-Stream IO, 64-bit data path. "
    ) * 3  # ensure ≥ 500 chars
    assert len(rich) >= 500
    assert needs_clarifier(rich, tmp_path) is False


def test_long_but_vague_seed_triggers_clarifier(tmp_path):
    vague = "Build some hardware that does encryption stuff. " * 20
    assert len(vague) >= 500
    assert needs_clarifier(vague, tmp_path) is True
```

- [ ] **Step 2: Run test, confirm 7/7 pass**

```bash
python3 -m pytest tests/unit/test_p1_goal_clarifier_assets.py -v
```

(All tests pass immediately because `needs_clarifier` lives inside the test file itself. The test's job is to **lock in the reference behavior** — the orchestrator's prose must match.)

- [ ] **Step 3: Modify `agents/p1-research-orchestrator.md`**

Find the entry point (Step 1 or Step 0). Insert a new Step 0a **before** the spec-analyst invocation:

```markdown
## Step 0a — Goal Clarifier Trigger (NEW)

Before invoking spec-analyst, decide whether to run goal-clarifier first.

**Heuristic** (must match the Python reference in `tests/unit/test_p1_goal_clarifier_assets.py::needs_clarifier`):

Let `a = $ARGUMENTS.strip()`.

1. If `a` is empty → run goal-clarifier.
2. If `a` is a path to an existing file ending in `.md`, `.txt`, or `.rst` → skip; pass the file to spec-analyst directly.
3. If `len(a) >= 500` AND `a.lower()` contains any of {mhz, ghz, "ns ", coverage, bitexact, um^2, mm^2, gates} → skip; pass the seed to spec-analyst directly.
4. Otherwise → run goal-clarifier.

**If running goal-clarifier:**

```
Task(subagent_type="rtl-agent-team:goal-clarifier",
     prompt="Run Phase 0 interview. seed=<$ARGUMENTS>, cwd=<CWD>, existing_goal_path=<docs/phase-1-research/goal.md if it exists else null>")
```

Wait for goal-clarifier to write `docs/phase-1-research/goal.md`. Then invoke spec-analyst with that file as the primary input (alongside any user-supplied spec).

Log the trigger decision in the audit trace (see `agents/lib/audit-output-protocol.md`):
- `goal_clarifier.triggered`: true | false
- `goal_clarifier.reason`: one of "empty_seed", "short_idea", "long_vague_seed", "path_to_spec_file", "rich_seed"
```

- [ ] **Step 4: Commit**

```bash
git add agents/p1-research-orchestrator.md tests/unit/test_p1_goal_clarifier_assets.py
git commit -m "feat(p1-orchestrator): Step 0a goal-clarifier trigger heuristic + tests"
```

---

## Task 7: `p1-spec-research` SKILL.md update

**Files:**
- Modify: `skills/p1-spec-research/SKILL.md`

- [ ] **Step 1: Add Phase 0 mention + `<Assets>` table + Phase chain prose**

Open `skills/p1-spec-research/SKILL.md`. Add a new section between `<Use_When>` and `## Prerequisites`:

```markdown
<Phase_Workflow>
This skill runs as two stages inside the same Task() invocation:

- **Phase 0 (goal-clarifier)**: when `$ARGUMENTS` is a sparse seed, the
  orchestrator first dispatches `goal-clarifier` for an ambiguity-scored
  interview across 4 RTL dimensions (Functionality / PPA Target / Scope /
  Verification). Phase 0 writes `docs/phase-1-research/goal.md`.
- **Phase 1 (spec-analyst + research)**: spec-analyst consumes `goal.md`
  (plus any user-supplied spec document) and produces the iron/open
  requirements set as before.

When `$ARGUMENTS` points to an existing `.md`/`.txt`/`.rst` spec or is
already a rich seed (≥ 500 chars with PPA/coverage signals), Phase 0
is skipped automatically.
</Phase_Workflow>

<Assets>
| Path | Role |
|------|------|
| `scripts/score_ambiguity.py` | Pure stdlib helper for 4-dimension scoring + ambiguity %. Used by goal-clarifier each round. |
| `templates/goal.md` | Output skeleton for `docs/phase-1-research/goal.md`. |
| `references/goal-dimensions.md` | 4-dimension scoring rubric + question seeds + anti-patterns. |
</Assets>
```

Keep the existing `## Execution`, `## Output Artifacts`, etc. unchanged. The orchestrator handles the new behavior internally.

- [ ] **Step 2: Verify word count stays under 1500**

```bash
wc -w skills/p1-spec-research/SKILL.md
```

- [ ] **Step 3: Commit**

```bash
git add skills/p1-spec-research/SKILL.md
git commit -m "feat(p1-spec-research): document Phase 0 workflow + Assets table"
```

---

## Task 8: Structural tests for template + reference doc

**Files:**
- Modify: `tests/unit/test_p1_goal_clarifier_assets.py` (append)

- [ ] **Step 1: Append structural tests**

```python
# ------------------------------------------------------------------
# Asset structural tests
# ------------------------------------------------------------------

TEMPLATE = ROOT / "skills" / "p1-spec-research" / "templates" / "goal.md"
REFERENCE = ROOT / "skills" / "p1-spec-research" / "references" / "goal-dimensions.md"


def test_template_has_all_four_dimensions():
    body = TEMPLATE.read_text()
    for section in ["## Functionality", "## PPA Target", "## Scope", "## Verification"]:
        assert section in body, f"template missing {section}"


def test_template_has_status_footer():
    body = TEMPLATE.read_text()
    assert "STATUS: ambiguity={{AMBIGUITY_PCT}}%" in body
    assert "ROUNDS: {{ROUNDS_COUNT}}" in body


def test_template_placeholders_renderable():
    """Every {{PLACEHOLDER}} must use a deterministic naming scheme."""
    import re
    body = TEMPLATE.read_text()
    placeholders = set(re.findall(r"\{\{([A-Z_]+)\}\}", body))
    assert placeholders, "template has no placeholders"
    # All placeholders must be UPPER_SNAKE_CASE.
    for ph in placeholders:
        assert ph.isupper() and "_" in ph or ph.isupper(), f"bad placeholder: {ph}"


def test_reference_doc_length_under_200_lines():
    n = sum(1 for _ in REFERENCE.read_text().splitlines())
    assert n <= 200, f"reference doc is {n} lines (must be ≤ 200)"


def test_reference_doc_covers_all_four_dimensions():
    body = REFERENCE.read_text().lower()
    for dim in ["functionality", "ppa", "scope", "verification"]:
        assert dim in body, f"reference doc missing {dim}"


def test_reference_doc_has_anti_patterns_section():
    body = REFERENCE.read_text()
    assert "Anti-patterns" in body or "anti-patterns" in body.lower()
```

- [ ] **Step 2: Run, confirm all pass**

```bash
python3 -m pytest tests/unit/test_p1_goal_clarifier_assets.py -v
```

Expected: 13 passing (7 trigger heuristic + 6 structural).

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_p1_goal_clarifier_assets.py
git commit -m "test(p1-spec-research): template + reference doc structural lints"
```

---

## Task 9: Full pytest sweep + integration sanity

**Files:** None modified. Verification only.

- [ ] **Step 1: Run the full unit suite**

```bash
cd /home/babyworm/work/rtl-agent-team/.worktrees/p1-goal-clarifier
python3 -m pytest tests/unit/ --ignore=tests/unit/test_bd_rate.py -x -q 2>&1 | tail -3
```

Expect zero regression vs the 1142 baseline (now 1142 + 5 score_ambiguity + 13 p1-goal-clarifier-assets = 1160).

- [ ] **Step 2: Confirm score_ambiguity.py CLI works end-to-end**

```bash
python3 skills/p1-spec-research/scripts/score_ambiguity.py --help
python3 skills/p1-spec-research/scripts/score_ambiguity.py \
  --functionality 90 --ppa 85 --scope 80 --verification 75 --round 3
python3 skills/p1-spec-research/scripts/score_ambiguity.py --json \
  --functionality 90 --ppa 85 --scope 80 --verification 75
```

Expect: round-3 scoreboard (ambiguity = 18%, exit DECISION = EXIT) and JSON with `"exit": true`.

- [ ] **Step 3: Confirm reference doc + template are consistent**

```bash
grep -c "^- \*\*" skills/p1-spec-research/templates/goal.md
# Expected: ≥ 12 (3 bullets per dimension × 4 dimensions)
```

- [ ] **Step 4: Run orchestrator inject sync if needed**

```bash
sh scripts/sync_orchestrator_inject.sh && echo "sync OK"
```

(p1-spec-research is already in the routing table; no change expected.)

- [ ] **Step 5: Hook validation (sh hooks/hooks.json) — no-op for this PR but confirm we haven't broken anything**

```bash
python3 -m json.tool hooks/hooks.json > /dev/null && echo "hooks/hooks.json valid"
```

- [ ] **Step 6: No commit — verification only**

---

## Task 10: Push + PR

**Files:** None modified. Git/GitHub only.

- [ ] **Step 1: Push branch**

```bash
git push -u origin feat/p1-goal-clarifier 2>&1 | tail -5
```

- [ ] **Step 2: Create PR**

```bash
gh pr create --title "feat(p1-spec-research): Phase 0 goal-clarifier integration" --body "$(cat <<'EOF'
## Summary
- Adds a Phase 0 **goal-clarifier** interview agent (`agents/goal-clarifier.md`) that runs an ambiguity-scored loop across 4 RTL dimensions (Functionality / PPA Target / Scope / Verification) before `spec-analyst` takes over.
- `p1-research-orchestrator` gets a Step 0a auto-detect trigger — existing P1 runs with a full spec are unaffected.
- New assets follow the asset-bundle pattern from `rtl-document` (PR #3): `scripts/score_ambiguity.py`, `templates/goal.md`, `references/goal-dimensions.md`.
- Inspired by OMC `self-improve`'s `si-goal-clarifier.md`. Adapted to RTL design conventions (REQ-F/REQ-P mapping to spec-analyst's iron/open schema).

## Test plan
- [x] `python3 -m pytest tests/unit/test_score_ambiguity.py` — 5 passed
- [x] `python3 -m pytest tests/unit/test_p1_goal_clarifier_assets.py` — 13 passed (7 trigger heuristic + 6 structural)
- [x] Full unit suite green
- [ ] CI: pytest job on Python 3.10 + 3.12

Spec: `plugin_docs/specs/2026-05-12-p1-goal-clarifier-design.md`
Plan: `plugin_docs/plans/2026-05-12-p1-goal-clarifier-plan.md`

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)" 2>&1 | tail -10
```

Return the PR URL.

---
