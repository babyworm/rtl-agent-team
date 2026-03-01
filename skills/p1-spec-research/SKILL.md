---
name: p1-spec-research
description: "Phase 1 spec research skill. Refines spec precisely, collects missing information via AskUserQuestion and domain-consult, surveys candidate algorithms/tools with trade-offs, and proposes options matching user requirements. Architecture design is deferred to Phase 2. Produces domain-analysis.md, requirements.json, and io_definition.json."
---

<Purpose>
Phase 1: Precise spec refinement, information gathering, and algorithm/tool candidate survey.
This is the foundation phase — thoroughness here prevents costly rework in later phases.

**This phase does NOT design architecture.** Efficient HW architecture, block partitioning,
and pipeline stage breakdown are Phase 2 (p2-arch-design) responsibilities.

Three core activities:

1. **Spec refinement and information gathering** — the FIRST priority:
   - Precisely refine the user's specification: clarify ambiguities, fill gaps, resolve conflicts
   - Identify what information is MISSING for algorithm study and proactively request it via AskUserQuestion
   - Actively invoke `domain-consult` skill to obtain domain expert knowledge on unfamiliar areas
   - Example: For an encoder, if ME algorithm study requires reference frame count, buffer size, or
     target bitrate — ask the user. If coding tool characteristics are unclear — consult domain experts.

2. **Algorithm/tool candidate survey and proposal** (domain-analysis.md) — the PRIMARY creative output:
   - Survey candidate algorithms and coding tools for each functional area
   - For each candidate, document: computational complexity, memory access patterns, quality impact,
     HW-friendliness, and any known HW implementation data from literature
   - **Propose multiple candidates** with clear trade-off comparisons so the user can make an informed choice
   - Example: "For motion estimation, candidates are: (A) diamond search — low complexity, moderate quality;
     (B) TZ search — higher complexity, better quality; (C) full search — highest complexity, best quality.
     Published HW data: diamond search achieves X gates at Y MHz, TZ search achieves..."
   - Leverage existing HW implementation data when available (gate counts, throughput, power from papers)
   - Do NOT select a final algorithm — present candidates with recommendations for user decision

3. **Structured requirement extraction** (requirements.json, io_definition.json):
   - Transform the refined spec and user-confirmed scope into structured, traceable requirements
   - Define the system I/O boundary

**AskUserQuestion is the primary communication tool in this phase.**
Every ambiguity, design choice, or scope decision must be resolved via AskUserQuestion BEFORE proceeding.
Do not assume — ask. The cost of asking is low; the cost of a wrong assumption cascades to all later phases.

**domain-consult is the primary knowledge acquisition tool.**
Actively invoke `/rtl-agent-team:domain-consult` to get domain expert answers on algorithms, standards,
coding tools, filter characteristics, and HW implementation trade-offs. Do not rely solely on spec reading.

Domain experts provide knowledge; spec-analyst captures the results as structured artifacts.
</Purpose>

<Use_When>
- Starting Phase 1 of the RTL pipeline
- Specification has changed and artifacts need regeneration
- Domain knowledge gap exists before architecture decisions
</Use_When>

<Do_Not_Use_When>
- Artifacts already exist and spec has not changed
- Only a quick domain question needs answering (use domain-consult instead)
</Do_Not_Use_When>

<Why_This_Exists>
Codec specifications are dense and cross-referenced. Multiple domain experts must reconcile
their interpretations before a unified requirements set can drive architecture.
Separating this from p2-arch-design prevents spec ambiguity from corrupting structural decisions.

The research phase uses 4 sub-domain codec experts (vcodec-syntax-entropy, vcodec-prediction,
vcodec-transform-quant, vcodec-filter-recon) coordinated by a vcodec-chief-standard-expert who
iteratively reviews their combined output until it reaches Architecture-ready quality (3 mandatory
rounds by default). This ensures cross-block dependencies are identified and resolved before Phase 2.
</Why_This_Exists>

<Execution_Policy>
- **AskUserQuestion first**: Resolve all ambiguities BEFORE any delegation. Do not proceed with assumptions.
- **domain-consult actively**: Invoke `/rtl-agent-team:domain-consult` to acquire domain knowledge on
  algorithms, coding tools, filter characteristics, and HW trade-offs. Do not research in isolation.
