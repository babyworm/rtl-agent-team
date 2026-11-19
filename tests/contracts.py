"""Read distributed prompt contracts, including explicitly loadable mode resources.

Structural tests inspect all delivered modes. Runtime prompt tests separately check
that only the selected mode is loaded. This helper never patches pathlib or tools.
"""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def read_contract(path, **kwargs):
    path=Path(path)
    if path.name=='SKILL.md' and not path.is_file():
        policy=ROOT/'plugin_docs/agent-lib/policies'/(path.parent.name+'.md')
        if policy.is_file():return policy.read_text(**kwargs)
    text=path.read_text(**kwargs)
    if path.parent==ROOT/'agents':
        for mode in ('sequential','team'):
            workflow=ROOT/'runtime/workflows'/(path.stem+'-'+mode+'.md')
            if workflow.is_file():text+='\n\n'+workflow.read_text(**kwargs)
    return text


def accepted_skill_input(payload):
    import json
    value=json.loads(payload) if isinstance(payload,str) else dict(payload)
    value.setdefault('hook_event_name','PostToolUse')
    return value
