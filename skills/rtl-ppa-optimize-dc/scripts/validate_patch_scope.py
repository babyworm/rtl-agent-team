#!/usr/bin/env python3
"""Validate that a unified diff only touches allowed scope, never frozen scope.

Invocation:
    validate_patch_scope.py <patch.diff> <allowed_globs_csv> <frozen_globs_csv>

Exit 0 when patch is within scope; non-zero on violation (paths printed to stderr).
"""
from __future__ import annotations

import fnmatch
import pathlib
import re
import sys


DIFF_FILE_RE = re.compile(r"^diff --git a/(\S+) b/\S+", re.MULTILINE)


def extract_changed_files(diff_text):
    return DIFF_FILE_RE.findall(diff_text)


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
                    # fnmatch.translate wraps in (?s:...)\Z — strip that wrapper
                    translated = translated.replace(r"\Z", "").replace(r"(?s:", "").rstrip(")")
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
    for f in files:
        if _match(f, frozen):
            violations.append(f)
            continue
        if not _match(f, allowed):
            violations.append(f)
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
