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
    for g in glob_list:
        if fnmatch.fnmatchcase(path, g):
            return True
        # support ** prefix style by substituting to * walks
        if "**" in g:
            simple = g.replace("**", "*")
            if fnmatch.fnmatchcase(path, simple):
                return True
            no_dstar = g.replace("**/", "")
            if fnmatch.fnmatchcase(path, no_dstar):
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