- **Domain/paper study before analysis**: Conduct literature survey (Step 1.8) BEFORE sub-domain expert delegation.
  This ensures candidate survey is informed by state-of-the-art research, not just spec reading.
- **Propose, do not decide**: Present algorithm/tool candidates with trade-offs. Let the user make final selections.
  Architecture-level decisions (pipeline, block partitioning, memory hierarchy) are Phase 2's responsibility.
- Run sub-domain experts (vcodec-syntax-entropy, vcodec-prediction, vcodec-transform-quant, vcodec-filter-recon),
  video-processing-expert, and spec-analyst in parallel
- vcodec-chief-standard-expert reviews combined output iteratively (3 mandatory rounds by default, user-adjustable)
- Merge outputs into unified artifacts after chief declares Architecture-Ready
- Validate JSON schemas before declaring gate passed
- **Exhaustive tree exploration is MANDATORY**: Spawn maximum agents in parallel to explore all solution paths.
  Every feasible approach must be investigated and compared before committing. Skip only if user specifies exact algorithm + architecture.
</Execution_Policy>

<Steps>
1. **Requirement clarification and information gathering (BEFORE delegation)**:
   Assess whether the user's request contains enough information. Use `AskUserQuestion` proactively to clarify:
   - Target codec, profile, level (e.g., H.264 High Profile Level 4.1)
   - Target resolution and framerate (e.g., 1080p@60fps, 4K@30fps)
   - Encoder, decoder, or both
   - Interface protocol (AXI4, AXI4-Lite, APB, custom)
   - Clock frequency target and process node (ASIC vs FPGA)
   - Any feature scope restrictions (e.g., "TQ only", "intra-only")
   - Priority trade-off preference (throughput vs area vs power vs quality)

   **Invoke domain-consult for missing domain knowledge**:
   If the user's domain is unfamiliar or specific algorithm characteristics are needed,
   invoke `/rtl-agent-team:domain-consult` to obtain expert knowledge BEFORE proceeding.
   Example: "What encoding tools (intra prediction modes, transform types, entropy coding methods)
   are commonly used for H.264 Baseline Profile? What are their HW implementation characteristics?"

   Skip AskUserQuestion if the user has already provided a detailed spec document or explicit parameters.
   domain-consult should still be invoked even if the spec is complete, to enrich algorithm understanding.

