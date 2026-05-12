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
