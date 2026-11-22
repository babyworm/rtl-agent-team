"""The plugin's Python floor is one number, enforced in CI and in every Python file."""

import ast
import os
import re
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT

sys.path.insert(0, str(REPO_ROOT / "scripts"))
import rat_compat  # noqa: E402

# Names added after the floor (3.9). The floor's CI job catches what this list misses.
NEWER_APIS = [
    r"\btomllib\b", r"\bdatetime\.UTC\b", r"from datetime import[^\n]*\bUTC\b",
    r"\bzip\([^)\n]*\bstrict\s*=", r"\bitertools\.batched\b", r"from itertools import[^\n]*\bbatched\b",
    r"\btyping\.(?:Self|TypeAlias|ParamSpec|TypeGuard|Concatenate|override|Never|LiteralString)\b",
    r"from typing import[^\n]*\b(?:Self|TypeAlias|ParamSpec|TypeGuard|Concatenate|override|Never|LiteralString)\b",
    r"\bcontextlib\.chdir\b", r"from contextlib import[^\n]*\bchdir\b", r"\bExceptionGroup\b", r"\bexcept\s*\*",
    r"\.bit_count\(\)", r"@dataclass\([^)]*\b(?:slots|kw_only)\s*=",
    r"\.hardlink_to\(", r"\.is_junction\(", r"\bhashlib\.file_digest\b", r"\bStrEnum\b",
    r"\basyncio\.timeout\(", r"\bsys\.(?:orig_argv|stdlib_module_names)\b", r"\bpipesize\s*=",
    r"\bitertools\.pairwise\b", r"from itertools import[^\n]*\bpairwise\b", r"\bglob\([^)\n]*\broot_dir\s*=",
]


def python_files():
    listed = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "--others", "--exclude-standard",
                             "*.py"], capture_output=True, text=True, check=True).stdout.split()
    for name in listed:
        path = REPO_ROOT / name
        if not path.is_file():
            continue
        text = path.read_text(errors="replace")
        if "/templates/" in name and "{{" in text:
            continue  # a code template with placeholders, rendered before it runs
        yield name, text


def floor_from(path, pattern):
    match = re.search(pattern, (REPO_ROOT / path).read_text(), re.M)
    assert match, f"{path}: no Python floor found"
    return tuple(int(part) for part in match[1].split("."))


def test_shell_and_python_floors_agree():
    assert floor_from("hooks/lib/python-util.sh", r"^RAT_PYTHON_MIN=([0-9.]+)$") == rat_compat.MIN_PYTHON


# A floor written out elsewhere: a version comparison or a "Python >= X.Y" message.
FLOOR_COPY = re.compile(r"version_info\s*(?:<|>=)\s*\(\s*(\d+)\s*,\s*(\d+)\s*\)|Python\s*>=\s*(\d+)\.(\d+)")


def test_every_copy_of_the_floor_is_the_floor():
    listed = subprocess.run(["git", "-C", str(REPO_ROOT), "ls-files", "--cached", "--others", "--exclude-standard",
                             "*.sh", "*.py", "skills/*/SKILL.md"], capture_output=True, text=True, check=True)
    copies, wrong = 0, []
    for name in listed.stdout.split():
        if name.startswith("tests/") or not (REPO_ROOT / name).is_file():
            continue
        text = (REPO_ROOT / name).read_text(errors="replace")
        for match in FLOOR_COPY.finditer(text):
            copies += 1
            version = tuple(int(part) for part in match.groups() if part)
            if version != rat_compat.MIN_PYTHON:
                wrong.append(f"{name}:{text.count(chr(10), 0, match.start()) + 1}: {match[0]}")
    assert copies >= 6, "the floor copies moved; update this test's pattern"
    assert not wrong, "raise every copy of the Python floor together:\n" + "\n".join(wrong)


def test_ci_tests_the_floor_and_the_newest_version():
    workflow = (REPO_ROOT / ".github/workflows/ci.yml").read_text()
    matrix = re.search(r"python-version:\s*\[([^\]]+)\]", workflow)
    versions = {tuple(int(part) for part in value.strip(" '\"").split(".")) for value in matrix[1].split(",")}
    assert set(rat_compat.TESTED) <= versions and rat_compat.MIN_PYTHON in versions


@pytest.mark.parametrize("version,expected", [
    ((2, 7), "unsupported"), ((3, 8), "unsupported"), ((3, 9), "eol"), ((3, 10), "eol"), ((3, 12), "supported"),
    ((3, 14), "supported"), ((3, 15), "untested"),
])
def test_compatibility_levels(version, expected):
    assert rat_compat.level(version) == expected


def test_compat_module_parses_under_python_2_grammar():
    # An old interpreter must reach the "unsupported" line, not a SyntaxError.
    tree = ast.parse((REPO_ROOT / "scripts/rat_compat.py").read_text())
    for node in ast.walk(tree):
        assert not isinstance(node, (ast.JoinedStr, ast.AnnAssign, ast.NamedExpr)), ast.dump(node)[:80]
        if isinstance(node, ast.FunctionDef):
            assert node.returns is None and all(arg.annotation is None for arg in node.args.args)


