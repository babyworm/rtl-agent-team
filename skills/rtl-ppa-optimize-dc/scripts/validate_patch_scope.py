#!/usr/bin/env python3
"""Validate that a unified diff only touches allowed scope, never frozen scope.

Invocation:
    validate_patch_scope.py <patch.diff> <allowed_globs_csv> <frozen_globs_csv>

Exit 0 when patch is within scope; non-zero on violation (paths printed to stderr).
"""
from __future__ import annotations

import fnmatch
import pathlib
import posixpath
import re
import sys


# Match git diff headers with either unquoted or C-quoted paths on either side.
DIFF_GIT_RE = re.compile(
    r'^diff --git (?:"a/((?:\\.|[^"\\])+)"|a/(\S+)) (?:"b/((?:\\.|[^"\\])+)"|b/(\S+))$',
    re.MULTILINE,
)
UNIFIED_HEADER_RE = re.compile(
    r'^(?:---|\+\+\+)\s+(?:"((?:\\.|[^"\\])+)"|(\S+))',
    re.MULTILINE,
)


def _unescape_git_path(raw: str) -> str:
    return re.sub(r'\\(.)', r'\1', raw)


def _normalize_path(raw: str) -> str:
    p = raw.replace("\\", "/")
    if p.startswith(("a/", "b/")):
        p = p[2:]
    while p.startswith("./"):
        p = p[2:]
    if not p:
        return ""
    if p.startswith("/"):
        return "/" + posixpath.normpath(p).lstrip("/")
    return posixpath.normpath(p)


def extract_changed_files(diff_text):
    seen = []
    seen_set = set()

    def _add(raw_path: str, quoted: bool = False) -> None:
        if not raw_path or raw_path == "/dev/null":
            return
        val = _unescape_git_path(raw_path) if quoted else raw_path
        if val == "/dev/null":
            return
        norm = _normalize_path(val)
        if norm and norm not in seen_set:
            seen_set.add(norm)
            seen.append(norm)

    for m in DIFF_GIT_RE.finditer(diff_text):
        a_q, a_u, b_q, b_u = m.groups()
        if a_q is not None:
            _add(a_q, quoted=True)
        elif a_u is not None:
            _add(a_u)
        if b_q is not None:
            _add(b_q, quoted=True)
        elif b_u is not None:
            _add(b_u)

    if not seen:
        for m in UNIFIED_HEADER_RE.finditer(diff_text):
            q, u = m.groups()
            if q is not None:
                _add(q, quoted=True)
            elif u is not None:
                _add(u)

    return seen


def _match(path, glob_list):
    """Match path against a glob list with proper ** (recursive) support."""
    import re as _re
    for g in glob_list:
        if "**" in g:
            # Build a regex from the glob where ** matches zero or more path segments.
            # Strategy: split on "/" and translate each segment independently.
            parts = g.split("/")
            regex_segments = []
            for part in parts:
                if part == "**":
                    # ** matches zero or more path components (including none)
                    regex_segments.append("__DOUBLESTAR__")
                else:
                    # Translate fnmatch pattern for a single segment (no slashes)
                    translated = fnmatch.translate(part)
                    # fnmatch.translate wraps in (?s:...)\Z (Python <3.14) or
                    # (?s:...)\z (Python 3.14+). Strip outer wrapper + end anchor
                    # in either form.
                    translated = (
                        translated.replace(r"\Z", "")
                                  .replace(r"\z", "")
                                  .replace(r"(?s:", "")
                                  .removesuffix(")")
                    )
                    regex_segments.append(translated)
            # Join segments with "/" and collapse __DOUBLESTAR__ properly
            regex = "/".join(regex_segments)
            # __DOUBLESTAR__ between slashes: matches zero or more path components
            regex = regex.replace("/__DOUBLESTAR__/", "(?:/.+)?/")
            # __DOUBLESTAR__ at start
            regex = regex.replace("__DOUBLESTAR__/", "(?:.+/)?")
            # __DOUBLESTAR__ at end
            regex = regex.replace("/__DOUBLESTAR__", "(?:/.+)?")
            # __DOUBLESTAR__ alone (whole pattern)
            regex = regex.replace("__DOUBLESTAR__", ".*")
            if _re.match("^" + regex + "$", path):
                return True
        else:
            if fnmatch.fnmatchcase(path, g):
                return True
    return False


def check_scope(files, allowed, frozen):
    violations = []
    for raw_f in files:
        f = _normalize_path(raw_f)
        if not f or f == "." or f.startswith("/") or f == ".." or f.startswith("../"):
            violations.append(raw_f)
            continue
        if _match(f, frozen):
            violations.append(raw_f)
            continue
        if not _match(f, allowed):
            violations.append(raw_f)
    return (not violations, violations)


def main(argv):
    if len(argv) < 4:
        print(
            "Usage: validate_patch_scope.py <patch.diff> <allowed_csv> <frozen_csv>",
            file=sys.stderr,
        )
        return 2
    diff_text = pathlib.Path(argv[1]).read_text()
    allowed = [s for s in argv[2].split(",") if s]
    frozen = [s for s in argv[3].split(",") if s]
    files = extract_changed_files(diff_text)
    if diff_text.strip() and not files:
        print("SCOPE_VIOLATION: non-empty diff produced no parseable file paths", file=sys.stderr)
        return 1
    ok, violations = check_scope(files, allowed, frozen)
    if not ok:
        for v in violations:
            print(f"SCOPE_VIOLATION: {v}", file=sys.stderr)
        return 1
    for f in files:
        print(f)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
