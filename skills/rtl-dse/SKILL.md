---
name: rtl-dse
description: "This skill should be used for deep Design Space Exploration covering spec analysis, in-depth algorithm study, architecture exploration with multiple candidates, and reference C model creation or transformation from a user-provided functional model. Covers Phase 1→2 with emphasis on algorithmic trade-offs and architectural alternatives."
---

<Purpose>
Perform deep Design Space Exploration (DSE) through Phase 1 (Research) and Phase 2 (Architecture + Reference C Model),
with significantly more depth in algorithm analysis and architecture exploration than the standard pipeline.

This skill is the "exploration front-end" of the pipeline, intended for workflows where:
- Multiple algorithmic approaches need quantitative comparison before committing
- Multiple architecture candidates must be evaluated with trade-off analysis
- A user-provided functional C model needs to be restructured into an architectural reference model
- The design team wants deep understanding before proceeding to μArch

**What makes this different from standard Phase 1→2:**

| Aspect | Standard (p1-spec-research + p2-arch-design) | rtl-dse |
|--------|------------------------------------------|---------|
| Algorithm study | Select best algorithm, justify | Explore N candidates, quantitative comparison (complexity, memory BW, gate estimates, quality impact) |
| Architecture | Single architecture from requirements | Multiple architecture candidates, trade-off matrix, user selects |
| Ref C model | Build from scratch | Accept functional C model as input, transform to architectural ref C model |
| Fixed-point | Identify precision requirements | Simulate fixed-point effects, precision vs area trade-off curves |
| Output | Ready for Phase 3 | Ready for Phase 3, with DSE rationale documented for future reference |

**Design Priority Order:**
1. Functional Correctness (highest) — Every required feature in Spec works exactly
2. Interface Compliance — Ports, protocols, timing interfaces match Architecture
3. Timing/Performance — Throughput, latency targets met
4. Area/Power (lowest)

**Document-as-Memory Principle:**
All exploration results are captured in design artifacts (docs/, reviews/) so that
downstream phases and future sessions can reference the DSE rationale without repeating exploration.

State is persisted at .rtl-agent-team/state/rtl-dse-state.json for resumability.
</Purpose>

<Use_When>
- Starting a new design where algorithmic alternatives need in-depth comparison
- Multiple architecture approaches are viable and trade-off analysis is needed
- A functional C model exists and needs to be restructured into an architectural reference model
- The design is complex enough that rushing to μArch would risk costly rework
- The user explicitly says "DSE", "design space exploration", "algorithm study", "architecture comparison"
</Use_When>

<Do_Not_Use_When>
- The algorithm is already decided and architecture is straightforward (use rtl-autopilot or rtl-spec-to-uarch)
- Only Phase 1 research is needed (use p1-spec-research)
- Only architecture design is needed with no algorithm exploration (use p2-arch-design)
- μArch or RTL implementation is needed (use rtl-p3-uarch-design or rtl-uarch-to-verify)
</Do_Not_Use_When>

<Why_This_Exists>
In complex RTL design, the most impactful decisions happen at the algorithm and architecture levels.
A poor algorithm choice costs orders of magnitude more to fix at RTL than if caught during exploration.

Standard Phase 1→2 selects a single approach and moves forward. This is efficient when the design
space is well-understood. But for novel or complex designs, exploring multiple options first is
essential — this is Design Space Exploration (DSE).

Additionally, teams often have an existing functional C model (e.g., a software reference encoder/decoder)
that computes correct outputs but does not reflect hardware block boundaries or memory access patterns.
This skill transforms such functional models into architectural reference models that serve as the
golden baseline for RTL verification.
</Why_This_Exists>

<Execution_Policy>
- State file (.rtl-agent-team/state/rtl-dse-state.json) tracks progress for resumability
- Independent sub-tasks run in parallel via concurrent Task() calls
- **Dual-Layer Phase Gates** are hard stops between Phase 1 and Phase 2:
  1. **Artifact Gate**: Required files exist
  2. **Quality Gate**: Review quality AND hierarchical spec compliance
