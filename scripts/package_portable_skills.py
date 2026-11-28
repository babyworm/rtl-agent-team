#!/usr/bin/env python3
"""Export RAT skills and their runtime for Gemini CLI and Antigravity."""
import argparse
import json
from pathlib import Path
import shutil
import subprocess
import tempfile


ROOT = Path(__file__).resolve().parents[1]


def export(destination):
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"destination already exists: {destination}")
    # Reuse the release file list and private-site exclusions without installing
    # dependencies, contacting a registry, or running package lifecycle scripts.
    packed = subprocess.check_output(
        ["npm", "pack", "--dry-run", "--ignore-scripts", "--offline", "--json"],
        cwd=ROOT, text=True,
    )
    with tempfile.TemporaryDirectory(dir=destination.parent) as work:
        staged = Path(work) / "package"
        staged.mkdir()
        for entry in json.loads(packed)[0]["files"]:
            path = Path(entry["path"])
            # Host-specific lifecycle events and the SessionStart routing source
            # belong to the Claude package. Keep the shell/Python helpers.
            if path.parts[0] == "evals" or path in (
                Path("hooks/hooks.json"), Path("skills/rtl-orchestrate/SKILL.md"),
                Path(".claude-plugin/marketplace.json"),
            ):
                continue
            # These hosts scan agents/ as native definitions. The role prompts
            # are still used by RAT's generic delegation and model selection.
            target = (staged / "runtime/roles" / path.relative_to("agents")
                      if path.parts[0] == "agents" else staged / path)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ROOT / path, target)

        # Claude and Codex use the native marketplace in the full package.
        # Codex 0.172 ignores native hooks when it selects the portable root manifest.
        native = json.loads((staged / ".claude-plugin/plugin.json").read_text())
        manifest = {key: native[key] for key in ("name", "version", "repository", "license")}
        manifest.update({
            "$schema": "https://agent-plugins.org/schemas/1.0.0/plugin.schema.json",
            "description": "SystemVerilog RTL design and verification skills with simulation, synthesis, and CDC evidence.",
        })
        (staged / "plugin.json").write_text(json.dumps(manifest, indent=2) + "\n")
        gemini = {key: manifest[key] for key in ("name", "version", "description")}
        (staged / "gemini-extension.json").write_text(json.dumps(gemini, indent=2) + "\n")
        staged.rename(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path, help="new directory for the installable package")
    args = parser.parse_args()
    try:
        export(args.destination.absolute())
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
