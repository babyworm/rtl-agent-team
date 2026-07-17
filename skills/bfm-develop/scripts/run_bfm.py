#!/usr/bin/env python3
"""run_bfm.py — build-and-run wrapper for the Phase 3 SystemC BFM.

Locates the bfm/ directory, picks a build system, honours SYSTEMC_HOME,
builds, runs the smoke flow, and writes a JSON run report. Stdlib-only.
Used by the bfm-develop skill to give agents one deterministic CLI for
"build the BFM and run its smoke test".

Build system resolution order:
  1. CMakeLists.txt -> `cmake -S . -B build` + `cmake --build build`
                       (cwd = bfm dir)
  2. Makefile       -> `make` (default target), cwd = bfm dir
  3. neither        -> exit 2

SYSTEMC_HOME contract: when the chosen build file references SYSTEMC_HOME
and the environment variable is not set, exit 2 with install guidance
BEFORE attempting the build — SystemC is a local prerequisite (see the
skill's Escalation rules). When set, the variable is passed through to the
build environment unchanged.

Run resolution order:
  1. Makefile with a `run:` target and no --args/--binary -> `make run`
     (cwd = bfm dir)
  2. otherwise -> execute the built binary directly (--binary override,
     else first executable under bfm/build — CMakeFiles/ excluded — else
     the bfm dir top level), with --args appended.

Report schema (commands as argv lists; paths recorded as given, never
resolved to absolute):
  tool, bfm_dir, build_system ("make"|"cmake"), systemc_home_referenced,
  systemc_home_set, build_cmds, build_cwd, built, build_exit_code,
  run_mode ("make-run"|"binary"), run_cmd, run_cwd, exit_code, stdout_tail,
  stderr_tail, output_files [{path, bytes}], duration_seconds.
output_files records the two documented BFM artifacts when present after
the run — smoke_test_result.txt and perf_baseline.json — searched in the
bfm dir and bfm/build, reported relative to the bfm dir.
Non-deterministic fields sync tests must exclude: duration_seconds,
systemc_home_set (host-dependent).

Usage:
    python3 run_bfm.py [--bfm-dir bfm] [--args "EXTRA ARGS"] [--binary NAME]
        [--report bfm_run_report.json]

Exit codes: 0 = build + run OK, 1 = build failed or run returned non-zero
(report still written), 2 = usage/environment error (no bfm dir, no build
system, missing cmake/make, SYSTEMC_HOME required but unset, no binary).
"""

import argparse
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

TAIL_LINES = 20
ARTIFACT_NAMES = ("smoke_test_result.txt", "perf_baseline.json")
RUN_TARGET_RE = re.compile(r"^run\s*:", re.MULTILINE)
NON_BINARY_SUFFIXES = {
    ".c", ".h", ".cpp", ".hpp", ".cc", ".o", ".so", ".a", ".d",
    ".sh", ".mk", ".cmake", ".txt", ".json", ".md", ".log",
}
NON_BINARY_NAMES = {"Makefile", "makefile", "GNUmakefile", "CMakeCache.txt"}


class RunnerError(Exception):
    """Environment/usage error — maps to exit code 2."""


def tail_lines(text):
    """Last TAIL_LINES lines of captured output, as a list."""
    return text.splitlines()[-TAIL_LINES:]


def is_runnable(path):
    """True for an executable regular file that is not a source/object file."""
    return (path.is_file()
            and os.access(path, os.X_OK)
            and path.suffix not in NON_BINARY_SUFFIXES
            and path.name not in NON_BINARY_NAMES)


def find_binary(bfm_dir):
    """Locate the built binary: bfm/build (recursive, CMakeFiles excluded),
    then the bfm dir top level."""
    build_dir = bfm_dir / "build"
    candidates = []
    if build_dir.is_dir():
        candidates = sorted(
            p for p in build_dir.rglob("*")
            if "CMakeFiles" not in p.parts and is_runnable(p))
    if not candidates:
        candidates = sorted(p for p in bfm_dir.iterdir() if is_runnable(p))
    if not candidates:
        return None
    if len(candidates) > 1:
        print(f"WARNING: multiple executables found: "
              f"{[c.name for c in candidates]} — using "
              f"'{candidates[0].name}' (pass --binary to override)",
              file=sys.stderr)
    return candidates[0]


def plan_build(bfm_dir, bfm_arg):
    """Return (build_system, build_file, build_cmds) or raise RunnerError."""
    cmake_file = bfm_dir / "CMakeLists.txt"
    if cmake_file.is_file():
        if not shutil.which("cmake"):
            raise RunnerError(
                f"CMakeLists.txt found at {bfm_arg} but 'cmake' is not on "
                "PATH — install cmake or provide a plain Makefile")
        return ("cmake", cmake_file,
                [["cmake", "-S", ".", "-B", "build"],
                 ["cmake", "--build", "build"]])
    for name in ("Makefile", "makefile", "GNUmakefile"):
        makefile = bfm_dir / name
        if makefile.is_file():
            if not shutil.which("make"):
                raise RunnerError(
                    f"{name} found at {bfm_arg} but 'make' is not on PATH — "
                    "install make")
            return "make", makefile, [["make"]]
    raise RunnerError(
        f"no CMakeLists.txt or Makefile in {bfm_arg} — nothing to build; "
        "run the bfm-develop skill to generate the BFM sources first")


