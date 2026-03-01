---
name: research-analyze
description: "This skill should be used when analyzing algorithms, selecting optimal approaches, and extracting structured requirements from raw specifications in Phase 1. Produces domain-analysis.md (algorithm trade-offs), requirements.json, and io_definition.json."
---

<Purpose>
Research, analyze, and select the optimal algorithms and implementation approaches for the target design.
Phase 1 has two equally important outputs:

1. **Algorithm analysis and selection** (domain-analysis.md) — the PRIMARY creative output:
   - Compare candidate algorithms for each functional block (e.g., diamond search vs full search for ME)
   - Analyze trade-offs: computational complexity, memory access patterns, quality impact, HW-friendliness
   - Select and justify the optimal algorithm for each functional area given the design constraints
   - Identify fixed-point precision requirements and HW-friendly algorithm modifications

2. **Structured requirement extraction** (requirements.json, io_definition.json):
   - Transform the selected algorithms and spec constraints into structured, traceable requirements
   - Define the system I/O boundary

Domain experts drive algorithm analysis; spec-analyst captures the results as structured artifacts.
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
Separating this from arch-design prevents spec ambiguity from corrupting structural decisions.

The research phase uses 4 sub-domain codec experts (vcodec-syntax-entropy, vcodec-prediction,
vcodec-transform-quant, vcodec-filter-recon) coordinated by a vcodec-chief-standard-expert who
iteratively reviews their combined output until it reaches Architecture-ready quality (3 mandatory
rounds by default). This ensures cross-block dependencies are identified and resolved before Phase 2.
</Why_This_Exists>

<Execution_Policy>
- Run sub-domain experts (vcodec-syntax-entropy, vcodec-prediction, vcodec-transform-quant, vcodec-filter-recon),
  video-processing-expert, and spec-analyst in parallel
- vcodec-chief-standard-expert reviews combined output iteratively (3 mandatory rounds by default, user-adjustable)
- Merge outputs into unified artifacts after chief declares Architecture-Ready
- Validate JSON schemas before declaring gate passed
- (Optional) Tree-based solution path exploration before sub-domain analysis — skipped when user provides explicit scope
</Execution_Policy>

<Steps>
1. **Requirement clarification (BEFORE delegation)**: Assess whether the user's request contains enough information to produce complete requirements. Use `AskUserQuestion` proactively to clarify:
   - Target codec, profile, level (e.g., H.264 High Profile Level 4.1)
   - Target resolution and framerate (e.g., 1080p@60fps, 4K@30fps)
   - Encoder, decoder, or both
   - Interface protocol (AXI4, AXI4-Lite, APB, custom)
   - Clock frequency target and process node (ASIC vs FPGA)
   - Any feature scope restrictions (e.g., "TQ only", "intra-only")
   Skip this step if the user has already provided a detailed spec document or explicit parameters.

1.5. **Solution Path Exploration (optional tree-based)**:
   Before committing to a single design scope, explore multiple feasible design paths in parallel.
   - spec-analyst identifies 2-4 feasible design paths from the user's requirements
     (e.g., full decoder vs intra-only decoder vs specific subsystem like TQ block)
   - Each path is delegated to a separate research agent in parallel (Task with model=sonnet)
   - Each agent studies: feasibility, complexity estimate (gate count range), risk factors, resource requirements
   - Results collected and presented to vcodec-chief-standard-expert
   - Chief ranks paths by optimality (complexity vs risk vs value)
   - AskUserQuestion presents top-ranked paths for user selection with trade-off summary
   - Selected path drives the rest of Phase 1 sub-domain analysis (Step 2 onward)
   - **Skip condition**: If the user already specified exact scope (e.g., "H.264 TQ block only"),
     skip tree exploration entirely and proceed directly to Step 2

1.7. **Load domain knowledge base**: Before sub-domain analysis, ensure agents have access to domain knowledge:
   - Read `domain-packages/video-codec/manifest.json` to identify the active domain package
   - Key knowledge files (auto-loaded by agents via their `<Knowledge_Base>` sections):
     - `domain-packages/video-codec/knowledge/h264-spec-summary.md` — H.264 algorithm summaries
     - `domain-packages/video-codec/knowledge/h265-spec-summary.md` — H.265 algorithm summaries
     - `domain-packages/video-codec/knowledge/fixed-point-conventions.md` — Fixed-point conventions
     - `domain-packages/video-codec/knowledge/throughput-tables.md` — Throughput reference tables
     - `domain-packages/video-codec/knowledge/jm-function-map.md` — JM function-to-spec mapping
   - Agents will read their relevant knowledge files autonomously; no manual passing required

