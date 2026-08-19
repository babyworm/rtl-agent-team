"""Pin the EDA tool command lines to the shapes each vendor documents.

These runners are the only place the plugin touches a real EDA tool, and a wrong
switch does not degrade gracefully — it either fails to launch or hangs a
headless CI. None of these tools can be installed in CI, so the invocations are
verified structurally here instead.

v0.14.3 corrected five of them:
  - `vc_cdc` is the Synopsys *app* name; the executable is `vc_static_shell`, so
    the VC CDC path could never launch.
  - Conformal was invoked with Synopsys' `-64bit` spelling and no `-nogui`, so a
    headless run would try to open the GUI. Cadence spells it `-64` and documents
    the batch form as `lec -dofile <file> -nogui`.
  - Genus was missing `-batch`, leaving an interactive shell alive after the
    script, and carried the RTL-Compiler-era `-64` that newer releases reject.
  - Questa CDC was missing `-od`, so the session database and the runner's report
    directory disagreed.
  - Xcelium jumped from `-compile` straight to `-R`. `-compile` writes no
    snapshot and `-R` opens an existing one, so `-elaborate` was required in
    between.
"""

import re
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT

TEMPLATES = REPO_ROOT / "skills" / "rat-init-project" / "templates"
RUN_SIM = REPO_ROOT / "scripts" / "run_sim.sh"
RUN_SYN = TEMPLATES / "run_syn.sh"
RUN_CDC = TEMPLATES / "run_cdc.sh"
RUN_CONFORMAL = TEMPLATES / "run_conformal.sh"
RUN_FORMALITY = TEMPLATES / "run_formality.sh"


def _body(path: Path) -> str:
    """Script text with comment-only lines removed, so prose cannot satisfy a check."""
    return "\n".join(
        line for line in path.read_text().splitlines() if not line.lstrip().startswith("#")
    )


# (path, must-contain, must-not-contain, why)
CONTRACTS = [
    (RUN_CONFORMAL, "lec -nogui -dofile", "lec -64bit",
     "Cadence documents `lec -dofile <file> -nogui`; -64bit is the Synopsys spelling"),
    (RUN_SYN, "genus -batch -files", "genus -64 ",
     "Cadence documents `genus -batch -files <tcl>`; -64 is RTL-Compiler era"),
    (RUN_CDC, "vc_static_shell -f", "run_tool vc_cdc ",
     "vc_cdc is an app name; the executable is vc_static_shell"),
    (RUN_CDC, "qverify -c -do", None,
     "Siemens documents `qverify -c -do <do> -od <outdir>`"),
    (RUN_SYN, "dc_shell -64bit -f", None,
     "Synopsys shells spell the 64-bit switch -64bit"),
    (RUN_FORMALITY, "fm_shell -64bit -f", None,
     "Synopsys shells spell the 64-bit switch -64bit"),
    (RUN_SYN, "vivado -mode batch -source", None,
     "AMD documents `vivado -mode batch -source <tcl>`; batch mode exits after the script"),
]


@pytest.mark.parametrize(
    ("path", "required", "forbidden", "why"),
    CONTRACTS,
    ids=[f"{p.name}:{r.split()[0]}" for p, r, _, _ in CONTRACTS],
)
def test_documented_invocation_shape(path: Path, required, forbidden, why) -> None:
    text = _body(path)
    assert required in text, f"{path.name}: expected `{required}` — {why}"
    if forbidden:
        assert forbidden not in text, f"{path.name}: `{forbidden}` must not survive — {why}"


def test_vc_static_shell_runs_in_batch() -> None:
    """-batch makes VC Static quit on an unexpected error instead of prompting."""
    text = _body(RUN_CDC)
    match = re.search(r"run_tool vc_static_shell[^\n]*", text)
    assert match, "vc_static_shell invocation not found"
    assert "-batch" in match.group(0), f"missing -batch: {match.group(0)}"


def test_questa_cdc_directs_output_to_the_reported_directory() -> None:
    """Without -od the session database and the runner's report directory diverge."""
    text = _body(RUN_CDC)
    match = re.search(r"run_tool qverify[^\n]*", text)
    assert match, "qverify invocation not found"
    assert "-od" in match.group(0), f"missing -od: {match.group(0)}"


def test_xcelium_elaborates_before_running() -> None:
    """-compile writes no snapshot and -R opens an existing one."""
    text = _body(RUN_SIM)
    for step in ("xrun -compile", "xrun -elaborate", "xrun -R"):
        assert step in text, f"missing Xcelium step: {step}"
    assert text.index("xrun -compile") < text.index("xrun -elaborate"), (
        "elaborate must follow compile"
    )


def test_xcelium_steps_share_one_library_directory() -> None:
    """compile, elaborate and run must all name the same -xmlibdirname."""
    text = _body(RUN_SIM)
    libs = {m.rstrip('"\'') for m in re.findall(r"-xmlibdirname (\S+)", text)}
    assert len(libs) == 1, f"Xcelium steps disagree on the library directory: {libs}"


def test_vivado_uses_the_user_script_instead_of_only_erroring() -> None:
    """The branch used to exit 1 even when --script was supplied."""
    text = _body(RUN_SYN)
    branch = text.split("\n  vivado)", 1)[1].split("\n    ;;", 1)[0]
    assert "SCRIPT_PATH" in branch, "vivado branch must consume --script"
    assert "run_tool vivado" in branch, "vivado branch must actually run the tool"