1.5. **Exhaustive Solution Path Tree Exploration (MANDATORY)**:
   Explore ALL feasible solution paths as a tree structure using maximum parallelism.
   Every possible approach must be investigated before committing to a direction.

   **Phase A — Tree Construction (breadth-first discovery)**:
   - spec-analyst + vcodec-chief-standard-expert collaborate to identify the solution space:
     - **Level 1 (Scope)**: Full system vs subsystem options (e.g., full decoder, encoder, intra-only, TQ block)
     - **Level 2 (Architecture)**: Per scope, architectural variants (e.g., sequential vs pipelined vs parallel)
     - **Level 3 (Algorithm)**: Per architecture, algorithm choices (e.g., diamond search vs full search vs TZ search)
   - Output: Solution tree with all leaf nodes identified (target: 8-20 leaf candidates)

   **Phase B — Parallel Deep Dive (maximum agent spawn)**:
   Spawn one dedicated research agent per leaf node, ALL running in parallel:
   ```
   For EACH leaf candidate, spawn an Agent(subagent_type="general-purpose", model="sonnet"):
     - Study: algorithm complexity (O-notation, operation counts per pixel/block)
     - Study: memory bandwidth requirements (bytes/pixel, access patterns, line buffer sizes)
     - Study: gate count estimates (from literature or analytical estimation)
     - Study: throughput achievable (pixels/cycle, blocks/cycle at target frequency)
     - Study: power characteristics (switching activity, clock gating opportunities)
     - Study: implementation risk (tool support, verification complexity, proven vs novel)
     - Study: quality impact (PSNR, BD-rate, visual quality trade-offs)
     - Use WebSearch for academic papers, existing implementations, benchmark data
     - Output: structured assessment JSON per candidate
   ```
   Additionally spawn **cross-cutting research agents** in parallel:
   - **Memory architecture agent**: Survey SRAM vs register file vs external DRAM trade-offs across all candidates
   - **Interconnect agent**: Survey bus topologies (shared bus, crossbar, NoC) for candidate architectures
   - **Power optimization agent**: Survey clock gating, voltage scaling, operand isolation techniques
   - **Reference implementation agent**: Deep-dive into open-source/published implementations (JM, HM, VTM, existing RTL)

   **Phase C — Comparison Matrix Construction**:
   After all agents complete, build a comprehensive comparison:
   ```
   | Candidate | Complexity | Memory BW | Gate Est. | Throughput | Power | Risk | Quality |
   |-----------|-----------|-----------|-----------|------------|-------|------|---------|
   | Path A1   | ...       | ...       | ...       | ...        | ...   | ...  | ...     |
   | Path A2   | ...       | ...       | ...       | ...        | ...   | ...  | ...     |
   | ...       | ...       | ...       | ...       | ...        | ...   | ...  | ...     |
   ```
   - Compute weighted scores based on user's priority (throughput vs area vs power)
   - Identify Pareto-optimal candidates (no candidate dominates another on all axes)
   - Flag high-risk candidates with specific risk descriptions

   **Phase D — Candidate Selection via AskUserQuestion**:
   Present top 3-5 Pareto-optimal candidates to user with:
   - Radar chart description (text-based) showing each candidate's strengths/weaknesses
   - Clear trade-off summary: "Candidate A is 2x faster but 3x larger than Candidate B"
   - Recommendation with justification from literature evidence
   - Use `AskUserQuestion` with detailed option descriptions for final selection
   - User may request deeper investigation of specific candidates → re-spawn agents for targeted deep dive

   **Output artifacts**:
   - `docs/phase-1-research/solution-tree.md` — Full tree with all explored paths
   - `docs/phase-1-research/candidate-comparison.md` — Comparison matrix + Pareto analysis
   - `docs/phase-1-research/selected-approach.md` — Selected candidate with full justification
   - Selected candidate drives the rest of Phase 1 (Step 1.8 domain study + Step 2 sub-domain analysis)

   **Skip condition**: ONLY if user explicitly specifies exact algorithm + architecture
   (e.g., "H.264 baseline profile intra-only decoder with 4-stage pipeline"). Even then, at least
   2 architectural variants should be explored for validation.

1.7. **Load domain knowledge base**: Before sub-domain analysis, ensure agents have access to domain knowledge:
   - Read `domain-packages/video-codec/manifest.json` to identify the active domain package
   - Key knowledge files (auto-loaded by agents via their `<Knowledge_Base>` sections):
     - `domain-packages/video-codec/knowledge/h264-spec-summary.md` — H.264 algorithm summaries
     - `domain-packages/video-codec/knowledge/h265-spec-summary.md` — H.265 algorithm summaries
     - `domain-packages/video-codec/knowledge/fixed-point-conventions.md` — Fixed-point conventions
     - `domain-packages/video-codec/knowledge/throughput-tables.md` — Throughput reference tables
     - `domain-packages/video-codec/knowledge/jm-function-map.md` — JM function-to-spec mapping
   - Agents will read their relevant knowledge files autonomously; no manual passing required

1.8. **Extensive domain study and paper research** (MANDATORY before sub-domain analysis):
   This step conducts broad literature research to inform algorithm selection decisions.
   - **Academic paper survey**: Use `WebSearch` to find recent papers on the target domain:
     - Search queries: "{domain} hardware implementation", "{algorithm} VLSI architecture",
       "{codec} FPGA implementation", "{standard} low-power design"
     - Target venues: IEEE TCAS-I/II, ISSCC, VLSI Symposium, DATE, DAC, ISCAS, JSTSP
     - Collect: architecture choices, throughput/area/power numbers, algorithm modifications for HW
   - **Reference implementation study**: Analyze known reference software implementations:
     - Video codec: JM (H.264), HM (H.265), VTM (H.266) — function structure, algorithm flow
     - Read `domain-packages/video-codec/knowledge/jm-function-map.md` for function-to-spec mapping
     - Identify which software functions map to which HW blocks
   - **Existing HW architecture survey**: Review published HW architectures:
     - Read `domain-packages/video-codec/knowledge/hw-architecture-survey.md`
     - Compare: pipeline depth, parallelism strategy, memory organization, throughput
   - **AskUserQuestion checkpoints**: After literature review, present findings to user:
     - "Based on {N} papers surveyed, the common approaches are {A, B, C}. Which direction fits your constraints?"
     - "Published implementations achieve {X} throughput at {Y} area. Is this within your target range?"
     - "The literature suggests {trade-off}. Do you prefer {option A} or {option B}?"
   - Output: `docs/phase-1-research/literature-survey.md` with:
     - Paper list (title, venue, year, key findings)
     - Architecture comparison table from surveyed implementations
     - Recommended approach with literature justification