- Quality Gate verdicts: `PASS` or `FAIL + findings[]`
- Maximum 2 Quality Gate retry cycles before escalating to user
- **User decision point**: after architecture DSE, present candidates to user for selection via AskUserQuestion
- **Functional → Architectural C model transformation**: when user provides a functional C model,
  analyze its structure then restructure it to match architecture block boundaries
- On interruption: state file preserved for resumability
- **Context Manifest**: load files per templates/context-manifest-phase-{N}.json
- **Termination**: after Phase 2 Quality Gate PASS, generate summary + ADR, then STOP
</Execution_Policy>

<Steps>
1. **Initialize state**: write .rtl-agent-team/state/rtl-dse-state.json with phase=1, sub_phase="algorithm_exploration", pipeline_scope="dse-phase-1-to-2"

1.5. **Resume check** (if state file already exists):
   - Read state, skip completed phases/steps, resume from last action
   - Clear `interrupted_reason` after successful resume

---

2. **Detect input mode**: check for user-provided functional C model
   - Scan for C source files provided by user (in specs/ or refc/ or user-specified path)
   - If functional C model found → set `input_mode = "transform"` (restructure existing model)
   - If no C model found → set `input_mode = "create"` (build from scratch)
   - Record input_mode in state file

---

3. **Phase 1 — Deep Research + Algorithm Exploration**
   - **Review artifacts setup**: `mkdir -p reviews/phase-1-research`

   **Step 3a: Requirement extraction** (same as standard Phase 1):
   - Invoke p1-spec-research skill OR delegate to spec-analyst
   - Produce: requirements.json, io_definition.json
   - Port names must use `i_`/`o_`/`io_` prefix, `{domain}_clk`, `{domain}_rst_n`

   **Step 3b: Deep algorithm exploration** (ENHANCED — this is the key differentiator):
   - For each major functional block identified in requirements.json:
     1. **Candidate enumeration**: domain experts list 2-4 algorithmic approaches
     2. **Quantitative comparison matrix** per candidate:
        - Computational complexity (operations per input unit)
        - Memory access pattern (sequential vs random, read/write ratio, bandwidth estimate)
        - HW gate count estimate (rough order of magnitude)
        - Quality/accuracy impact (PSNR/SSIM difference if applicable)
        - Parallelization potential (data-level, pipeline-level)
     3. **Fixed-point feasibility analysis**:
        - Minimum bit-width for acceptable precision
        - Rounding mode impact (truncate vs round-half-up vs convergent)
        - Precision vs area trade-off (e.g., 12-bit vs 16-bit internal paths)
     4. **HW-friendly algorithm modifications**:
        - Simplifications that reduce gate count with minimal quality loss
        - Regularization of memory access patterns for SRAM efficiency
        - Opportunities for resource sharing between blocks
   - Coordinated by `vcodec-chief-standard-expert` with sub-domain experts
   - Output: `docs/phase-1-research/domain-analysis.md` (ENHANCED with comparison matrices)

   > **Quantitative RD evaluation (optional):**
   > If ref C model encoder is buildable and test sequences are available,
   > invoke `/rtl-agent-team:codec-rd-eval` to measure BD-PSNR between algorithm candidates.
   > This provides objective quality metrics beyond theoretical analysis.
   >
   > **Decoder conformance evaluation (optional):**
   > If ref C model decoder exists and conformance bitstreams are available,
   > invoke `/rtl-agent-team:codec-conformance-eval` to verify decoder correctness
   > against JVET/JCTVC official conformance streams before committing to architecture.

   **Step 3c: Algorithm selection** (user decision point):
   - Present algorithm candidates with quantitative trade-off matrix to user via AskUserQuestion
   - User selects preferred algorithm per functional block (or accepts recommended defaults)
   - Record selections in `docs/decisions/ADR-001-algorithm-selection.md`

   **Phase 1→2 Artifact Gate**: requirements.json + io_definition.json + domain-analysis.md exist

   **Phase 1→2 Quality Gate (Research Completeness Review)**:
   - `spec-analyst` self-reviews requirements.json for completeness
   - `arch-designer` evaluates requirements for implementation feasibility
   - Algorithm comparison matrices are complete with quantitative data
   - **Save review to `reviews/phase-1-research/research-review.md`**
   - **Verdict**: PASS if requirements clear, algorithms selected with rationale; FAIL otherwise

   **Phase 1 Summary Generation**:
   - Generate `docs/phase-1-research/phase-1-summary.md`

