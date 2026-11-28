# Native subagent dispatch

Claude Code is the reference host for RAT roles, phase handoffs and verification
requirements. On Claude Code, Codex, Antigravity CLI and Grok, use the corresponding
host ID (`claude`, `codex`, `agy`, `grok`) to resolve a named delegate's model:

```sh
python3 "$plugin_root/scripts/resolve_agent_model.py" --host "$host" --agent "$agent"
```

An explicit native model takes precedence via `--model`. A bare Codex family
name resolves to a full catalog ID. Otherwise select the tier from the actual
task. Use `--tier complex|design|straightforward|trivial` in place of
`--agent` when the task differs from the role default, in either direction.
For example, an architect extracting a known report field uses the trivial
tier. Reuse results for the same host and tier in the session.

| Work | Tier | Claude | Codex family | agy preference | Grok preference |
| --- | --- | --- | --- | --- | --- |
| Architecture, orchestration, difficult judgments | complex | fable | astra | Gemini Orchestrator or planning model | native default |
| Design, implementation, verification | design | opus | sol | Gemini planning model | native default |
| Straightforward tool execution and reporting | straightforward | sonnet | terra | Hydrogen or Flash | fast |
| Mechanical extraction or formatting | trivial | haiku | luna | Flash or Hydrogen | fast |

Supply the result to the host's native delegation tool if it accepts a model.
An empty result or missing override capability inherits the session model. If a
user-selected model is rejected, report that choice to the user. For an
automatically selected unavailable Claude Fable role, fall back to Opus once.
If an automatic catalog selection is rejected, inherit the native session.
Leave reasoning effort under host control.

On a different host, including Gemini CLI, use its active session model. Skip
the resolver and use the role-body fallback below. Pass the absolute plugin and
project paths to the worker so it can find bundled resources from the RTL project.

On hosts without a registered RAT role, read `agents/<agent>.md` from the
plugin (`runtime/roles/<agent>.md` in the portable skills export) and pass
its instructions to a native worker with the resolved model.
Use the role's YAML `model` as its Claude default. If a registered role would
pin that alias on another host, give the role body to a generic native worker.
If the host has no worker facility, execute that role in the current session.
For a delegation-only action skill, switch to the named role's instructions
for the task and return its normal artifact and evidence handoff.
For a direct skill invocation, load `skills/<skill>/SKILL.md` from the plugin
and resolve relative references there.

When delegating EDA work on hosts without session hooks, give workers the
project root and a distinct `RAT_EXPERIMENT_ID` per parallel experiment. The
bundled runner reads effective settings before project initialization. Run
the project's functional regression after behavioral RTL changes and carry
the measured verdict into the phase handoff. A failed run keeps the affected
case open until a matching rerun passes or the user grants a waiver.
See [EDA execution](eda-runner-contract.md).
