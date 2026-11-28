# v1.0.0 evaluation

## RTL edit and verification

The `unit-mismatch` fixture changes a four-bit incrementer from adding one to
adding two. Its unit bench expects five for input four. The same file list
includes an unrelated smoke bench that would end the simulation before that
check if the simulator selected both tops.

Run the deterministic check with Python 3.9+, Icarus Verilog and `vvp`:

```sh
python3 evals/runtime/check_host_verification.py
```

This replays Claude `Edit` and Codex `apply_patch` events in separate temporary
projects. It checks the actual simulator log, evidence record, pending RTL file
and Stop hook decision. It uses the project's installed runner in both cases.

To exercise skill selection and the tools used by a real Claude Code session,
run the native case from the plugin root:

```sh
claude plugin eval . --case unit-mismatch --ablation none --scaffold \
  --allow-tools Bash Edit Write --trust-plugin --no-publish \
  --output-dir "$(mktemp -d)"
```

The graders check the unit-test skill call, the selected top, the measured
mismatch, the failed verdict and the pending verification state. The native
case needs an authenticated Claude Code session and an available shell sandbox.
The installed marketplace copy can be selected by passing
`rtl-agent-team@rtl-agent-marketplace` as the target. [Claude Code plugin evals](https://code.claude.com/docs/en/plugin-evals)

To replay the same case in another host, create a disposable project from the
checkout and start the host with RAT enabled in that project:

```sh
rat_checkout="$(pwd -P)"
rat_fixture="$(mktemp -d)"
(cd "$rat_fixture" && bash "$rat_checkout/evals/unit-mismatch/scaffold.sh")
cd "$rat_fixture"
```

Give the host the `execution.prompt` from `evals/unit-mismatch/case.yaml`.
Check the invoked skill or role, the requested top in the evidence record, and
`REQ-U-001 expected=5 actual=6` in the runtime log. The handoff must report
failed verification. In a host with RAT edit and Stop hooks also check that
`rtl/incrementer.sv` remains pending. Skills-only exports report the failed
handoff through the runner and do not install lifecycle hooks.

## Prompt judgments and template checks

Run one assessment per fixed fixture and model, with no response retries:

```sh
python3 scripts/eval_prompts.py --suite judgment --variant both --models gpt-6.1-sol --output /tmp/rat-judgment
python3 scripts/eval_prompts.py --suite routing --variant both --models gpt-6.1-sol --output /tmp/rat-routing
python3 evals/runtime/check_verilator_templates.py
```

The judgment fixtures cover settled requirements, contradictory requirements,
measured mismatch, and an undefined verification oracle. Routing covers English,
Korean, refusing fabricated functional PASS, and preserving an unresolved oracle.
Baseline prompts are loaded from git `0db2ba5`; current prompts include the selected
sequential workflow and generated policy, not only the short agent entry file.

Claude requests use tools/hooks disabled and a per-case budget (default $0.50).
Codex uses ephemeral read-only sessions with the session's default effort.
Provider usage limits are unavailability, not a model behavior failure. Do not retry
quota errors across every remaining case. Source text and raw CLI results belong
in the specified local output directory; the repository stores sanitized results.

[Measured results](results/2026-11-17-sol.json) preserve the raw assessment fields.
Both baseline and current pass 4/4 judgment and 4/4 routing checks after semantic
normalization of qualified routes. Confidence concerns can differ: confidence in
identifying a contradiction does not establish confidence in a design choice.
The grader checks that contradiction remains open; it does not demand the label low.
A conditional rerun after clarification is not a request to invent another review.
These grader corrections were applied equally to existing baseline/current outputs.

The four judgment prompts total 140035 -> 73084 UTF-8 bytes (47.8% less). This is
prompt-size evidence, not a measured reduction in billed tokens or elapsed time.
The sample is small and does not establish general design quality or confidence
calibration. Fable/Opus live evaluation was unavailable at the account weekly limit.
No result is reported for them.

The [Verilator 5.032 results](results/2026-11-17-verilator.json) record 8/8 passing
checks of two actual templates on PASS, mismatch, zero checks, and cycle timeout.
They test template/runner verdict behavior, not a complete codec design.
Transport and commercial tool contracts use controlled, synthetic fixtures.
Real site profiles, SSH connection settings, probe logs and qualification reports
are private user data stored outside this repository. No identifying site result
is published here; setup smoke evidence does not verify a user's design.

CI runs the template harness on PRs, tag pushes and manual runs. It retains
synthetic logs and verdicts for reproduction. The same job runs 6,000 generated
simulation log cases across three fixed seeds. A failed case reports its seed,
index and log, so repairs can be checked without rerunning model reviews.
