#!/usr/bin/env python3
# rat-version: 1.0.0
"""Python compatibility level of the plugin's hooks and helpers.

This file parses under any Python, including Python 2, so that an old interpreter gets a clear
"unsupported" line instead of a SyntaxError. Every other plugin module may use the floor's
features. Python 2 is not supported.
"""
from __future__ import print_function

import sys

MIN_PYTHON = (3, 9)  # keep equal to RAT_PYTHON_MIN in hooks/lib/python-util.sh
TESTED = ((3, 9), (3, 14))  # oldest and newest versions in the CI test matrix
END_OF_LIFE = {(3, 9): "2025-10", (3, 10): "2026-10"}  # supported here, but past upstream support


def level(version=None):
    """unsupported, eol, supported or untested for a (major, minor[, ...]) version."""
    version = tuple((version or sys.version_info)[:2])
    if version < MIN_PYTHON:
        return "unsupported"
    if version > TESTED[1]:
        return "untested"
    if version in END_OF_LIFE:
        return "eol"
    return "supported"


def describe(version=None):
    version = tuple((version or sys.version_info)[:3])
    name = ".".join(str(part) for part in version)
    floor = ".".join(str(part) for part in MIN_PYTHON)
    newest = ".".join(str(part) for part in TESTED[1])
    found = level(version)
    if found == "unsupported":
        return "Python {0}: unsupported; the plugin needs Python >= {1}".format(name, floor)
    if found == "untested":
        return "Python {0}: newer than the tested range {1}-{2}; expected to work".format(name, floor, newest)
    if found == "eol":
        return ("Python {0}: supported, but upstream support ended {1}; a newer Python is recommended"
                .format(name, END_OF_LIFE[tuple(version[:2])]))
    return "Python {0}: supported (tested {1}-{2})".format(name, floor, newest)


def require():
    """Exit with a clear message when the running interpreter is below the floor."""
    if level() == "unsupported":
        print(describe() + " (" + sys.executable + ")", file=sys.stderr)
        raise SystemExit(2)


if __name__ == "__main__":
    print(describe() + " (" + sys.executable + ")")
    sys.exit(2 if level() == "unsupported" else 0)