2. **Parallel sub-domain survey**: Delegate to 6 agents in parallel:
   - `vcodec-syntax-entropy-expert`: Entropy coding tool survey (CABAC vs CAVLC trade-offs, context model complexity, HW-friendly binarization, known HW data)
   - `vcodec-prediction-expert`: Prediction tool survey (ME search algorithm candidates, sub-pel filter options, mode decision trade-offs, published HW implementations)
   - `vcodec-transform-quant-expert`: Transform/quantization tool survey (DCT/DST butterfly structures, fixed-point precision requirements, RDOQ HW feasibility, gate/throughput data)
   - `vcodec-filter-recon-expert`: Filter tool survey (deblocking decision logic, SAO classification, processing order constraints, filter complexity data)
   - `video-processing-expert`: Signal processing survey (pixel throughput requirements, fixed-point vs floating-point, HW-friendly algorithm modifications)
   - `spec-analyst`: Formal requirement extraction from spec + candidate survey results (requirements.json, io_definition.json)

3. **Chief expert review — Round 1**: Delegate to `vcodec-chief-standard-expert` with all 4 sub-domain outputs.
   Chief reviews for:
   - Cross-block data flow completeness (inputs/outputs defined at every block boundary)
   - Cross-block dependency identification (which block produces/consumes what data)
   - Performance constraint consistency (throughput, latency, bandwidth as specific numbers)
   - Fixed-point constraint completeness (bit widths, rounding modes per block)
   - Cross-block issue identification (e.g., RDOQ↔Entropy dependency, ME↔MC pipeline)
   - [AMBIGUITY]/[CONFLICT] status (all resolved or explicitly promoted to [ARCHITECTURE_DECISION])
   Chief produces feedback with specific improvements per sub-domain expert.

4. **Sub-domain expert improvement**: Re-delegate to specific sub-domain experts with Chief's feedback.
   Only re-run experts that received feedback (not all 4 necessarily).

5. **Chief expert review — Round 2**: Chief re-reviews updated outputs for convergence.
   - Even if convergence appears achieved, proceed to Round 3 (mandatory by default)
   - If NOT converged → repeat Steps 4-5 for Round 3
   - After Round 3 (or user-specified round limit) if still not converged → escalate remaining gaps to user via AskUserQuestion
   - User can override round count: "set iterations to N" → N rounds (minimum 1)

6. **Resolve ambiguities**: Review all expert outputs for remaining `[AMBIGUITY]` and `[CONFLICT]` flags.
   Use `AskUserQuestion` to resolve each one before merging.
   Do not proceed with unresolved ambiguities.

7. Merge results into requirements.json (all functional + non-functional requirements)
   - **Each requirement MUST have a unique ID field `"id": "REQ-NNN"`** (e.g., `"id": "REQ-001"`)
   - IDs are sequential starting from REQ-001
   - Both functional and non-functional requirements receive IDs

8. Self-verification of requirements completeness:
   - Count features/constraints extracted from original spec documents
   - Compare against number of items in requirements.json
   - Generate a **suspected omission list** for any spec features not mapped to a REQ item
   - **Save self-verification result to `reviews/phase-1-research/research-review.md`** in standard review Markdown format:
     ```markdown
     # Phase 1 Review: Research Completeness
     - Date: YYYY-MM-DD
     - Reviewer: spec-analyst
     - Upper Spec: specs/
     - Verdict: PASS | FAIL

     ## Feature Coverage Checklist
     | Spec Section | Requirement ID | Status |
     |-------------|----------------|--------|

     ## Findings
     ### [severity] Finding-N: ...

     ## Verdict
     PASS | FAIL: [reason]
     ```
   - Output verdict:
     ```
     VERDICT: PASS — N requirements extracted, 0 suspected omissions
     ```
     or:
     ```
     VERDICT: REVIEW_NEEDED — N requirements extracted, M suspected omissions
     Suspected omissions:
       - [spec section X.Y.Z] feature description not mapped to any REQ
     ```

