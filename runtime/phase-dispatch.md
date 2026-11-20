# Optional Codex cross-review

At a phase handoff, the phase owner runs one independent Codex review of the
completed deliverables when enabled. A direct request for the review skill
counts as opt-in. For a phased run:

- Forward the user's review choice and scope to each applicable child. “Auto design
  with Codex cross-review” covers all phases in that run. “Review P3 only” selects
  P3 and skips the other phases. An explicit skip overrides the project default.
- Store `review_scope` as `project`, `on`, `off`, or a comma-separated list of
  phase IDs such as `2,3`. For split verification, `5` includes `5a` and `5b`.
  With no run override, use the project-root `rat_config.json` boolean
  `review.codex_cross_review`. Missing means false. To check the effective
  decision, run `python3 {plugin_root}/skills/codex-cross-review/scripts/review.py enabled --root <project> --phase <id> --choice <review_scope>`. Pass the same scope to the reviewer.
- The phase owner invokes `codex-cross-review` once, after ordinary gate
  evidence is available. Pass the phase and artifact paths. In team mode the
  coordinator can hand this action to the leader if only the leader can invoke
  it. The pipeline parent consumes the result; it does not start another review.
- Keep a run-specific choice and the phase review result with the existing
  pipeline resume state. Reuse a completed review on unchanged inputs. End the
  override with this run. If a requested review could not run, report it as
  incomplete with the reason. A reviewer verdict never replaces measured gates.
