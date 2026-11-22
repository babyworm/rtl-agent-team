"""Bundled bash scripts must run under bash 3.2 (macOS /bin/bash) and bash 4.0-4.3.

Linux CI runs bash 5, where two classes of breakage stay invisible:

- syntax added in bash 4 or later (``exec {fd}<file``, ``declare -A``, ``mapfile``, ...)
  fails at parse or run time on macOS;
- ``"${name[@]}"`` of an empty array under ``set -u`` is an "unbound variable" error
  before bash 4.4 (macOS 3.2, RHEL 7's 4.2). ``${name[@]+"${name[@]}"}`` expands to
  the same words on every version, and ``${name[*]:-}`` to the same string.

The scan is static so that it guards every script, not only the paths a unit test runs.
"""

import re

import pytest

from tests.conftest import REPO_ROOT

SCRIPT_GLOBS = ("scripts/*.sh", "skills/**/*.sh")

# Scripts that may use bash 4 syntax because they exit with a clear error under bash < 4
# before reaching it. The guard itself is checked below.
BASH4_ONLY = {
    "skills/rat-init-project/scripts/generate_config.sh":
        "associative arrays; refuses bash < 4 at entry, and its tests skip without bash 4",
}

# Never sets -u itself, but every wrapper that sources it does.
SOURCED_UNDER_NOUNSET = {"skills/rat-init-project/templates/lib/tool-runner.sh"}

BASH4_CONSTRUCTS = {
    "{name}> / {name}< descriptor allocation (bash 4.1)": re.compile(r"\{[A-Za-z_]\w*\}[<>]"),
    "declare/local -A or -n (bash 4.0 / 4.3)": re.compile(r"\b(?:declare|local|typeset)\s+-[a-zA-Z]*[An]"),
    "mapfile / readarray (bash 4.0)": re.compile(r"\b(?:mapfile|readarray)\b"),
    "${x,,} / ${x^^} case modification (bash 4.0)": re.compile(r"\$\{[A-Za-z_]\w*(?:\[[^]]*\])?(?:,,?|\^\^?)\}"),
    "wait -n (bash 4.3)": re.compile(r"\bwait\s+-n\b"),
    "coproc (bash 4.0)": re.compile(r"\bcoproc\b"),
    "|& (bash 4.0)": re.compile(r"\|&"),
    ";& / ;;& case fall-through (bash 4.0)": re.compile(r";;?&"),
    "&>> (bash 4.0)": re.compile(r"&>>"),
}

NOUNSET = re.compile(r"^\s*set\s+(?:-[a-zA-Z]*u|-o\s+nounset)", re.M)
# ${name[@]+"${name[@]}"}, also inside outer double quotes.
GUARDED = re.compile(r'\$\{([A-Za-z_]\w*)\[@\]\+"\$\{\1\[@\]\}"\}')
ARRAY_EXPANSION = re.compile(r"\$\{([A-Za-z_]\w*)\[([@*])\]([^}]*)\}")
# Operators that substitute instead of failing when the array has no elements.
SAFE_OPERATORS = ("+", "-", ":+", ":-")
HEREDOC = re.compile(r"<<(-?)\s*(?:'([A-Za-z_]\w*)'|\"([A-Za-z_]\w*)\"|\\([A-Za-z_]\w*)|([A-Za-z_]\w*))")


def bash_scripts():
    found = set()
    for pattern in SCRIPT_GLOBS:
        for path in REPO_ROOT.glob(pattern):
            first = path.read_text(errors="replace").split("\n", 1)[0]
            if first.startswith("#!") and "bash" in first:
                found.add(path)
    return sorted(found)


def code_lines(text):
    """Yield (line number, text, is_heredoc_body) with comments, single-quoted text and
    quoted heredoc bodies removed. Unquoted heredoc bodies are kept: bash expands them."""
    quote = None  # None, "'", '"' or "$'"; carried across lines
    pending = []  # heredocs opened on the current line: (delimiter, quoted, strip_tabs)
    heredoc = None
    for number, line in enumerate(text.splitlines(), 1):
        if heredoc:
            delimiter, quoted, strip_tabs = heredoc
            if (line.lstrip("\t") if strip_tabs else line) == delimiter:
                heredoc = pending.pop(0) if pending else None
            elif not quoted:
                yield number, line, True
            continue
        code, index = [], 0
        while index < len(line):
            char = line[index]
            if quote in ("'", "$'"):
                if quote == "$'" and char == "\\":
                    index += 2
                    continue
                if char == "'":
                    quote = None
                    code.append("'")
                index += 1
                continue
            if char == "\\":
                code.append(line[index:index + 2])
                index += 2
                continue
            if quote == '"':
                if char == '"':
                    quote = None
                code.append(char)
                index += 1
                continue
            if char == "#" and (index == 0 or line[index - 1] in " \t;&|("):
                break
            if char == "'" or line.startswith("$'", index):
                quote = "'" if char == "'" else "$'"
                code.append(line[index:index + len(quote)])
                index += len(quote)
                continue
            if char == '"':
                quote = '"'
            elif line.startswith("<<", index) and not line.startswith("<<<", index):
                match = HEREDOC.match(line, index)
                if match:
                    delimiter = next(group for group in match.groups()[1:] if group)
                    pending.append((delimiter, not match.group(5), match.group(1) == "-"))
                    code.append(match.group(0))
                    index = match.end()
                    continue
            code.append(char)
            index += 1
        yield number, "".join(code), False
        if pending and quote is None:
            heredoc = pending.pop(0)


