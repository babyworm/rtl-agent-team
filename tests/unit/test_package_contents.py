import json
import subprocess
import shutil

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
