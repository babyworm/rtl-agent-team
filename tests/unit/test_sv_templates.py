"""Static checks on the bundled SystemVerilog templates.

CI has no EDA tools, so these reproduce — with plain regex — the two defect
classes that Verilator and slang caught in the shipped templates:

- v0.14.2: ``systemverilog/templates/module-template.sv`` declared
  ``localparam L_DEPTH`` (derived from an otherwise-unused ``ADDR_WIDTH``) and
  never referenced it. Verilator ``-Wall`` reports UNUSEDPARAM and exits
  non-zero, and ``rtl-coder`` runs exactly that lint after every write — so the
  canonical module scaffold failed its own first lint.
- v0.14.2: ``rtl-p5s-sva-check/templates/sva-property-template.sv`` used
  ``DATA_WIDTH`` in two port ranges without declaring it. slang reported 2
  errors; the module could not elaborate at all.
"""

import re
import subprocess
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT, SKILLS_DIR

SV_TEMPLATES = sorted(SKILLS_DIR.glob("*/templates/*.sv"))
CHECK_CONVENTIONS = SKILLS_DIR / "rtl-lint-check" / "scripts" / "check_conventions.sh"

_SUBST = {
    "{{MODULE_NAME_UPPER}}": "MY_MODULE",
    "{{MODULE_NAME}}": "my_module",
    "{{MODULE}}": "my_module",
    "{{DOMAIN}}": "sys",
    "{{TOP_NAME}}": "my_top",
    "{{IP_SHORT_NAME}}": "ip",
    "{{IP_NAME}}": "my_ip",
    "{{WRAPPER_NAME}}": "my_ip_wrapper",
    "{{DATA_WIDTH}}": "32",
    "{{BUG_ID}}": "BUG_042",
    "{{FAIL_CYCLE}}": "250",
    "{{SYMPTOM}}": "symptom",
    "{{BRIEF_DESCRIPTION}}": "brief",
    "{{PROTO}}": "axi",
}


def _render(path: Path) -> str:
    text = path.read_text()
    for key, value in _SUBST.items():
        text = text.replace(key, value)
    return text


def _strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"//[^\n]*", " ", text)


def test_templates_exist():
    assert len(SV_TEMPLATES) >= 10, f"Expected ≥10 SV templates, got {len(SV_TEMPLATES)}"


@pytest.mark.parametrize("template", SV_TEMPLATES, ids=lambda p: p.name)
def test_every_localparam_is_referenced(template):
    """An unreferenced localparam fails Verilator -Wall (UNUSEDPARAM)."""
    body = _strip_comments(_render(template))
    unused = []
    for match in re.finditer(r"\blocalparam\b[^;=]*?\b([A-Za-z_]\w*)\s*=", body):
        name = match.group(1)
        # one occurrence is the declaration itself
        if len(re.findall(rf"\b{re.escape(name)}\b", body)) < 2:
            unused.append(name)
    assert unused == [], (
        f"{template.name}: localparam(s) declared but never used {unused} — "
        "Verilator -Wall reports UNUSEDPARAM and exits non-zero"
    )


@pytest.mark.parametrize("template", SV_TEMPLATES, ids=lambda p: p.name)
def test_widths_used_in_port_ranges_are_declared(template):
    """A width identifier used in a port range must be declared in the file."""
    body = _strip_comments(_render(template))
    declared = set(re.findall(r"\b(?:parameter|localparam)\b[^;=]*?\b([A-Za-z_]\w*)\s*=", body))
    declared |= set(re.findall(r"\b(?:typedef|import)\b[^;]*?\b([A-Za-z_]\w*)", body))
    undeclared = set()
    for expr in re.findall(r"\[([^\]]*?)\s*-\s*1\s*:\s*0\]", body):
        # drop system functions ($clog2, $bits, ...) before harvesting identifiers
        expr = re.sub(r"\$\w+", " ", expr)
        for ident in re.findall(r"\b([A-Za-z_]\w*)\b", expr):
            if ident not in declared:
                undeclared.add(ident)
    assert undeclared == set(), (
        f"{template.name}: port/signal range uses undeclared width(s) "
        f"{sorted(undeclared)} — the module cannot elaborate"
    )


def test_templates_pass_the_plugin_convention_checker(tmp_path):
    """check_conventions.sh is pure bash, so it runs in CI without EDA tools."""
    for template in SV_TEMPLATES:
        (tmp_path / template.name).write_text(_render(template))
    result = subprocess.run(
        ["bash", str(CHECK_CONVENTIONS), str(tmp_path)],
        capture_output=True, text=True, check=False, cwd=REPO_ROOT,
    )
    assert result.returncode == 0, (
        "Bundled SV templates violate the plugin's own conventions:\n" + result.stdout
    )


def test_uvm_clocking_block_waits_do_not_attach_iff_to_clocking_items():
    """IEEE-compatible waits sample the clocking block before testing signals."""
    template = SKILLS_DIR / "rtl-p5s-uvm-verify" / "templates" / "uvm-agent-template.sv"
    body = _render(template)
    forbidden = re.findall(r"@\(vif\.(?:drv_cb|mon_cb)\s+iff\b", body)
    assert forbidden == [], (
        "Slang rejects `@(clocking_item iff condition)`; wait on the clocking "
        "item first and test the sampled signal in a loop"
    )