def test_every_python_file_stays_within_the_floor():
    problems = []
    for name, text in python_files():
        try:
            tree = ast.parse(text, feature_version=rat_compat.MIN_PYTHON)
        except SyntaxError as exc:
            problems.append(f"{name}:{exc.lineno}: not {rat_compat.MIN_PYTHON} syntax: {exc.msg}")
            continue
        future = any(isinstance(node, ast.ImportFrom) and node.module == "__future__"
                     and any(alias.name == "annotations" for alias in node.names) for node in tree.body)
        union = lambda node: node is not None and any(  # noqa: E731
            isinstance(part, ast.BinOp) and isinstance(part.op, ast.BitOr) for part in ast.walk(node))
        for node in ast.walk(tree):
            annotations = []
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                arguments = node.args.posonlyargs + node.args.args + node.args.kwonlyargs
                annotations = [node.returns, *(arg.annotation for arg in arguments),
                               *(arg.annotation for arg in (node.args.vararg, node.args.kwarg) if arg)]
            elif isinstance(node, ast.AnnAssign):
                annotations = [node.annotation]
            if not future and any(union(annotation) for annotation in annotations):
                problems.append(f"{name}:{node.lineno}: X | Y annotation needs 'from __future__ import annotations'")
        for pattern in NEWER_APIS if name != "tests/unit/test_python_compat.py" else ():  # its own list
            for match in re.finditer(pattern, text):
                problems.append(f"{name}:{text.count(chr(10), 0, match.start()) + 1}: newer than the floor: {match[0]}")
    assert not problems, "\n".join(problems)


def _shell(script, path):
    # /bin/sh by absolute path, so PATH can hold nothing but the fakes.
    return subprocess.run(["/bin/sh", "-c", script], capture_output=True, text=True, timeout=20,
                          env={"PATH": path, "HOME": "/tmp"})


def _real_python3_usable():
    """/usr/bin/python3 runs and meets the floor, without starting macOS's install stub."""
    if not os.path.exists("/usr/bin/python3"):
        return False
    if sys.platform == "darwin":
        developer = subprocess.run(["xcode-select", "-p"], capture_output=True, text=True)
        tools = os.path.join(developer.stdout.strip() or "/missing", "usr/bin/python3")
        if developer.returncode or not os.access(tools, os.X_OK) or os.path.samefile(tools, "/usr/bin/python3"):
            return False
    probe = ["/usr/bin/python3", "-c", "import sys; sys.exit(sys.version_info < (3, 9))"]
    return subprocess.run(probe, capture_output=True).returncode == 0


@pytest.mark.skipif(not _real_python3_usable(), reason="needs a /usr/bin/python3 that meets the floor")
@pytest.mark.parametrize("spelling", ["/usr/bin", "/usr//bin", "symlink"])
@pytest.mark.parametrize("tools", ["installed", "missing", "empty answer", "root answer"])
def test_macos_install_stub_is_never_started(tmp_path, tools, spelling):
    # Without the developer tools, macOS /usr/bin/python3 opens an install dialog when run.
    # The guard compares files, so another spelling of the path or a symlink is caught too,
    # and an xcode-select answer that points back at the shim does not count as installed.
    fake = tmp_path / "bin"
    fake.mkdir()
    developer = tmp_path / "Developer"
    (developer / "usr/bin").mkdir(parents=True)
    (developer / "usr/bin/python3").symlink_to(sys.executable)
    answers = {"installed": f"echo {developer}", "missing": "exit 2", "empty answer": "exit 0",
               "root answer": "echo /"}
    (fake / "uname").write_text("#!/bin/sh\necho Darwin\n")
    (fake / "xcode-select").write_text(f"#!/bin/sh\n{answers[tools]}\n")
    for tool in ("uname", "xcode-select"):
        (fake / tool).chmod(0o755)
    if spelling == "symlink":
        (fake / "python3").symlink_to("/usr/bin/python3")
        path = f"{fake}:/bin"
    else:
        path = f"{fake}:{spelling}:/bin"
    hooks = REPO_ROOT / "hooks/lib"
    selected = _shell(f'. "{hooks}/python-util.sh"; rat_select_python', path)
    parsed = _shell(f'. "{hooks}/json-util.sh"; RTL_FORCE_PYTHON_PARSER=1 jsonu_detect_parser; printf %s "$JSONU_PY_BIN"', path)
    assert (selected.returncode == 0) == (tools == "installed"), selected.stderr
    assert (parsed.stdout != "") == (tools == "installed")


def test_python_is_not_started_when_jq_parses(tmp_path):
    fake = tmp_path / "bin"
    fake.mkdir()
    started = tmp_path / "python-started"
    (fake / "python3").write_text(f'#!/bin/sh\n: > "{started}"\nexit 1\n')
    (fake / "jq").write_text("#!/bin/sh\nexit 0\n")
    for tool in ("python3", "jq"):
        (fake / tool).chmod(0o755)
    hooks = REPO_ROOT / "hooks/lib"
    # Only the fakes on PATH: CI images carry a real jq in /usr/bin (= /bin there).
    with_jq = _shell(f'. "{hooks}/json-util.sh"; jsonu_detect_parser; printf %s "$JSONU_PARSER_MODE"', str(fake))
    assert with_jq.stdout == "jq" and not started.exists()
    (fake / "jq").unlink()
    _shell(f'. "{hooks}/json-util.sh"; jsonu_detect_parser', str(fake))
    assert started.exists()  # without jq the parser needs Python and probes it
