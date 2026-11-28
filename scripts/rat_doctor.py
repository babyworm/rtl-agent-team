#!/usr/bin/env python3
# rat-version: 1.0.0
"""Check plugin and project settings and print what is right (✓), unverified (?) or wrong (✗)."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import shlex
import shutil
import subprocess
import sys
import time

from eda_runner import available, backend, configuration, remote_shell_command, tool_configuration
from eda_setup import failed_probe, read_json, tool_fingerprint, validate_host
from verify_evidence import pre_init_state_root
import rat_compat

OK, WARN, FAIL, NA = "✓", "?", "✗", "–"
STALE_DAYS = 90
SETUP = "/rtl-agent-team:rat-setup"
# Legacy per-tool forwarding links (v0.14) make remote tools look local.
LICENSE_FREE = {"verilator", "iverilog", "verible", "verible-verilog-lint", "slang", "yosys", "sby", "svlens"}
FORWARDED = ("vcs", "xrun", "vsim", "dc_shell", "genus", "sg_shell", "fm_shell", "pt_shell", "pwr_shell", "urg", "verdi")


def add(rows, level, item, status, detail="", fix=""):
    rows.append({"level": level, "item": item, "status": status, "detail": detail, "fix": fix})


BAD_HOST = "is not a plain SSH alias or user@host"


def ssh_ok(execution, script="true"):
    """True or False for the remote script; None when the host is not a plain alias."""
    # Settings may come from a cloned project's rat_config.json: accept only a plain host,
    # end ssh options before it, ignore ssh_options (keep them in ~/.ssh/config), and pass
    # the script through the same tcsh-safe encoding as dispatch.
    try:
        validate_host(execution.get("host", ""))
    except ValueError:
        return None
    try:
        return subprocess.run(["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=8", "--", execution["host"],
                               remote_shell_command(script)], capture_output=True, timeout=20).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def tool_row(rows, label, config, name, category):
    _, entry = tool_configuration(config, name, category)
    probe = entry.get("probe") if isinstance(entry.get("probe"), dict) else {}
    if failed_probe(entry):
        add(rows, "project", label, FAIL, f"{name}: probe failed ({probe.get('failure') or 'error'})",
            f"{SETUP}: fix its environment and probe again")
        return
    try:
        is_avail = available(argparse.Namespace(tool=name, category=category), config) == 0
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        add(rows, "project", label, FAIL, f"{name}: availability check failed ({exc})",
            f"{SETUP}: fix its configuration and probe again")
        return
    if not is_avail:
        add(rows, "project", label, FAIL, f"{name}: not found", f"{SETUP}: install it or select an available tool")
    elif probe.get("configuration_sha256") not in (None, tool_fingerprint(entry)):
        add(rows, "project", label, WARN, f"{name}: probed before its path or environment changed", f"{SETUP}: probe again")
    elif probe.get("license_checked") or entry.get("setup_status") == "workload_passed":
        add(rows, "project", label, OK, f"{name}: licensed workload passed")
    elif probe.get("status") == "completed" and name in LICENSE_FREE:
        add(rows, "project", label, OK, f"{name}: runs (no license needed)")
    elif probe.get("status") == "completed":
        add(rows, "project", label, WARN, f"{name}: starts; license not checked", f"{SETUP}: run a licensed workload probe")
    else:
        add(rows, "project", label, WARN, f"{name}: found, never run", f"{SETUP}: probe it")


def plugin_checks(rows, live):
    plugin = Path(__file__).resolve().parents[1]
    version = json.loads((plugin / ".claude-plugin/plugin.json").read_text()).get("version", "?")
    add(rows, "plugin", "version", OK, f"{version} ({plugin})")
    found = rat_compat.level()
    floor = ".".join(map(str, rat_compat.MIN_PYTHON))
    add(rows, "plugin", "python", {"supported": OK, "unsupported": FAIL}.get(found, WARN),
        f"{rat_compat.describe()} ({sys.executable})",
        "" if found == "supported" else f"install Python >= {floor} and set RAT_PYTHON" if found == "unsupported"
        else "set RAT_PYTHON to a newer Python 3 if hooks misbehave" if found == "untested"
        else "install a newer Python 3 and set RAT_PYTHON to it")
    data = os.environ.get("RAT_DATA_DIR") or os.environ.get("CLAUDE_PLUGIN_DATA")
    if not data:
        add(rows, "plugin", "settings folder", FAIL, "RAT_DATA_DIR is not set in this shell",
            "restart Claude Code; the plugin's SessionStart hook sets it")
        return None
    add(rows, "plugin", "settings folder", OK, data)
    legacy = Path.home() / ".config/rtl-agent-team"
    if legacy.is_dir():
        add(rows, "plugin", "old settings folder", WARN, f"{legacy} is no longer read",
            f"move its env-config.json and sites/ into {data}")
    forwarders = [path for name in FORWARDED if (path := shutil.which(name)) and Path(path).resolve().name == "rat-ssh"]
    if forwarders:
        add(rows, "plugin", "legacy forwarders", WARN, ", ".join(forwarders) + " forward to rat-ssh and pose as local tools",
            "remove these links; remote execution no longer needs them")
    machine_path = Path(data) / "env-config.json"
    if not machine_path.is_file():
        add(rows, "plugin", "machine defaults", WARN, "no env-config.json; projects start with local tools", SETUP)
        return None
    try:
        machine = read_json(machine_path)
    except ValueError as exc:
        add(rows, "plugin", "machine defaults", FAIL, f"env-config.json is unreadable: {exc}", f"fix or remove {machine_path}")
        return None
    site = machine.get("default_site")
    if not site:
        add(rows, "plugin", "default site", NA, "none selected")
        return None
    if not isinstance(site, str) or not re.fullmatch(r"[A-Za-z0-9._-]+", site) or site in (".", ".."):
        add(rows, "plugin", "default site", FAIL, f"invalid default_site name: {site!r}", f"fix default_site in {machine_path}")
        return None
    profile_path = Path(data) / "sites" / f"{site}.json"
    if not profile_path.is_file():
        add(rows, "plugin", "default site", FAIL, f"{site}: profile {profile_path} is missing", f"{SETUP}: measure the site again")
        return None
    try:
        profile = read_json(profile_path)
    except (OSError, ValueError) as exc:
        add(rows, "plugin", "default site", FAIL, f"{site}: profile {profile_path} is unreadable: {exc}", f"{SETUP}: measure the site again")
        return None
    execution = profile.get("execution", {})
    days = (time.time() - float(profile.get("measured_at") or 0)) / 86400
    where = f"{site}: {execution.get('backend', 'local')} {execution.get('host', '')}".rstrip()
    if days > STALE_DAYS:
        add(rows, "plugin", "default site", WARN, f"{where}, measured {days:.0f} days ago", f"{SETUP}: measure the site again")
    else:
        add(rows, "plugin", "default site", OK, f"{where}, measured {days:.0f} days ago")
    if live and execution.get("host"):
        reached = ssh_ok(execution)
        if reached is None:
            add(rows, "plugin", "site connection", FAIL, f"{execution['host']!r} {BAD_HOST}",
                f"{SETUP}: keep SSH options in ~/.ssh/config and use its alias")
        else:
            add(rows, "plugin", "site connection", OK if reached else FAIL, f"ssh {execution['host']}",
                "" if reached else "check the VPN, SSH keys and ~/.ssh/config for this host")
    return profile


def project_checks(rows, root, profile, live):
    marker = next((name for name in (".rat", ".rtl-agent-team") if (root / name).is_dir()), None)
    if marker:
        add(rows, "project", "initialized", OK, f"{marker}/ present")
    else:
        records = pre_init_state_root(root) or root / ".rat"
        add(rows, "project", "initialized", NA, f"no; EDA settings still work and run records go to {records}",
            "/rtl-agent-team:rat-init-project when templates and phase tracking are needed")
    config_path = root / "rat_config.json"
    if config_path.is_file():
        try:
            read_json(config_path)
        except ValueError as exc:
            add(rows, "project", "rat_config.json", FAIL, f"unreadable: {exc}", f"fix {config_path}")
            return
        add(rows, "project", "rat_config.json", OK, "project settings")
    else:
        add(rows, "project", "rat_config.json", NA, "absent; machine defaults apply")
    try:
        config = configuration(root)
        selected = backend(config)
    except (OSError, ValueError) as exc:
        add(rows, "project", "effective settings", FAIL, str(exc), SETUP)
        return
    execution = config.get("execution", {})
    if selected in ("ssh", "lsf"):
        complete = execution.get("host") and Path(execution.get("workspace", "")).is_absolute()
        add(rows, "project", "execution", OK if complete else FAIL,
            f"{selected} {execution.get('host', '?')} workspace {execution.get('workspace', '?')}",
            "" if complete else f"{SETUP}: select a site for this project")
        mode = execution.get("results", "experiment")
        meaning = {"experiment": "only in experiment/<id>/", "merge": "at their usual paths; sources kept",
                   "sync": "at their usual paths; stale fetched files removed"}
        if mode not in meaning:
            add(rows, "project", "remote results", FAIL, f"execution.results={mode!r}",
                "set execution.results to experiment, merge or sync")
        elif mode != "experiment" and subprocess.run(["git", "-C", str(root), "rev-parse"], capture_output=True).returncode:
            add(rows, "project", "remote results", FAIL, f"{mode} needs a Git work tree to protect sources",
                "use experiment, or run inside a Git work tree")
        else:
            add(rows, "project", "remote results", OK, f"{mode}: results land {meaning[mode]}")
        site_host = (profile or {}).get("execution", {}).get("host")
        if config_path.is_file() and site_host and execution.get("host") != site_host:
            add(rows, "project", "default site", NA, f"project uses {execution.get('host')}, default site is {site_host}")
    else:
        add(rows, "project", "execution", OK, selected)
    for preference, category, needed in (("simulator", "simulators", True), ("synthesis", "synthesis", False),
                                         ("lint", "lint", False)):
        name, source = config.get("preferences", {}).get(preference), config
        if not name and profile:  # configure() leaves out a site tool that failed its probe; say why
            name, source = profile.get("preferences", {}).get(preference), profile
        if name:
            tool_row(rows, preference, source, name, category)
        else:
            add(rows, "project", preference, WARN if needed else NA, "not selected", SETUP if needed else "")
    db = config.get("technology", {}).get("db")
    if not db:
        add(rows, "project", "technology.db", WARN, "not set; synthesis needs a library",
            "set technology.db in rat_config.json or the site profile")
    elif selected not in ("ssh", "lsf"):
        found = Path(db).is_file()
        add(rows, "project", "technology.db", OK if found else FAIL, db, "" if found else "correct the library path")
    elif live:
        found = ssh_ok(execution, "test -f " + shlex.quote(db))
        if found is None:
            add(rows, "project", "technology.db", FAIL, f"host {execution.get('host')!r} {BAD_HOST}",
                "keep SSH options in ~/.ssh/config and use its alias as execution.host")
        else:
            add(rows, "project", "technology.db", OK if found else FAIL, f"{db} on {execution['host']}",
                "" if found else "correct the library path")
    else:
        add(rows, "project", "technology.db", WARN, f"{db} (remote, not checked)", "run the doctor with --live")


def table(rows):
    def cell(text):
        return str(text).replace("|", "\\|")
    lines = ["| Level | Check | Status | Detail | Fix |", "|---|---|:-:|---|---|"]
    lines += [f"| {r['level']} | {r['item']} | {r['status']} | {cell(r['detail'])} | {cell(r['fix'])} |" for r in rows]
    counts = {mark: sum(r["status"] == mark for r in rows) for mark in (OK, WARN, FAIL)}
    lines.append(f"\n{counts[OK]} {OK}  {counts[WARN]} {WARN}  {counts[FAIL]} {FAIL}")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--live", action="store_true", help="also test the SSH connection and remote library path")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    rows = []
    profile = plugin_checks(rows, args.live)
    project_checks(rows, Path(args.root).resolve(), profile, args.live)
    print(json.dumps(rows, ensure_ascii=False, indent=1) if args.json else table(rows))
    return 1 if any(row["status"] == FAIL for row in rows) else 0


if __name__ == "__main__":
    sys.exit(main())
