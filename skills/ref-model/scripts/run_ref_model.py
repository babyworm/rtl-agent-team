#!/usr/bin/env python3
"""run_ref_model.py — build-and-run wrapper for the Phase 2 C reference model.

Locates the refc/ directory, builds the model (existing Makefile preferred,
direct C11 compile fallback), runs the model binary, and writes a JSON run
report. Stdlib-only — no external dependencies. Used by the ref-model skill
to give agents one deterministic CLI for "build the golden model and run it".

Build resolution order:
  1. Makefile in the refc dir -> `make` (default target), cwd = refc dir
  2. otherwise                -> direct compile of refc/*.c (+ refc/src/*.c)
                                 with $CC/cc/gcc/clang -std=c11 -Wall -Wextra
                                 into refc/build/ref_model

Run resolution order:
  1. --binary PATH (absolute, or relative to the refc dir)
  2. first executable under refc/build/ (sorted, sources/objects excluded)
  3. first executable at the refc dir top level (sorted)

The model binary is executed from the invoking CWD (not the refc dir) so
that --input/--output paths behave exactly as the caller wrote them.

Report schema (commands as argv lists; paths recorded as given, never
resolved to absolute):
  tool, refc_dir, build_mode ("make"|"cc"), build_cmds, build_cwd, built,
  build_exit_code, run_mode, run_cmd, run_cwd, exit_code, stdout_tail,
  stderr_tail, output_files [{path, bytes}], duration_seconds.
On a deterministic model invoked with relative paths, `duration_seconds` is
the only non-deterministic field — sync tests must exclude it.

Usage:
    python3 run_ref_model.py [--refc-dir refc] [--input FILE] [--output FILE]
        [--args "EXTRA ARGS"] [--binary NAME] [--report refc_run_report.json]

Exit codes: 0 = build + run OK (model exited 0), 1 = build failed or model
returned non-zero (report still written), 2 = usage/environment error
(no refc dir, no compiler/make, no runnable binary).
"""

import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

TAIL_LINES = 20
CC_FLAGS = ["-std=c11", "-O2", "-Wall", "-Wextra"]
CC_BINARY_NAME = "ref_model"
NON_BINARY_SUFFIXES = {
    ".c", ".h", ".cpp", ".hpp", ".o", ".so", ".a", ".d",
    ".sh", ".mk", ".txt", ".json", ".md", ".log",
}
NON_BINARY_NAMES = {"Makefile", "makefile", "GNUmakefile"}


class RunnerError(Exception):
    """Environment/usage error — maps to exit code 2."""


def tail_lines(text):
    """Last TAIL_LINES lines of captured output, as a list."""
    return text.splitlines()[-TAIL_LINES:]


def find_compiler():
    """First available C compiler: $CC, then cc, gcc, clang."""
    for cand in (os.environ.get("CC"), "cc", "gcc", "clang"):
        if cand and shutil.which(cand):
            return cand
    return None


def is_runnable(path):
    """True for an executable regular file that is not a source/object file."""
    return (path.is_file()
            and os.access(path, os.X_OK)
            and path.suffix not in NON_BINARY_SUFFIXES
            and path.name not in NON_BINARY_NAMES)


def find_binary(refc_dir):
    """Locate the built model binary under build/ first, then the dir root."""
    for search_dir in (refc_dir / "build", refc_dir):
        if not search_dir.is_dir():
            continue
        candidates = sorted(p for p in search_dir.iterdir() if is_runnable(p))
        if candidates:
            if len(candidates) > 1:
                print(f"WARNING: multiple executables in {search_dir}: "
                      f"{[c.name for c in candidates]} — using "
                      f"'{candidates[0].name}' (pass --binary to override)",
                      file=sys.stderr)
            return candidates[0]
    return None