---

4. **Phase 2 — Architecture DSE + Reference C Model**
   - **Review artifacts setup**: `mkdir -p reviews/phase-2-architecture .rtl-agent-team/scratch/phase-2`

   **Step 4a: Architecture candidate exploration** (ENHANCED — multiple candidates):
   - For the selected algorithms, `arch-designer` + domain experts propose 2-3 architecture candidates:
     1. **Candidate A**: Optimized for throughput (wider datapath, more parallelism)
     2. **Candidate B**: Optimized for area (resource sharing, sequential processing)
     3. **Candidate C** (optional): Balanced trade-off
   - For each candidate, produce:
     - Block diagram (D2)
     - Estimated area breakdown (LUT/FF for FPGA, gate count for ASIC)
     - Throughput/latency estimate
     - Memory bandwidth requirement (informed by ref C model bandwidth analysis)
     - Critical path identification
   - Output: `docs/phase-2-architecture/architecture-candidates.md` (comparison document)

   **Step 4b: Architecture selection** (user decision point):
   - Present architecture candidates with trade-off matrix to user via AskUserQuestion
   - User selects preferred architecture (or accepts recommended default)
   - Record selection in `docs/decisions/ADR-002-architecture-selection.md`

   **Step 4c: Architecture refinement**:
   - `arch-designer` refines the selected candidate into full architecture.md
   - architecture.md interface tables must use `i_`/`o_` prefix, `{domain}_clk`/`{domain}_rst_n`
   - Invoke p2-arch-design skill logic for the selected candidate

   **Step 4d: Reference C model** (parallel with Step 4c):
   - **If input_mode == "transform"** (user-provided functional C model):
     1. `ref-model-dev` analyzes the functional C model structure:
        - Identify function boundaries and data flow
        - Map functions to architecture blocks
        - Identify global state that needs to become block-local state
     2. Restructure into architectural reference C model:
        - Split monolithic functions into per-block functions matching architecture.md blocks
        - Replace global memory access with `ext_mem_read()`/`ext_mem_write()` abstraction
        - Convert global state into per-block context structs (`context_t`)
        - Add block-level I/O interfaces matching architecture port definitions
        - Preserve bitexact functional equivalence (test: original output == transformed output)
     3. Verify functional equivalence:
        - Run same test vectors through original and transformed models
        - Bitexact match required — any mismatch is a transformation bug
     4. Output: refc/*.c (restructured), refc/include/*.h

   - **If input_mode == "create"** (build from scratch):
     1. Invoke ref-model skill (standard flow)
     2. C model follows: no clock/reset, I/O as function args, ext_mem abstraction
     3. Output: refc/*.c, refc/include/*.h

   **Step 4e: 3-round iterative review** (same as standard Phase 2):
   - Coordinated by `rtl-architect`:
     (a) `rtl-architect`: spec compliance (Feature Coverage Checklist) + structural review
     (b) `vcodec-architecture-expert`: memory access patterns, performance analysis
     (c) `ref-model-dev`: architecture ↔ C model consistency
   - Round 1-2: review → targeted feedback → revision
   - Round 3 mandatory: cross-block interface audit + memory conflict analysis + ref model code review
   - After 3 rounds if not converged → escalate to user

   **Phase 2 Artifact Gate**: architecture.md + architecture-candidates.md + refc/*.c exist

   **Phase 2 Quality Gate (Architecture Review)**:
   - 3-round iterative review converged (or user-approved)
   - **Feature Coverage Checklist**: 100% REQ-NNN mapped to architecture blocks
     - **Save to `reviews/phase-2-architecture/feature-coverage.md`**
   - Architecture candidates document exists with quantitative comparison
   - Architecture selection ADR records user's decision and rationale
   - Ref C model is architecturally structured (block boundaries match architecture.md)
   - If transformed: bitexact equivalence with original functional model verified
   - **Architecture Diagram**: Save to `reviews/phase-2-architecture/architecture-diagram.md`
   - Per-round review artifacts: architecture-review-r1.md, r2.md, r3.md
   - **Save consolidated review to `reviews/phase-2-architecture/architecture-review.md`**
   - **Verdict**: PASS if 100% feature coverage AND architecture selected with rationale AND ref model consistent; FAIL otherwise

   **Phase 2 Summary Generation**:
   - Generate `docs/phase-2-architecture/phase-2-summary.md`

   **Phase 2 ADR Recording**:
   - Record 3-5 key architectural decisions in `docs/decisions/ADR-{NNN}.md`
   - Include algorithm selection ADR and architecture selection ADR

---

5. **On completion**: update state file, report summary.

   **Completion Report**:
   - Algorithm exploration: N candidates evaluated per block, selections documented
   - Architecture DSE: N candidates compared, selected architecture documented
   - Reference C model: created / transformed (bitexact equivalence verified if transformed)
   - Phase 1 artifacts: requirements.json, io_definition.json, domain-analysis.md (enhanced)
   - Phase 2 artifacts: architecture.md, architecture-candidates.md, refc/*.c
   - Reviews: research-review.md PASS, architecture-review.md PASS
   - ADR count and key decisions
   - Next step: "Run `/rtl-agent-team:rtl-p3-uarch-design` for Phase 3 μArch, or `/rtl-agent-team:rtl-spec-to-uarch` (will skip completed Phase 1-2 and run Phase 3)"

   **Do NOT proceed to Phase 3.** The pipeline stops here for human review.

---

**Gate Failure Handling:**
- **Quality Gate FAIL (same-level fix)**: pass findings to worker agent, re-run gate. Max 2 retries
- **Upper-Spec Violation**: STOP, report to user
- **Artifact Gate FAIL**: retry phase once, then escalate

**Scratchpad Convention:**
During iterative review rounds:
  .rtl-agent-team/scratch/phase-{N}/round-{R}-{agent}.md
On phase gate PASS: consolidate to reviews/, clean scratch

**Coding Convention Enforcement:**
See CLAUDE.md for full rules. C ref model: C11, no clock/reset, ext_mem abstraction.
Port naming: i_/o_/io_ prefix, {domain}_clk/{domain}_rst_n.
</Steps>

<Tool_Usage>
```
# ============================================================
# Input Detection
# ============================================================
Glob("specs/**/*.c")                    # Check for user-provided functional C model
Glob("refc/*.c")                       # Or already in refc/
# → set input_mode = "transform" or "create"