def relative(path):
    return path.relative_to(REPO_ROOT).as_posix()


def test_scan_covers_the_bundled_runners():
    names = {relative(path) for path in bash_scripts()}
    for expected in ("scripts/run_sim.sh", "skills/rat-init-project/templates/run_lint.sh",
                     "skills/rat-init-project/templates/lib/tool-runner.sh",
                     "skills/rtl-p5s-func-verify/scripts/run_regression.sh",
                     "skills/rtl-p5s-uvm-verify/scripts/run_regression_uvm.sh"):
        assert expected in names
    assert set(BASH4_ONLY) | SOURCED_UNDER_NOUNSET <= names


def test_scanner_reads_bash_quoting_and_heredocs():
    sample = """x='${a[@]} |& # not code'
echo "${b[@]}" # ${c[@]}
cat <<'EOF'
${d[@]} |&
EOF
cat <<EOF
${e[*]}
EOF
echo ${f[@]+"${f[@]}"} "${g[*]:-}" ${#h[@]} ${!i[@]}
"""
    lines = list(code_lines(sample))
    code = "\n".join(text for _, text, _ in lines)
    found = [match.group(1) for match in ARRAY_EXPANSION.finditer(GUARDED.sub("", code))
             if not match.group(3).startswith(SAFE_OPERATORS)]
    assert found == ["b", "e"]
    assert [number for number, _, body in lines if body] == [7]
    assert not any(pattern.search(code) for pattern in BASH4_CONSTRUCTS.values())


@pytest.mark.parametrize("line", [
    'exec {fd}<"$file"', "exec {out}>log", "declare -A seen=()", "local -n ref=$1", "mapfile -t rows < f",
    "readarray rows", 'echo "${name,,}"', "echo ${name^^}", "wait -n", "coproc worker { :; }",
    "make |& tee log", "a) x ;&", "a) x ;;&", "make &>> log",
])
def test_scanner_flags_bash4_syntax(line):
    [(_, code, _)] = code_lines(line + "\n")
    assert any(pattern.search(code) for pattern in BASH4_CONSTRUCTS.values())


@pytest.mark.parametrize("path", bash_scripts(), ids=relative)
def test_no_bash4_syntax(path):
    name = relative(path)
    text = path.read_text()
    if name in BASH4_ONLY:
        assert re.search(r"BASH_VERSINFO\[0\]\s*<\s*4\b.*\n.*\n\s*exit", text), \
            f"{name} must refuse bash < 4 before using bash 4 syntax"
        return
    problems = [f"{name}:{number}: {label}: {code.strip()}"
                for number, code, body in code_lines(text) if not body
                for label, pattern in BASH4_CONSTRUCTS.items() if pattern.search(code)]
    assert not problems, "bash 3.2 (macOS) cannot run:\n" + "\n".join(problems)


@pytest.mark.parametrize("path", bash_scripts(), ids=relative)
def test_array_expansions_survive_nounset_before_bash_4_4(path):
    name = relative(path)
    text = path.read_text()
    strict = (any(NOUNSET.search(code) for _, code, body in code_lines(text) if not body)
              or name in SOURCED_UNDER_NOUNSET)
    if not strict:
        pytest.skip("does not run under set -u")
    problems = []
    for number, code, _ in code_lines(text):
        for match in ARRAY_EXPANSION.finditer(GUARDED.sub("", code)):
            if not match.group(3).startswith(SAFE_OPERATORS):
                problems.append(f"{name}:{number}: {match.group(0)}")
    assert not problems, ('empty arrays are unbound under set -u before bash 4.4; write ${a[@]+"${a[@]}"} '
                          "or ${a[*]:-}:\n" + "\n".join(problems))
