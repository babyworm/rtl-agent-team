"""Unit tests for the PPA_TOP / PPA_LIBERTY / PPA_SDC validation blocks
extracted from skills/rtl-ppa-optimize-dc/SKILL.md. These test that the
validator rejects invalid inputs per Codex R1/R2 hardening.
"""
import os
import subprocess
import textwrap

import pytest


VALIDATOR_SCRIPT = textwrap.dedent(r'''
#!/bin/sh
set -e

# PPA_TOP validation (must be a SV identifier)
if [ -z "${PPA_TOP}" ]; then
    echo "ERROR: PPA_TOP must be provided" >&2
    exit 1
fi

case "${PPA_TOP}" in
    *[!A-Za-z0-9_]*|[!A-Za-z_]*)
        echo "ERROR: PPA_TOP='${PPA_TOP}' must match [A-Za-z_][A-Za-z0-9_]*" >&2
        exit 1
        ;;
esac

# PPA_LIBERTY / PPA_SDC validation (no shell+Tcl metachars, must be regular file)
for _var in PPA_LIBERTY PPA_SDC; do
    _val=$(eval "printf '%s' \"\${$_var:-}\"")
    if [ -z "${_val}" ]; then
        continue
    fi
    case "${_val}" in
        *[\`\$\;\&\|\<\>\"\'\ \[\]\\]*)
            echo "ERROR: ${_var}='${_val}' contains unsafe shell/Tcl characters" >&2
            exit 1
            ;;
    esac
    if [ ! -f "${_val}" ]; then
        echo "ERROR: ${_var}='${_val}' is not a regular file" >&2
        exit 1
    fi
done

echo "VALID"
''').strip()


def _run(env):
    """Run the validator with a given environment and return (rc, stdout, stderr)."""
    res = subprocess.run(
        ["sh", "-c", VALIDATOR_SCRIPT],
        env={**os.environ, **env},
        capture_output=True, text=True, timeout=5,
    )
    return res.returncode, res.stdout.strip(), res.stderr.strip()


class TestPPATopValidation:
    def test_empty_rejected(self):
        rc, _, err = _run({"PPA_TOP": ""})
        assert rc == 1
        assert "PPA_TOP" in err

    def test_valid_identifier_accepted(self, tmp_path):
        rc, out, _ = _run({"PPA_TOP": "vc_transform_8x8"})
        assert rc == 0
        assert out == "VALID"

    def test_leading_digit_rejected(self):
        rc, _, err = _run({"PPA_TOP": "8x8_transform"})
        assert rc == 1
        assert "PPA_TOP" in err

    def test_shell_injection_rejected(self):
        rc, _, err = _run({"PPA_TOP": "foo; rm -rf /"})
        assert rc == 1

    def test_path_traversal_rejected(self):
        rc, _, err = _run({"PPA_TOP": "../../etc/passwd"})
        assert rc == 1

    def test_hyphen_rejected(self):
        rc, _, err = _run({"PPA_TOP": "foo-bar"})
        assert rc == 1


class TestPPALibrarySDCValidation:
    def test_unset_liberty_allowed(self, tmp_path):
        rc, out, _ = _run({"PPA_TOP": "top"})  # LIBERTY/SDC unset
        assert rc == 0
        assert out == "VALID"

    def test_valid_liberty_path_accepted(self, tmp_path):
        lib = tmp_path / "test.lib"
        lib.write_text("dummy")
        rc, out, _ = _run({"PPA_TOP": "top", "PPA_LIBERTY": str(lib)})
        assert rc == 0
        assert out == "VALID"

    def test_liberty_with_backtick_rejected(self):
        rc, _, err = _run({"PPA_TOP": "top", "PPA_LIBERTY": "/tmp/`id`.lib"})
        assert rc == 1
        assert "unsafe" in err.lower() or "PPA_LIBERTY" in err

    def test_liberty_with_tcl_bracket_rejected(self):
        rc, _, err = _run({"PPA_TOP": "top", "PPA_LIBERTY": "/tmp/[exec].lib"})
        assert rc == 1

    def test_liberty_with_dollar_rejected(self):
        rc, _, err = _run({"PPA_TOP": "top", "PPA_LIBERTY": "/tmp/$PATH.lib"})
        assert rc == 1

    def test_liberty_with_space_rejected(self):
        rc, _, err = _run({"PPA_TOP": "top", "PPA_LIBERTY": "/tmp/has space.lib"})
        assert rc == 1

    def test_liberty_with_semicolon_rejected(self):
        rc, _, err = _run({"PPA_TOP": "top", "PPA_LIBERTY": "/tmp/a;rm.lib"})
        assert rc == 1

    def test_liberty_nonexistent_rejected(self):
        rc, _, err = _run({"PPA_TOP": "top", "PPA_LIBERTY": "/tmp/definitely_nonexistent.lib"})
        assert rc == 1
        assert "not a regular file" in err

    def test_liberty_directory_rejected(self, tmp_path):
        rc, _, err = _run({"PPA_TOP": "top", "PPA_LIBERTY": str(tmp_path)})
        assert rc == 1
        assert "not a regular file" in err

    def test_sdc_with_backslash_rejected(self):
        rc, _, err = _run({"PPA_TOP": "top", "PPA_SDC": "/tmp/a\\b.sdc"})
        assert rc == 1