9. Produce io_definition.json (all input/output ports with widths, rates, protocols)
   - **Port naming convention (MANDATORY):**
     - Inputs: `i_` prefix (e.g., `i_data`, `i_valid`) — NOT suffix `_i`
     - Outputs: `o_` prefix (e.g., `o_result`, `o_ready`) — NOT suffix `_o`
     - Bidirectional: `io_` prefix (e.g., `io_sda`)
     - Clocks: `clk` (single domain) or `{domain}_clk` (multiple domains, e.g., `sys_clk`) — NOT `clk_i`
     - Resets: `rst_n` (single domain) or `{domain}_rst_n` (multiple domains, e.g., `sys_rst_n`) — NOT `rst_ni`
   - Single clock domain defaults to `sys_clk` / `sys_rst_n`

10. Produce domain-analysis.md — **the primary algorithm/tool candidate survey deliverable**:
    - **Candidate algorithm/tool survey per functional area**: each candidate with
      computational complexity, memory access patterns, quality impact, HW-friendliness, known HW data
    - **Candidate comparison table per functional area** with trade-off summary and recommendation
      (do NOT select a final algorithm — present ranked candidates for user/Phase 2 decision)
    - **Fixed-point precision requirements**: bit widths, rounding modes, dynamic range per algorithm stage
    - **HW implementation data from literature**: gate counts, throughput, power numbers where available
    - Include vcodec-chief-standard-expert's cross-block dependency matrix
    - Include Architecture-Ready assessment summary
    - Known implementation challenges and references

11. Validate all three files exist and JSON is well-formed

12. Validate io_definition.json port names comply with naming conventions above
</Steps>

