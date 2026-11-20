# Native subagent dispatch

Use the host running the skill (`claude`, `codex`, `agy`, or `grok`). For a named
RAT delegate, resolve its default from the installed plugin:

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

On hosts without a registered RAT role, read `agents/<agent>.md` from the
plugin and pass its instructions to a native worker with the resolved model.
Use the role's YAML `model` as its Claude default. If a registered role would
pin that alias on another host, give the role body to a generic native worker.
If the host has no worker facility, execute that role in the current session.
For a direct skill invocation, load `skills/<skill>/SKILL.md` from the plugin
and resolve relative references there.