# ============================================================
# Phase 1: Deep Research + Algorithm Exploration
# ============================================================
Bash("mkdir -p reviews/phase-1-research docs/decisions")

# Step 3a: Requirement extraction
Task(subagent_type="rtl-agent-team:spec-analyst",
     prompt="Analyze spec at specs/ and produce requirements.json, io_definition.json.
Port names must use i_/o_/io_ prefix, clocks as {domain}_clk, resets as {domain}_rst_n.")

# Step 3b: Deep algorithm exploration (parallel domain experts)
Task(subagent_type="rtl-agent-team:vcodec-chief-standard-expert",
     prompt="Coordinate sub-domain experts for DEEP algorithm exploration.
For each major functional block:
1. Enumerate 2-4 algorithmic candidates
2. Produce quantitative comparison matrix:
   - Computational complexity, memory BW, gate count estimate, quality impact, parallelization potential
3. Fixed-point feasibility: minimum bit-width, rounding mode impact, precision vs area curves
4. HW-friendly modifications: simplifications, memory access regularization, resource sharing
Output: enhanced domain-analysis.md with comparison matrices per block.")

# Step 3c: Algorithm selection (user decision)
AskUserQuestion(questions=[{
  question: "Which algorithm do you prefer for each functional block? (see domain-analysis.md for trade-off matrices)",
  header: "Algorithm",
  options: [...],  # populated from domain-analysis.md candidates
  multiSelect: false
}])

# Phase 1→2 Quality Gate
Task(subagent_type="rtl-agent-team:spec-analyst",
     prompt="Self-review requirements.json. Verify completeness, consistency, algorithm selection rationale.
Save to reviews/phase-1-research/research-review.md. verdict: PASS or FAIL")

Task(subagent_type="rtl-agent-team:arch-designer",
     prompt="Feasibility review. Evaluate selected algorithms for RTL implementability.
verdict: PASS or FAIL + findings[]")

# Phase 1 Summary
Task(subagent_type="rtl-agent-team:rtl-architect", model="sonnet",
     prompt="Generate docs/phase-1-research/phase-1-summary.md from Phase 1 artifacts.")

# ============================================================
# Phase 2: Architecture DSE + Reference C Model
# ============================================================
Bash("mkdir -p reviews/phase-2-architecture .rtl-agent-team/scratch/phase-2")

# Step 4a: Architecture candidate exploration
Task(subagent_type="rtl-agent-team:arch-designer",
     prompt="Propose 2-3 architecture candidates for the selected algorithms.
For each candidate: block diagram, area estimate, throughput, latency, memory BW, critical path.
Output: docs/phase-2-architecture/architecture-candidates.md")

Task(subagent_type="rtl-agent-team:vcodec-architecture-expert",
     prompt="Review architecture candidates. Add SRAM sizing, memory port analysis,
pipeline depth estimates. Annotate architecture-candidates.md.")

# Step 4b: Architecture selection (user decision)
AskUserQuestion(questions=[{
  question: "Which architecture candidate do you prefer? (see architecture-candidates.md)",
  header: "Architecture",
  options: [...],  # populated from candidates
  multiSelect: false
}])

# Step 4c + 4d: Architecture refinement + Ref C model (parallel)
Skill(skill="rtl-agent-team:p2-arch-design")    # Refine selected candidate

# If input_mode == "transform":
Task(subagent_type="rtl-agent-team:ref-model-dev",
     prompt="Transform the user-provided functional C model into an architectural reference C model.
1. Analyze existing functional model structure and data flow
2. Map functions to architecture.md block boundaries
3. Restructure: split into per-block functions, add ext_mem_read/write abstraction,
   convert global state to per-block context_t structs
4. Verify bitexact equivalence: same test vectors → identical outputs
5. Output: refc/*.c (restructured), refc/include/*.h
C11 standard, no clock/reset, DPI-C compatible.")

# If input_mode == "create":
Skill(skill="rtl-agent-team:ref-model")

# Step 4e: 3-round iterative review (handled by p2-arch-design skill internally)
# Phase 2→ Quality Gate
# Check: reviews/phase-2-architecture/architecture-review.md verdict=PASS

# Phase 2 Summary + ADR
Task(subagent_type="rtl-agent-team:rtl-architect", model="sonnet",
     prompt="Generate docs/phase-2-architecture/phase-2-summary.md.")
Task(subagent_type="rtl-agent-team:arch-designer", model="sonnet",
     prompt="Record key decisions as ADRs in docs/decisions/.
Include: ADR-001-algorithm-selection.md, ADR-002-architecture-selection.md, plus 2-3 more.")

# ============================================================
# STOP — Pipeline ends here for human review
# ============================================================
```
</Tool_Usage>

<Examples>
**Example 1: DSE from spec with no existing C model**
```
User: "H.264 인트라 예측 모듈을 설계하려고 해. 알고리즘 비교부터 아키텍처 탐색까지 진행해줘."
→ Invoke /rtl-agent-team:rtl-dse
→ input_mode = "create" (no existing C model)
→ Phase 1: Requirement extraction + deep algorithm exploration
  - Candidate algorithms: Mode Decision (RDO-based vs SAD-based vs Hadamard-based)
  - Quantitative comparison: complexity, gate count, PSNR impact
  - Fixed-point: 10-bit vs 12-bit internal precision analysis
  - User selects: Hadamard-based (best HW/quality trade-off)
→ Phase 2: Architecture DSE
  - Candidate A: 4-mode parallel processor (high throughput, large area)
  - Candidate B: Sequential mode evaluator (small area, lower throughput)
  - Candidate C: 2-mode parallel with pipeline (balanced)
  - User selects: Candidate C
  - Ref C model built from scratch
→ STOP: "DSE 완료. 아키텍처 검토 후 /rtl-agent-team:rtl-uarch-design으로 μArch 설계를 진행하세요."
```

**Example 2: DSE with existing functional C model**
```
User: "이미 있는 functional C model을 기반으로 아키텍처를 설계해줘. specs/에 스펙도 있고
refc/transform.c에 기존 모델이 있어."
→ Invoke /rtl-agent-team:rtl-dse
→ input_mode = "transform" (existing functional C model detected)
→ Phase 1: Extract requirements + deep algorithm study (informed by existing model)
→ Phase 2: Architecture DSE + transform functional model
  - Analyze transform.c: monolithic function with global arrays
  - Restructure: split into forward_transform(), quantize(), scan() per architecture blocks
  - Add ext_mem_read/write for external coefficient buffer access
  - Verify: original output == transformed output (bitexact)
→ STOP: "DSE + 모델 변환 완료."
```

**Example 3: Simple design, DSE not needed**
```
User: "간단한 UART 설계해줘."
→ Algorithm and architecture are straightforward for UART
→ Suggest: "UART는 알고리즘 탐색이 필요하지 않습니다. /rtl-agent-team:rtl-autopilot을 사용하세요."
```
</Examples>

<Escalation_And_Stop_Conditions>
- Algorithm candidates cannot be differentiated quantitatively → ask user for priority (area vs throughput vs quality)
- Architecture candidates are too similar → ask user for dominant constraint
- Functional C model is too complex to transform automatically → report complexity, suggest manual restructuring guidance
- Phase 1 Quality Gate fails after 2 retries → ask user to clarify spec
- Phase 2 Quality Gate fails after 2 retries → ask user for architecture direction
- Ref model transformation breaks bitexact equivalence → report divergence point, ask user to verify original model correctness
</Escalation_And_Stop_Conditions>

<Final_Checklist>
Before reporting completion, verify ALL of the following:
- [ ] Phase 1: requirements.json, io_definition.json exist
- [ ] Phase 1: domain-analysis.md contains algorithm comparison matrices (not just selection)
- [ ] Phase 1: Algorithm selection ADR recorded with user's decision
- [ ] Phase 1: reviews/phase-1-research/research-review.md verdict=PASS
- [ ] Phase 1: phase-1-summary.md generated
- [ ] Phase 2: architecture-candidates.md contains 2+ candidates with quantitative comparison
- [ ] Phase 2: Architecture selection ADR recorded with user's decision
- [ ] Phase 2: architecture.md exists (refined from selected candidate)
- [ ] Phase 2: refc/*.c exists
- [ ] Phase 2: If transform mode — bitexact equivalence verified between original and transformed model
- [ ] Phase 2: reviews/phase-2-architecture/architecture-review.md verdict=PASS
- [ ] Phase 2: reviews/phase-2-architecture/feature-coverage.md shows 100% coverage
- [ ] Phase 2: phase-2-summary.md generated
- [ ] Phase 2: ADRs recorded in docs/decisions/
- [ ] Scratch directories cleaned
- [ ] State file updated with all phases completed
- [ ] Pipeline did NOT proceed to Phase 3

If ANY item is unchecked → DO NOT report completion. Fix the issue first.
</Final_Checklist>