<Tool_Usage>
```
Bash("mkdir -p reviews/phase-1-research")

# Step 1: domain-consult for domain knowledge acquisition (BEFORE tree exploration)
Skill("rtl-agent-team:domain-consult",
      args="What algorithms/coding tools are available for {target domain}? For each tool, what are the HW implementation characteristics (gate count, throughput, power)? What are the common trade-offs?")

# Step 1.5: Exhaustive Solution Path Tree Exploration (MANDATORY)
# Phase A — Tree construction: identify all feasible paths
Task(subagent_type="rtl-agent-team:spec-analyst",
     prompt="From specs/ and user requirements, construct a solution tree: Level 1 (scope variants), Level 2 (architecture variants per scope), Level 3 (algorithm choices per architecture). Identify ALL leaf candidates (target 8-20). Output structured tree as JSON.")

Task(subagent_type="rtl-agent-team:vcodec-chief-standard-expert",
     prompt="Review the solution tree from spec-analyst. Validate completeness — are any feasible approaches missing? Add any overlooked branches. Finalize the tree for parallel exploration.")

# Phase B — Parallel deep dive: spawn ONE agent per leaf candidate (ALL in parallel)
# Each agent gets a dedicated research mission. Use run_in_background=true for all.
Task(subagent_type="general-purpose", model="sonnet", run_in_background=true,
     prompt="Deep-dive research for candidate: [Leaf 1]. Study: algorithm complexity (O-notation), memory BW (bytes/pixel), gate count estimate, achievable throughput (pixels/cycle), power characteristics, implementation risk, quality impact. Use WebSearch for papers. Output structured JSON assessment.")
Task(subagent_type="general-purpose", model="sonnet", run_in_background=true,
     prompt="Deep-dive research for candidate: [Leaf 2]. Study: algorithm complexity, memory BW, gate count, throughput, power, risk, quality. Use WebSearch for papers. Output structured JSON assessment.")
# ... spawn one Task per leaf node (8-20 agents in parallel)

# Phase B — Cross-cutting research agents (also in parallel with leaf agents)
Task(subagent_type="general-purpose", model="sonnet", run_in_background=true,
     prompt="Memory architecture survey: compare SRAM vs register file vs external DRAM trade-offs for the target design domain. Include line buffer sizing, bandwidth calculations, multi-port vs banking strategies. Use WebSearch for published implementations.")
Task(subagent_type="general-purpose", model="sonnet", run_in_background=true,
     prompt="Interconnect topology survey: compare shared bus, crossbar, ring, NoC for on-chip data movement in the target domain. Include latency, area overhead, scalability analysis. Use WebSearch for papers.")
Task(subagent_type="general-purpose", model="sonnet", run_in_background=true,
     prompt="Power optimization survey: clock gating effectiveness, voltage scaling, operand isolation, power domain strategies for the target design domain. Use WebSearch for low-power implementation papers.")
Task(subagent_type="general-purpose", model="sonnet", run_in_background=true,
     prompt="Reference implementation deep-dive: analyze open-source and published HW implementations. Extract architecture decisions, pipeline structures, resource utilization. Sources: GitHub RTL repos, IEEE papers, FPGA implementation reports.")

# Phase C — Comparison matrix: chief builds unified comparison after all agents complete
Task(subagent_type="rtl-agent-team:vcodec-chief-standard-expert",
     prompt="Build comparison matrix from all leaf candidate assessments + cross-cutting research. Columns: Complexity, Memory BW, Gate Est., Throughput, Power, Risk, Quality. Compute weighted scores. Identify Pareto-optimal candidates. Write docs/phase-1-research/candidate-comparison.md")

# Phase D — AskUserQuestion: present top 3-5 Pareto-optimal candidates to user
# Use AskUserQuestion with detailed trade-off descriptions for final selection
# Selected candidate drives Step 1.8 domain study + Step 2 sub-domain analysis

# Step 2: Parallel sub-domain analysis (6 agents)
Task(subagent_type="rtl-agent-team:vcodec-syntax-entropy-expert",
     prompt="Extract HLS and entropy coding requirements from spec at specs/. Cover NAL parsing, CABAC/CAVLC context models, DPB management. Output structured algorithm descriptions with standard clause citations.")

Task(subagent_type="rtl-agent-team:vcodec-prediction-expert",
     prompt="Extract intra and inter prediction requirements from spec at specs/. Cover all prediction modes, sub-pixel interpolation filters, MV prediction. Output structured algorithm descriptions with standard clause citations.")

Task(subagent_type="rtl-agent-team:vcodec-transform-quant-expert",
     prompt="Extract transform and quantization requirements from spec at specs/. Cover DCT/DST, quantization tables, RDOQ, fixed-point precision chain. Output structured algorithm descriptions with standard clause citations.")

Task(subagent_type="rtl-agent-team:vcodec-filter-recon-expert",
     prompt="Extract in-loop filter and reconstruction requirements from spec at specs/. Cover deblocking, SAO, reconstruction path, processing order. Output structured algorithm descriptions with standard clause citations.")

Task(subagent_type="rtl-agent-team:video-processing-expert",
     prompt="Extract signal processing and datapath requirements from specs/.")

Task(subagent_type="rtl-agent-team:spec-analyst",
     prompt="Parse specs/ and produce requirements.json and io_definition.json. Each requirement in requirements.json MUST have a unique 'id' field: 'REQ-001', 'REQ-002', etc. Port names in io_definition.json MUST use: i_/o_/io_ prefix (NOT suffix _i/_o), clocks as {domain}_clk (e.g. sys_clk), resets as {domain}_rst_n (e.g. sys_rst_n). After generation, count features in original spec vs REQ items and list any suspected omissions. Save the self-verification review to reviews/phase-1-research/research-review.md in standard review Markdown format with Date, Reviewer, Upper Spec, Verdict, Feature Coverage Checklist, Findings, and final Verdict sections.")

# Step 3: Chief expert review (after all sub-domain outputs are available)
Task(subagent_type="rtl-agent-team:vcodec-chief-standard-expert",
     prompt="Review the combined outputs from vcodec-syntax-entropy-expert, vcodec-prediction-expert, vcodec-transform-quant-expert, and vcodec-filter-recon-expert. Evaluate against Architecture-Ready criteria: (1) data flow completeness, (2) cross-block dependencies, (3) performance constraints, (4) fixed-point constraints, (5) cross-block issues, (6) zero unresolved ambiguities. Produce feedback per expert and convergence assessment. This is Round 1 of 3 mandatory rounds.")

# Step 4-5: Iterative improvement (repeat as needed, max 3 rounds)
# Re-delegate to specific experts with Chief's feedback, then re-run Chief review

# Write: reviews/phase-1-research/research-review.md
```
</Tool_Usage>

