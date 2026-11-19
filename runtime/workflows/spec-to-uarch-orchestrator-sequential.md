Run the requested P1 -> P2 -> P3 design sequence and stop before RTL coding for
the user's design review. Delegate each phase through its Action Skill. Use the
same shared phase orchestrator in sequential or explicitly requested team mode;
do not create nested teams while a parent team owns the workers.

Resume from .rat/state/rat-p1p3-spec-uarch-state.json and existing artifacts.
Preserve completed phases when their upstream inputs and evidence are current.
Record current_phase, status, completed items, pending material choices and paths
to the actual gate results. Migrate legacy state without treating an old review
round count as work to repeat. Check executable artifact gates at each handoff,
including runnable refc and the bandwidth_report.json at P2, and G4a/G4b/G4c BFM
measurements at P3. Gate PASS alone does not establish model correctness.

Honor upstream authority P1 > P2 > P3. Report contradictions and ask once when a
user decision is needed. A measured failure authorizes a local repair and affected
rerun, with at most two failed repairs before escalation. Do not add candidate
exploration, review rounds or Codex cross-review after an already settled result.
Produce phase summaries, significant ADRs and compliance evidence, then report
remaining limitations and the explicit stop before P4.
