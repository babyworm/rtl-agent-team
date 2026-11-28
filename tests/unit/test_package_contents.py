import json
import os
import shutil
import subprocess
import sys

from tests.conftest import REPO_ROOT


def test_npm_package_excludes_runtime_state_and_python_cache():
    # Given: the npm artifact generated from the repository allowlist.
    result = subprocess.run(
        ["npm", "pack", "--dry-run", "--json", "--silent"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )

    # When: every packaged path is inspected.
    data = json.loads(result.stdout)
    package = data[0] if isinstance(data, list) else next(iter(data.values()))
    paths = [entry["path"] for entry in package["files"]]
    assert {".claude-plugin/plugin.json", "hooks/hooks.json",
            "evals/unit-mismatch/case.yaml", "evals/unit-mismatch/scaffold.sh"} <= set(paths)
    assert "plugin.json" not in paths  # Codex 0.172 loads this package's Claude-compatible hooks.

    # Then: local runtime state and Python caches never leave the workspace.
    assert not [
        path
        for path in paths
        if "/.omc/" in f"/{path}"
        or "/__pycache__/" in f"/{path}/"
        or path.endswith((".pyc", ".pyo"))
    ]


def test_npm_excludes_private_site_data_even_inside_packaged_directories(tmp_path):
    shutil.copy2(REPO_ROOT / "package.json", tmp_path / "package.json")
    public = tmp_path / "agents/example.md"
    public.parent.mkdir()
    public.write_text("A synthetic public agent.\n")
    protected = ["agents/.rat/report.json", "skills/example/sites/site.json",
                 "scripts/site-profiles/site.json", "runtime/private-reports/result.json",
                 "scripts/env-config.json", "skills/example/experiment/run-a/result.json"]
    for name in protected:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"host":"private-site.example.invalid"}')
    template = "skills/rat-init-project/templates/rat_config.json"
    path = tmp_path / template
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("{}")
    result = subprocess.run(["npm", "pack", "--dry-run", "--json", "--silent"],
                            cwd=tmp_path, check=True, capture_output=True, text=True)
    data = json.loads(result.stdout)
    package = data[0] if isinstance(data, list) else next(iter(data.values()))
    paths = {entry["path"] for entry in package["files"]}
    assert "agents/example.md" in paths
    assert template in paths
    assert not paths.intersection(protected)


def test_portable_export_keeps_role_resources_and_runs_init_from_another_project(tmp_path):
    package = tmp_path / "RAT skills"
    project = tmp_path / "RTL project"
    project.mkdir()
    exporter = REPO_ROOT / "scripts/package_portable_skills.py"
    subprocess.run([sys.executable, str(exporter), str(package)], check=True, cwd=project)

    portable = json.loads((package / "plugin.json").read_text())
    gemini = json.loads((package / "gemini-extension.json").read_text())
    claude = json.loads((REPO_ROOT / ".claude-plugin/plugin.json").read_text())
    assert portable["name"] == gemini["name"] == claude["name"]
    assert portable["version"] == gemini["version"] == claude["version"]
    assert "extensions" not in portable
    assert not (package / "hooks/hooks.json").exists()
    assert not (package / "agents").exists()
    exported_roles = {p.name for p in (package / "runtime/roles").glob("*.md")}
    assert exported_roles == {p.name for p in (REPO_ROOT / "agents").glob("*.md")}
    assert sorted(p.parent.name for p in package.glob("skills/*/SKILL.md")) == sorted(
        p.parent.name for p in REPO_ROOT.glob("skills/*/SKILL.md") if p.parent.name != "rtl-orchestrate"
    )

    skill = package / "skills/rat-init-project"
    preview = next(line for line in (skill / "SKILL.md").read_text().splitlines()
                   if line.startswith("bash ") and "--dry-run" in line)
    env = {key: value for key, value in os.environ.items() if not key.startswith("CLAUDE_")}
    env["RAT_INIT_SKILL_DIR"] = str(skill)
    subprocess.run(["bash", "-c", preview], cwd=project, env=env, check=True)
    assert list(project.iterdir()) == []
    result = subprocess.run([sys.executable, str(package / "scripts/resolve_agent_model.py"),
                             "--host", "claude", "--agent", "rtl-coder"],
                            cwd=project, text=True, capture_output=True, check=True)
    assert result.stdout.strip() == "opus"
