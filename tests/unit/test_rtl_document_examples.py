import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
import pytest

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "skills" / "rtl-document" / "examples"
SCRIPTS = ROOT / "skills" / "rtl-document" / "scripts"
TEMPLATES = ROOT / "skills" / "rtl-document" / "templates"
FIXTURES = ROOT / "tests" / "fixtures" / "rtl-document"

VERIBLE_AVAILABLE = shutil.which("verible-verilog-syntax") is not None

# An unfilled marker is the literal HTML comment with the LLM_FILL token inside.
# The auto-generated preamble line in each example contains the words "LLM_FILL"
# as instructional text (inside a blockquote), not as a real marker, so we match
# only the bare comment form.
MARKER_RE = re.compile(r"<!--\s*LLM_FILL\s*:")


def test_examples_have_no_stray_markers():
    files = sorted(EXAMPLES.glob("*.md"))
    assert len(files) == 3, f"expected 3 examples, found {len(files)}"
    for f in files:
        raw = f.read_text()
        # Strip blockquote lines (preamble) — they intentionally contain the
        # literal text "<!-- LLM_FILL: ... -->" as instructional backtick-quoted
        # example text, which is not an actual unfilled marker.
        body = "\n".join(
            line for line in raw.splitlines() if not line.startswith(">")
        )
        assert not MARKER_RE.search(body), f"{f.name} still has unfilled LLM_FILL markers"
        assert "{{" not in body, f"{f.name} still has placeholder braces"


def test_examples_required_sections():
    expected = {
        "simple_fifo.md":           ["Ports", "Parameters"],
        "axi_stream_bridge.md":     ["Ports", "Clock Domains"],
        "cabac_encoder_excerpt.md": ["FSM States", "Sub-Module Instances"],
    }
    for name, sections in expected.items():
        body = (EXAMPLES / name).read_text()
        for s in sections:
            assert s in body, f"{name} missing '{s}'"


@pytest.mark.skipif(not VERIBLE_AVAILABLE, reason="verible not installed")
def test_pipeline_smoke(tmp_path):
    j = tmp_path / "s.json"
    md = tmp_path / "s.md"
    subprocess.run(
        [sys.executable, str(SCRIPTS / "extract_module_doc.py"),
         "--rtl", str(FIXTURES / "simple_fifo.sv"),
         "--out", str(j)],
        check=True,
    )
    data = json.loads(j.read_text())
    assert data["module_name"] == "simple_fifo"
    subprocess.run(
        [sys.executable, str(SCRIPTS / "render_doc.py"),
         "--json", str(j),
         "--template-dir", str(TEMPLATES),
         "--out", str(md)],
        check=True,
    )
    body = md.read_text()
    assert "i_data" in body
    # Raw rendered output still has markers; LLM fills them in a later step.
    assert MARKER_RE.search(body), "raw render should still contain LLM_FILL markers"
