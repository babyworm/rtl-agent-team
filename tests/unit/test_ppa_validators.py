"""Unit tests for the PPA_TOP / PPA_LIBERTY / PPA_SDC validation blocks
extracted LIVE from the actual source files so drift is caught.
"""
import os
import pathlib
import re
import subprocess
import textwrap

import pytest

REPO = pathlib.Path(__file__).resolve().parents[2]

VALIDATOR_SOURCES = {
    "skill": REPO / "skills" / "rtl-ppa-optimize-dc" / "SKILL.md",
    "orchestrator": REPO / "agents" / "ppa-optimizer-dc-orchestrator.md",
}


def _extract_validator(md_path):
    """Extract the PPA_TOP + PPA_LIBERTY/PPA_SDC validator bash block from the given markdown file.

    Uses a regex that matches from `# Validate PPA_TOP:` to the closing `done` of the
    PPA_LIBERTY/PPA_SDC loop.  The PPA_TOP= assignment line is stripped so tests can
    supply PPA_TOP directly via environment without it being overwritten.  Appends
    `echo VALID` so successful passage is detectable.
    """
    text = md_path.read_text()
    m = re.search(
        r"(# Validate PPA_TOP:.*?\n(?:.*?\n)*?\s*done)",
        text,
    )
    assert m, f"Could not locate validator block in {md_path}"
    body = m.group(1)
    # Remove the PPA_TOP= assignment line (may be indented inside a fenced block)
    body = re.sub(r"^[ \t]*PPA_TOP=.*\n", "", body, flags=re.MULTILINE)
    # Dedent after removing the assignment line so indented blocks normalise
    body = textwrap.dedent(body)
    return body + "\necho VALID\n"


# Materialize scripts once (module-level cache)
SCRIPTS = {name: _extract_validator(p) for name, p in VALIDATOR_SOURCES.items()}


@pytest.fixture(params=sorted(SCRIPTS.keys()))
def validator(request):
    """Yields the validator script name and its extracted body."""
    return request.param, SCRIPTS[request.param]


def _run(validator_body, env):
    """Run the validator with a given environment."""
    res = subprocess.run(
        ["sh", "-c", validator_body],
        env={**os.environ, **env},
        capture_output=True, text=True, timeout=5,
    )
    return res.returncode, res.stdout.strip(), res.stderr.strip()


class TestPPATopValidation:
    def test_empty_rejected(self, validator):
        name, body = validator
        rc, _, err = _run(body, {"PPA_TOP": ""})
        assert rc != 0, f"{name}: empty PPA_TOP must be rejected"

    def test_valid_identifier_accepted(self, validator):
        name, body = validator
        rc, out, err = _run(body, {"PPA_TOP": "vc_transform_8x8"})
        assert rc == 0, f"{name}: valid identifier rejected — err={err}"
        assert out == "VALID"

    def test_leading_digit_rejected(self, validator):
        name, body = validator
        rc, _, err = _run(body, {"PPA_TOP": "8x8_transform"})
        assert rc != 0, f"{name}: leading-digit PPA_TOP must be rejected"

    def test_shell_injection_rejected(self, validator):
        name, body = validator
        rc, _, err = _run(body, {"PPA_TOP": "foo; rm -rf /"})
        assert rc != 0, f"{name}"

    def test_path_traversal_rejected(self, validator):
        name, body = validator
        rc, _, err = _run(body, {"PPA_TOP": "../../etc/passwd"})
        assert rc != 0, f"{name}"

    def test_hyphen_rejected(self, validator):
        name, body = validator
        rc, _, err = _run(body, {"PPA_TOP": "foo-bar"})
        assert rc != 0, f"{name}"


class TestPPALibrarySDCValidation:
    def test_unset_liberty_allowed(self, validator):
        name, body = validator
        rc, out, _ = _run(body, {"PPA_TOP": "top"})
        assert rc == 0, f"{name}: unset LIBERTY should be allowed"

    def test_valid_liberty_path_accepted(self, validator, tmp_path):
        name, body = validator
        lib = tmp_path / "test.lib"
        lib.write_text("dummy")
        rc, out, _ = _run(body, {"PPA_TOP": "top", "PPA_LIBERTY": str(lib)})
        assert rc == 0

    def test_liberty_with_backtick_rejected(self, validator):
        name, body = validator
        rc, _, _ = _run(body, {"PPA_TOP": "top", "PPA_LIBERTY": "/tmp/`id`.lib"})
        assert rc != 0

    def test_liberty_with_tcl_bracket_rejected(self, validator):
        name, body = validator
        rc, _, _ = _run(body, {"PPA_TOP": "top", "PPA_LIBERTY": "/tmp/[exec].lib"})
        assert rc != 0

    def test_liberty_with_dollar_rejected(self, validator):
        name, body = validator
        rc, _, _ = _run(body, {"PPA_TOP": "top", "PPA_LIBERTY": "/tmp/$PATH.lib"})
        assert rc != 0

    def test_liberty_with_space_rejected(self, validator):
        name, body = validator
        rc, _, _ = _run(body, {"PPA_TOP": "top", "PPA_LIBERTY": "/tmp/has space.lib"})
        assert rc != 0

    def test_liberty_with_semicolon_rejected(self, validator):
        name, body = validator
        rc, _, _ = _run(body, {"PPA_TOP": "top", "PPA_LIBERTY": "/tmp/a;rm.lib"})
        assert rc != 0

    def test_liberty_nonexistent_rejected(self, validator):
        name, body = validator
        rc, _, err = _run(body, {"PPA_TOP": "top", "PPA_LIBERTY": "/tmp/definitely_nonexistent.lib"})
        assert rc != 0
        assert "not a regular file" in err

    def test_liberty_directory_rejected(self, validator, tmp_path):
        name, body = validator
        rc, _, err = _run(body, {"PPA_TOP": "top", "PPA_LIBERTY": str(tmp_path)})
        assert rc != 0
        assert "not a regular file" in err

    def test_sdc_with_backslash_rejected(self, validator):
        name, body = validator
        rc, _, _ = _run(body, {"PPA_TOP": "top", "PPA_SDC": "/tmp/a\\b.sdc"})
        assert rc != 0