def check_systemc_home(build_file):
    """Return (referenced, set). Raise RunnerError if referenced but unset.

    Comment-only mentions do not count: everything from the first '#' on
    each line is stripped before searching (Makefile and CMake comments).
    """
    code_text = "\n".join(
        line.split("#", 1)[0]
        for line in build_file.read_text(errors="replace").splitlines())
    referenced = "SYSTEMC_HOME" in code_text
    is_set = "SYSTEMC_HOME" in os.environ
    if referenced and not is_set:
        raise RunnerError(
            f"{build_file.name} references SYSTEMC_HOME but the environment "
            "variable is not set — install SystemC 3.0+ and "
            "`export SYSTEMC_HOME=/path/to/systemc` before running")
    return referenced, is_set


def collect_artifacts(bfm_dir):
    """Documented BFM artifacts present after the run, relative to bfm dir."""
    found = []
    for name in ARTIFACT_NAMES:
        for candidate in (bfm_dir / name, bfm_dir / "build" / name):
            if candidate.is_file():
                found.append({
                    "path": candidate.relative_to(bfm_dir).as_posix(),
                    "bytes": candidate.stat().st_size,
                })
                break
    return found


def write_report(report, report_path):
    out = Path(report_path)
    if out.parent != Path("."):
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Report written: {report_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build and run the Phase 3 SystemC BFM; write a JSON "
                    "run report.")
    parser.add_argument("--bfm-dir", default="bfm",
                        help="BFM directory (default: bfm)")
    parser.add_argument("--args", default="",
                        help="extra arguments appended to the BFM binary "
                             "command line (forces direct-binary run mode)")
    parser.add_argument("--binary",
                        help="BFM binary to run (absolute, or relative to "
                             "the bfm dir); skips auto-detection and "
                             "`make run`")
    parser.add_argument("--report", default="bfm_run_report.json",
                        help="run report path (default: bfm_run_report.json)")
    args = parser.parse_args(argv)

    start = time.monotonic()
    bfm_dir = Path(args.bfm_dir)
    if not bfm_dir.is_dir():
        print(f"ERROR: bfm directory not found: {args.bfm_dir} — pass "
              "--bfm-dir, or run from the project root (expected ./bfm)",
              file=sys.stderr)
        return 2

    try:
        build_system, build_file, build_cmds = plan_build(bfm_dir, args.bfm_dir)
        sysc_referenced, sysc_set = check_systemc_home(build_file)
    except RunnerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    report = {
        "tool": "run_bfm.py",
        "bfm_dir": args.bfm_dir,
        "build_system": build_system,
        "systemc_home_referenced": sysc_referenced,
        "systemc_home_set": sysc_set,
        "build_cmds": build_cmds,
        "build_cwd": args.bfm_dir,
        "built": False,
        "build_exit_code": 0,
        "run_mode": None,
        "run_cmd": None,
        "run_cwd": None,
        "exit_code": None,
        "stdout_tail": [],
        "stderr_tail": [],
        "output_files": [],
        "duration_seconds": None,
    }

    for cmd in build_cmds:
        proc = subprocess.run(cmd, cwd=bfm_dir, capture_output=True,
                              text=True, check=False)
        if proc.returncode != 0:
            report["build_exit_code"] = proc.returncode
            report["build_stdout_tail"] = tail_lines(proc.stdout)
            report["build_stderr_tail"] = tail_lines(proc.stderr)
            report["duration_seconds"] = round(time.monotonic() - start, 3)
            print(f"ERROR: build failed (exit {proc.returncode}): "
                  f"{' '.join(cmd)}", file=sys.stderr)
            if proc.stderr:
                print(proc.stderr.rstrip(), file=sys.stderr)
            write_report(report, args.report)
            return 1
    report["built"] = True

    has_run_target = (build_system == "make"
                      and RUN_TARGET_RE.search(
                          build_file.read_text(errors="replace")) is not None)
    if has_run_target and not args.args and not args.binary:
        run_mode = "make-run"
        run_cmd = ["make", "run"]
        run_cwd = args.bfm_dir
        proc = subprocess.run(run_cmd, cwd=bfm_dir, capture_output=True,
                              text=True, check=False)
    else:
        if args.binary:
            binary = Path(args.binary)
            if not binary.is_absolute():
                binary = bfm_dir / binary
            if not is_runnable(binary):
                print(f"ERROR: --binary {args.binary} is not an executable "
                      f"file (resolved: {binary})", file=sys.stderr)
                return 2
        else:
            binary = find_binary(bfm_dir)
            if binary is None:
                print(f"ERROR: no runnable binary found under "
                      f"{args.bfm_dir}/build or {args.bfm_dir} after build, "
                      "and no `run:` Makefile target — pass --binary",
                      file=sys.stderr)
                return 2
        run_mode = "binary"
        run_cmd = [binary.as_posix()] + shlex.split(args.args)
        run_cwd = "."
        proc = subprocess.run(run_cmd, capture_output=True, text=True,
                              check=False)

    report["run_mode"] = run_mode
    report["run_cmd"] = run_cmd
    report["run_cwd"] = run_cwd
    report["exit_code"] = proc.returncode
    report["stdout_tail"] = tail_lines(proc.stdout)
    report["stderr_tail"] = tail_lines(proc.stderr)
    report["output_files"] = collect_artifacts(bfm_dir)
    report["duration_seconds"] = round(time.monotonic() - start, 3)

    verdict = "PASS" if proc.returncode == 0 else "FAIL"
    print(f"Build: {build_system} OK")
    print(f"Run: {' '.join(run_cmd)} exit={proc.returncode} {verdict}")
    write_report(report, args.report)
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
