import json
import subprocess

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
    paths = [entry["path"] for entry in json.loads(result.stdout)[0]["files"]]

    # Then: local runtime state and Python caches never leave the workspace.
    assert not [
        path
        for path in paths
        if "/.omc/" in f"/{path}"
        or "/__pycache__/" in f"/{path}/"
        or path.endswith((".pyc", ".pyo"))
    ]
