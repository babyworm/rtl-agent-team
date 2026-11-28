#!/usr/bin/env python3
"""Print a native model ID for a RAT delegation, or nothing to inherit the session."""
import argparse
import json
from pathlib import Path
import re
import subprocess


PLUGIN = Path(__file__).resolve().parents[1]
AGENTS = PLUGIN / "agents" if (PLUGIN / "agents").is_dir() else PLUGIN / "runtime/roles"
TIERS = {
    "complex": ("fable", "astra"),
    "design": ("opus", "sol"),
    "straightforward": ("sonnet", "terra"),
    "trivial": ("haiku", "luna"),
}


def agent_tier(name):
    name = name.removeprefix("rtl-agent-team:")
    if not re.fullmatch(r"[a-z0-9-]+", name) or not (AGENTS / f"{name}.md").is_file():
        raise ValueError(f"Unknown RAT agent: {name}")
    header = (AGENTS / f"{name}.md").read_text().split("---", 2)[1]
    model = re.search(r"^model:\s*(\S+)\s*$", header, re.M)
    for tier, (alias, _) in TIERS.items():
        if model and model.group(1) == alias:
            return tier
    raise ValueError(f"Missing RAT role tier for {name}")


def catalog_output(host):
    command = [host, "debug", "models"] if host == "codex" else [host, "models"]
    try:
        return subprocess.run(command, check=True, capture_output=True, text=True,
                              stdin=subprocess.DEVNULL, timeout=8).stdout
    except (OSError, UnicodeError, subprocess.SubprocessError):
        return ""


def codex_model(catalog, family):
    try:
        models = json.loads(catalog)["models"]
    except (KeyError, ValueError, TypeError):
        return ""
    if not isinstance(models, list):
        return ""
    candidates = [
        item for item in models if isinstance(item, dict)
        and isinstance(item.get("slug"), str) and item["slug"].endswith("-" + family)
        and item.get("visibility", "list") == "list" and item.get("supported_in_api", True)
        and isinstance(item.get("priority"), int)
    ]
    return min(candidates, key=lambda item: item["priority"])["slug"] if candidates else ""


def agy_model(catalog, tier):
    # The first variant listed for a family is the host's catalog order.
    ids = re.findall(r"^(gemini-[\w.-]+)\t\S", catalog, re.M)
    preferences = {
        "complex": ("orchestrator", "neon", "carbon", "argon", "pro"),
        "design": ("neon", "carbon", "argon", "pro", "hydrogen"),
        "straightforward": ("hydrogen", "flash"),
        "trivial": ("flash", "hydrogen"),
    }
    for family in preferences[tier]:
        for model in ids:
            parts = model.split("-")
            if family in parts and ("orchestrator" not in parts or family == "orchestrator"):
                return model
    return ""


def grok_model(catalog, tier):
    ids = re.findall(r"^\s*[-*]\s+(grok-[\w.-]+)(?:\s|$)", catalog, re.M)
    if tier in {"straightforward", "trivial"}:
        for model in ids:
            if "fast" in model.split("-"):
                return model
    default = re.search(r"^Default model:\s*(\S+)", catalog, re.M)
    return default.group(1) if default and default.group(1) in ids else ""


def resolve(host, tier):
    alias, family = TIERS[tier]
    if host == "claude":
        return alias
    catalog = catalog_output(host)
    if host == "codex":
        return codex_model(catalog, family)
    if host == "agy":
        return agy_model(catalog, tier)
    return grok_model(catalog, tier)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True, choices=("claude", "codex", "agy", "grok"))
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--tier", choices=TIERS)
    source.add_argument("--agent", help="RAT agent name")
    parser.add_argument("--model", help="Explicit user-selected native model for this operation")
    args = parser.parse_args()
    if args.model:
        selected = args.model
        if args.host == "codex" and selected in {family for _, family in TIERS.values()}:
            selected = codex_model(catalog_output("codex"), args.model)
            if not selected:
                parser.error(f"No available Codex model for the requested family {args.model!r}")
        print(selected)
        return
    try:
        tier = args.tier or agent_tier(args.agent)
    except ValueError as error:
        parser.error(str(error))
    model = resolve(args.host, tier)
    if model:
        print(model)


if __name__ == "__main__":
    main()