<Examples>
<Good>
Input: H.264 spec PDF + system constraints doc
Output: requirements.json with 47 functional requirements, io_definition.json with all AXI ports (using i_/o_ prefix, sys_clk/sys_rst_n naming), domain-analysis.md with cross-block dependency matrix and CABAC algorithm notes.
Example io_definition.json port: `{"name": "i_axi_awaddr", "direction": "input", "width": 32, "protocol": "AXI4-Lite"}`
Chief expert review: 3 mandatory rounds to Architecture-Ready. Round 1 identified missing MC output bit width; vcodec-prediction-expert updated. Round 2-3 confirmed convergence.
Tree exploration: spec-analyst identified 3 paths (full H.264 decoder, intra-only decoder, TQ subsystem).
3 parallel research agents explored each. Chief ranked: TQ subsystem (lowest risk, fastest delivery).
User selected TQ subsystem via AskUserQuestion. Sub-domain analysis (Step 2) scoped to TQ only.
</Good>
<Bad>
Skipping vcodec-chief-standard-expert review and merging sub-domain outputs directly — misses cross-block dependency issues.
Running only 1 sub-domain expert instead of all 4 — incomplete domain coverage.
Skipping spec-analyst and writing requirements.json manually — misses formal traceability.
</Bad>
</Examples>

<Escalation_And_Stop_Conditions>
- Spec document not found → report to user, halt
- Conflicting requirements between experts → flag conflict in domain-analysis.md, ask user to resolve
- Chief expert not converged after 3 mandatory rounds (or user-specified limit) → escalate remaining gaps to user with specific questions
- Sub-domain expert returns [DOMAIN_UNCERTAINTY] that requires user input → AskUserQuestion before proceeding
</Escalation_And_Stop_Conditions>

<Final_Checklist>
- [ ] requirements.json exists and is valid JSON
- [ ] Every requirement in requirements.json has a unique `"id": "REQ-NNN"` field
- [ ] io_definition.json exists and is valid JSON
- [ ] io_definition.json port names use `i_`/`o_`/`io_` prefix (NOT suffix `_i`/`_o`)
- [ ] io_definition.json clocks use `{domain}_clk` (e.g., `sys_clk`) — bare `clk` OK for single domain, `{domain}_clk` for multiple domains. NOT `clk_i`
- [ ] io_definition.json resets use `{domain}_rst_n` (e.g., `sys_rst_n`) — bare `rst_n` OK for single domain, `{domain}_rst_n` for multiple domains. NOT `rst_ni`
- [ ] domain-analysis.md exists and includes cross-block dependency matrix
- [ ] No unresolved requirement conflicts
- [ ] vcodec-chief-standard-expert declared Architecture-Ready (or gaps escalated to user after 3 mandatory rounds)
- [ ] Self-verification verdict produced (PASS or REVIEW_NEEDED with suspected omissions)
- [ ] Spec feature count vs requirements.json item count comparison documented
- [ ] **reviews/phase-1-research/research-review.md saved with self-verification result**
- [ ] **docs/phase-1-research/solution-tree.md exists** with full tree of explored paths
- [ ] **docs/phase-1-research/candidate-comparison.md exists** with comparison matrix + Pareto analysis
- [ ] **docs/phase-1-research/selected-approach.md exists** with selected candidate + justification
- [ ] Tree exploration used maximum parallel agents (8-20 leaf agents + 4 cross-cutting agents)
- [ ] **docs/phase-1-research/literature-survey.md exists** with paper list, architecture comparison, recommended approach
- [ ] domain-consult invoked at least once to acquire domain expert knowledge
- [ ] Algorithm/tool candidates presented with trade-offs (NOT pre-selected — user decides)
- [ ] AskUserQuestion used at every ambiguity point (no unresolved assumptions)
</Final_Checklist>

<Advanced>
If spec is in multiple formats (PDF + XML + prose), run separate extraction per format then merge.
Traceability: each requirement in requirements.json must have a spec section reference.
Chief expert review rounds: Round 1 typically identifies 5-10 cross-block issues. Round 2 resolves
most. Round 3 is needed only for complex multi-standard targets (e.g., H.264+H.265 dual codec).
</Advanced>