def plan_build(refc_dir, refc_arg):
    """Return (build_mode, build_cmds) or raise RunnerError."""
    has_makefile = any((refc_dir / n).is_file() for n in NON_BINARY_NAMES)
    if has_makefile:
        if not shutil.which("make"):
            raise RunnerError(
                f"Makefile found at {refc_arg} but 'make' is not on PATH — "
                "install make, or remove the Makefile to use the direct-cc "
                "fallback")
        return "make", [["make"]]

    cc = find_compiler()
    if cc is None:
        raise RunnerError(
            f"no Makefile at {refc_arg} and no C compiler found "
            "(checked $CC, cc, gcc, clang) — install gcc/clang, or provide "
            "a refc Makefile, or pass a prebuilt binary via --binary")
    sources = sorted(refc_dir.glob("*.c")) + sorted((refc_dir / "src").glob("*.c"))
    if not sources:
        raise RunnerError(
            f"no Makefile and no C sources (*.c or src/*.c) in {refc_arg} — "
            "nothing to build")
    cmd = [cc, *CC_FLAGS]
    if (refc_dir / "include").is_dir():
        cmd.append("-Iinclude")
    cmd += ["-o", f"build/{CC_BINARY_NAME}"]
    cmd += [s.relative_to(refc_dir).as_posix() for s in sources]
    return "cc", [cmd]


def write_report(report, report_path):
    out = Path(report_path)
    if out.parent != Path("."):
        out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Report written: {report_path}")


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Build and run the Phase 2 C reference model; write a "
                    "JSON run report.")
    parser.add_argument("--refc-dir", default="refc",
                        help="reference model directory (default: refc)")
    parser.add_argument("--input",
                        help="input file passed to the model as '--input FILE'")
    parser.add_argument("--output",
                        help="output file passed to the model as "
                             "'--output FILE'; recorded in output_files")
    parser.add_argument("--args", default="",
                        help="extra arguments appended to the model command "
                             "line (shell-quoted string)")
    parser.add_argument("--binary",
                        help="model binary to run (absolute, or relative to "
                             "the refc dir); skips auto-detection")
    parser.add_argument("--report", default="refc_run_report.json",
                        help="run report path (default: refc_run_report.json)")
    args = parser.parse_args(argv)

    start = time.monotonic()
    refc_dir = Path(args.refc_dir)
    if not refc_dir.is_dir():
        print(f"ERROR: refc directory not found: {args.refc_dir} — pass "
              "--refc-dir, or run from the project root (expected ./refc)",
              file=sys.stderr)
        return 2

    try:
        build_mode, build_cmds = plan_build(refc_dir, args.refc_dir)
    except RunnerError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    report = {
        "tool": "run_ref_model.py",
        "refc_dir": args.refc_dir,
        "build_mode": build_mode,
        "build_cmds": build_cmds,
        "build_cwd": args.refc_dir,
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

    if build_mode == "cc":
        (refc_dir / "build").mkdir(exist_ok=True)
    for cmd in build_cmds:
        proc = subprocess.run(cmd, cwd=refc_dir, capture_output=True,
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

    if args.binary:
        binary = Path(args.binary)
        if not binary.is_absolute():
            binary = refc_dir / binary
        if not is_runnable(binary):
            print(f"ERROR: --binary {args.binary} is not an executable file "
                  f"(resolved: {binary})", file=sys.stderr)
            return 2
    else:
        binary = find_binary(refc_dir)
        if binary is None:
            print(f"ERROR: no runnable binary found under {args.refc_dir}/build "
                  f"or {args.refc_dir} after build — pass --binary",
                  file=sys.stderr)
            return 2

    run_cmd = [binary.as_posix()]
    if args.input:
        run_cmd += ["--input", args.input]
    if args.output:
        run_cmd += ["--output", args.output]
    run_cmd += shlex.split(args.args)

    proc = subprocess.run(run_cmd, capture_output=True, text=True, check=False)
    report["run_mode"] = "binary"
    report["run_cmd"] = run_cmd
    report["run_cwd"] = "."
    report["exit_code"] = proc.returncode
    report["stdout_tail"] = tail_lines(proc.stdout)
    report["stderr_tail"] = tail_lines(proc.stderr)
    if args.output and Path(args.output).is_file():
        report["output_files"].append(
            {"path": args.output, "bytes": Path(args.output).stat().st_size})
    report["duration_seconds"] = round(time.monotonic() - start, 3)

    verdict = "PASS" if proc.returncode == 0 else "FAIL"
    print(f"Build: {build_mode} OK")
    print(f"Run: {' '.join(run_cmd)} exit={proc.returncode} {verdict}")
    write_report(report, args.report)
    return 0 if proc.returncode == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