2. **Parallel sub-domain analysis**: Delegate to 6 agents in parallel:
   - `vcodec-syntax-entropy-expert`: Entropy coding algorithm analysis (CABAC vs CAVLC trade-offs, context model complexity, HW-friendly binarization)
   - `vcodec-prediction-expert`: Prediction algorithm analysis (ME search algorithms comparison, sub-pel filter complexity, mode decision trade-offs)
   - `vcodec-transform-quant-expert`: Transform/quantization algorithm analysis (DCT/DST butterfly structures, fixed-point precision chain, RDOQ HW feasibility)
   - `vcodec-filter-recon-expert`: Filter algorithm analysis (deblocking decision logic, SAO classification, processing order constraints)
   - `video-processing-expert`: Signal processing algorithm analysis (pixel throughput, fixed-point vs floating-point, HW-friendly modifications)
   - `spec-analyst`: Formal requirement extraction from spec + algorithm selections (requirements.json, io_definition.json)

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

10. Produce domain-analysis.md — **the primary algorithm analysis deliverable**:
    - **Algorithm trade-off analysis per functional area**: candidate algorithms compared on
      computational complexity, memory access patterns, quality impact, HW-friendliness
    - **Selected algorithm per block** with justification against design constraints (area, power, throughput)
    - **Fixed-point precision chain**: bit widths, rounding modes, dynamic range per algorithm stage
    - **HW-friendly algorithm modifications**: standard algorithm adaptations for efficient RTL implementation
    - Include vcodec-chief-standard-expert's cross-block dependency matrix
    - Include Architecture-Ready assessment summary
    - Known implementation challenges and references

11. Validate all three files exist and JSON is well-formed

12. Validate io_definition.json port names comply with naming conventions above
</Steps>

<Tool_Usage>
```
Bash("mkdir -p reviews/phase-1-research")

# Step 1.5: Solution Path Exploration (optional — skip if user specified exact scope)
# spec-analyst identifies feasible design paths, then parallel research agents explore each
Task(subagent_type="rtl-agent-team:spec-analyst",
     model="sonnet",
     prompt="From the user's requirements and specs/, identify 2-4 feasible design paths (e.g., full decoder, intra-only, specific subsystem). For each path, describe: scope, estimated complexity, key risks. Output a ranked list.")

# Parallel path exploration (one agent per path, model=sonnet for cost efficiency)
Task(subagent_type="rtl-agent-team:vcodec-architecture-expert",
     model="sonnet",
     prompt="Explore design path: [path 1 description]. Assess: feasibility, gate count estimate, risk factors, resource requirements, timeline impact. Output structured assessment.",
     run_in_background=true)
Task(subagent_type="rtl-agent-team:vcodec-architecture-expert",
     model="sonnet",
     prompt="Explore design path: [path 2 description]. Assess: feasibility, gate count estimate, risk factors, resource requirements, timeline impact. Output structured assessment.",
     run_in_background=true)
# ... one Task per identified path

# Chief ranks paths after all exploration agents complete
Task(subagent_type="rtl-agent-team:vcodec-chief-standard-expert",
     prompt="Review the exploration results for all design paths. Rank by optimality: complexity vs risk vs value. Recommend the top path with justification. Present trade-offs for AskUserQuestion.")

# AskUserQuestion: present top paths to user for selection
# Selected path drives Step 2 onward

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
- [ ] Solution path selected (or explicit scope given by user — tree exploration skipped)
</Final_Checklist>

<Advanced>
If spec is in multiple formats (PDF + XML + prose), run separate extraction per format then merge.
Traceability: each requirement in requirements.json must have a spec section reference.
Chief expert review rounds: Round 1 typically identifies 5-10 cross-block issues. Round 2 resolves
most. Round 3 is needed only for complex multi-standard targets (e.g., H.264+H.265 dual codec).
</Advanced>
