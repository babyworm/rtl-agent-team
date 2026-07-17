import json
import os
import stat
import subprocess
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT


PROJECT_INSTALLER = (
    REPO_ROOT
    / "skills"
    / "rat-init-project"
    / "scripts"
    / "install_project_templates.sh"
)
TOOL_RUNNER = (
    REPO_ROOT
    / "skills"
    / "rat-init-project"
    / "templates"
    / "lib"
    / "tool-runner.sh"
)
GENERATE_CONFIG = (
    REPO_ROOT
    / "skills"
    / "rat-init-project"
    / "scripts"
    / "generate_config.sh"
)


def _run_installer(workspace: Path, *, update: bool) -> subprocess.CompletedProcess[str]:
    command = ["bash", str(PROJECT_INSTALLER)]
    if update:
        command.append("--update")
    command.append(str(workspace))
    return subprocess.run(command, text=True, capture_output=True, check=False)


@pytest.mark.parametrize("update", [False, True])
def test_installer_rejects_symlink_destination_without_touching_target(
    tmp_path: Path, update: bool
) -> None:
    workspace = tmp_path / "project"
    destination = workspace / "syn" / "scripts" / "run_syn.sh"
    destination.parent.mkdir(parents=True)
    external_target = tmp_path / "external-run-syn.sh"
    original = "# rat-version: 0.0.1\nexternal target\n"
    external_target.write_text(original)
    destination.symlink_to(external_target)

    result = _run_installer(workspace, update=update)

    assert result.returncode != 0
    assert destination.is_symlink()
    assert external_target.read_text() == original


@pytest.mark.parametrize("update", [False, True])
def test_installer_rejects_parent_resolving_outside_workspace(
    tmp_path: Path, update: bool
) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    external_directory = tmp_path / "external-scripts"
    external_directory.mkdir()
    (workspace / "scripts").symlink_to(external_directory, target_is_directory=True)

    result = _run_installer(workspace, update=update)

    assert result.returncode != 0
    assert list(external_directory.iterdir()) == []


def test_installer_update_rejects_hard_link_without_touching_external_file(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "project"
    destination = workspace / "syn" / "scripts" / "run_syn.sh"
    destination.parent.mkdir(parents=True)
    external_target = tmp_path / "external-run-syn.sh"
    original = "# rat-version: 0.0.1\nexternal target\n"
    external_target.write_text(original)
    destination.hardlink_to(external_target)

    result = _run_installer(workspace, update=True)

    assert result.returncode != 0
    assert destination.stat().st_ino == external_target.stat().st_ino
    assert external_target.read_text() == original


def test_installer_updates_deployed_legacy_tool_runner(tmp_path: Path) -> None:
    workspace = tmp_path / "project"
    workspace.mkdir()
    deployed = workspace / "lib" / "tool-runner.sh"
    deployed.parent.mkdir()
    deployed.write_text("#!/bin/sh\n# rat-version: 0.8.16\nlegacy runner\n")

    result = _run_installer(workspace, update=True)

    assert result.returncode == 0, result.stderr
    assert "# rat-version: 0.14.1" in deployed.read_text()
    assert "legacy runner" not in deployed.read_text()


def _fake_docker(
    tmp_path: Path, *, containers_exist: bool = True
) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log = tmp_path / "docker.log"
    docker = bin_dir / "docker"
    ps_response = (
        '[ "${1:-}" != ps ] || printf \'container-id\\n\'\n'
        if containers_exist
        else ""
    )
    docker.write_text(
        "#!/bin/sh\n"
        "printf '%s\\n' \"$*\" >> \"$DOCKER_LOG\"\n"
        "case \"${1:-}\" in\n"
        "  ps) [ \"${DOCKER_PS_RC:-0}\" -eq 0 ] || exit \"$DOCKER_PS_RC\" ;;\n"
        "  inspect) printf '%s\\n' \"${DOCKER_OWNER:-$(pwd -P)}\"; "
        "exit \"${DOCKER_INSPECT_RC:-0}\" ;;\n"
        "  stop) exit \"${DOCKER_STOP_RC:-0}\" ;;\n"
        "  rm) exit \"${DOCKER_RM_RC:-0}\" ;;\n"
        "esac\n"
        f"{ps_response}"
    )
    docker.chmod(0o755)
    return bin_dir, log


def _container_name(project: Path) -> str:
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; _tool_runner_container_name',
            "_",
            str(TOOL_RUNNER),
        ],
        cwd=project,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def test_container_name_distinguishes_same_basename_physical_workspaces(
    tmp_path: Path,
) -> None:
    first = tmp_path / "owner-a" / "same-project"
    second = tmp_path / "owner-b" / "same-project"
    first.mkdir(parents=True)
    second.mkdir(parents=True)

    first_name = _container_name(first)
    second_name = _container_name(second)

    assert first_name != second_name
    assert all(len(name) <= 63 for name in (first_name, second_name))
    assert all(name.replace("-", "").isalnum() for name in (first_name, second_name))


@pytest.mark.parametrize("use_project_root_override", [False, True])
def test_container_setup_keeps_project_root_after_working_directory_change(
    tmp_path: Path, use_project_root_override: bool
) -> None:
    project = tmp_path / "project"
    output = project / "lint" / "lint"
    output.mkdir(parents=True)
    driver = tmp_path / "driver"
    driver.mkdir()
    source_cwd = driver if use_project_root_override else project
    bin_dir, log = _fake_docker(tmp_path, containers_exist=False)
    env = os.environ | {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "DOCKER_LOG": str(log),
    }
    if use_project_root_override:
        env["RAT_PROJECT_ROOT"] = str(project)

    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; cd "$2"; _tool_runner_ensure_container',
            "_",
            str(TOOL_RUNNER),
            str(output),
        ],
        cwd=source_cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    calls = log.read_text().splitlines()
    run_call = next(call for call in calls if call.startswith("run "))
    assert f"type=bind,src={project},dst=/workspace" in run_call
    assert f"rtl-agent-team.project-root={project}" in run_call
    assert (project / ".rat" / "state" / "docker-container.txt").is_file()
    assert not (output / ".rat").exists()


def test_container_setup_rejects_existing_container_owned_by_another_project(
    tmp_path: Path,
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    bin_dir, log = _fake_docker(tmp_path)

    result = subprocess.run(
        ["bash", "-c", 'source "$1"; _tool_runner_ensure_container', "_", str(TOOL_RUNNER)],
        cwd=project,
        env=os.environ
        | {
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "DOCKER_LOG": str(log),
            "DOCKER_OWNER": str(tmp_path / "foreign-project"),
        },
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    calls = log.read_text().splitlines()
    assert any(call.startswith("inspect ") for call in calls)
    assert not any(call.startswith(("start ", "run ")) for call in calls)


@pytest.mark.parametrize("name_source", ["memory", "state"])
def test_cleanup_never_removes_mismatched_container_name(
    tmp_path: Path, name_source: str
) -> None:
    project = tmp_path / "safe-project"
    state_file = project / ".rat" / "state" / "docker-container.txt"
    project.mkdir()
    bin_dir, log = _fake_docker(tmp_path)
    setup = "_TOOL_RUNNER_CONTAINER=foreign-container"
    if name_source == "state":
        state_file.parent.mkdir(parents=True)
        state_file.write_text("foreign-container\n")
        setup = "_TOOL_RUNNER_CONTAINER="

    result = subprocess.run(
        [
            "bash",
            "-c",
            f'source "$1"; {setup}; tool_runner_cleanup',
            "_",
            str(TOOL_RUNNER),
        ],
        cwd=project,
        env=os.environ
        | {"PATH": f"{bin_dir}:{os.environ['PATH']}", "DOCKER_LOG": str(log)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    calls = log.read_text().splitlines() if log.exists() else []
    assert not any(call.startswith(("stop ", "rm ")) for call in calls)
    assert all("foreign-container" not in call for call in calls)


def test_cleanup_without_ownership_evidence_does_not_query_or_remove_docker(
    tmp_path: Path,
) -> None:
    project = tmp_path / "safe-project"
    project.mkdir()
    bin_dir, log = _fake_docker(tmp_path)

    result = subprocess.run(
        ["bash", "-c", 'source "$1"; tool_runner_cleanup', "_", str(TOOL_RUNNER)],
        cwd=project,
        env=os.environ
        | {"PATH": f"{bin_dir}:{os.environ['PATH']}", "DOCKER_LOG": str(log)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert not log.exists()


def test_cleanup_removes_exact_derived_container(tmp_path: Path) -> None:
    project = tmp_path / "safe-project"
    state_file = project / ".rat" / "state" / "docker-container.txt"
    state_file.parent.mkdir(parents=True)
    container_name = _container_name(project)
    state_file.write_text(f"{container_name}\n")
    bin_dir, log = _fake_docker(tmp_path)

    result = subprocess.run(
        ["bash", "-c", 'source "$1"; tool_runner_cleanup', "_", str(TOOL_RUNNER)],
        cwd=project,
        env=os.environ
        | {"PATH": f"{bin_dir}:{os.environ['PATH']}", "DOCKER_LOG": str(log)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    calls = log.read_text().splitlines()
    assert f"stop {container_name}" in calls
    assert f"rm {container_name}" in calls
    assert not state_file.exists()


@pytest.mark.parametrize(
    ("failure_env", "expected_call", "forbidden_call"),
    [
        ({"DOCKER_PS_RC": "17"}, "ps ", "stop "),
        ({"DOCKER_STOP_RC": "18"}, "stop ", "rm "),
        ({"DOCKER_RM_RC": "19"}, "rm ", "never-matches "),
    ],
)
def test_cleanup_preserves_state_when_docker_cleanup_fails(
    tmp_path: Path,
    failure_env: dict[str, str],
    expected_call: str,
    forbidden_call: str,
) -> None:
    project = tmp_path / "safe-project"
    state_file = project / ".rat" / "state" / "docker-container.txt"
    state_file.parent.mkdir(parents=True)
    container_name = _container_name(project)
    state_file.write_text(f"{container_name}\n")
    bin_dir, log = _fake_docker(tmp_path)

    result = subprocess.run(
        ["bash", "-c", 'source "$1"; tool_runner_cleanup', "_", str(TOOL_RUNNER)],
        cwd=project,
        env=os.environ
        | {
            "PATH": f"{bin_dir}:{os.environ['PATH']}",
            "DOCKER_LOG": str(log),
            "DOCKER_OWNER": str(project),
        }
        | failure_env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode != 0
    assert state_file.read_text() == f"{container_name}\n"
    calls = log.read_text().splitlines()
    assert any(call.startswith(expected_call) for call in calls)
    assert not any(call.startswith(forbidden_call) for call in calls)


@pytest.mark.parametrize(
    "destination_kind",
    ["parent_symlink", "parent_file", "leaf_symlink", "leaf_directory", "leaf_hardlink"],
)
def test_container_setup_rejects_unsafe_state_destination_before_docker(
    tmp_path: Path, destination_kind: str
) -> None:
    project = tmp_path / "safe-project"
    project.mkdir()
    state_file = project / ".rat" / "state" / "docker-container.txt"
    external = tmp_path / "external"
    external.mkdir()
    external_file = external / "docker-container.txt"
    original = "external state\n"

    if destination_kind == "parent_symlink":
        (project / ".rat").symlink_to(external, target_is_directory=True)
    elif destination_kind == "parent_file":
        (project / ".rat").write_text(original)
    else:
        state_file.parent.mkdir(parents=True)
        if destination_kind == "leaf_symlink":
            external_file.write_text(original)
            state_file.symlink_to(external_file)
        elif destination_kind == "leaf_directory":
            state_file.mkdir()
        else:
            external_file.write_text(original)
            state_file.hardlink_to(external_file)

    bin_dir, log = _fake_docker(tmp_path, containers_exist=False)
    result = subprocess.run(
        [
            "bash",
            "-c",
            'source "$1"; _tool_runner_ensure_container',
            "_",
            str(TOOL_RUNNER),
        ],
        cwd=project,
        env=os.environ
        | {"PATH": f"{bin_dir}:{os.environ['PATH']}", "DOCKER_LOG": str(log)},
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert result.returncode != 0
    assert not log.exists()
    if external_file.exists():
        assert external_file.read_text() == original


def _minimal_config() -> dict[str, object]:
    return {
        "preferences": {},
        "technology": {},
        "coverage": {"seeds": "42"},
    }


@pytest.mark.parametrize("destination_name", ["rat_config.json", "config.mk"])
@pytest.mark.parametrize("destination_kind", ["directory", "symlink", "fifo"])
def test_config_generation_rejects_non_regular_managed_destination_before_writes(
    tmp_path: Path, destination_name: str, destination_kind: str
) -> None:
    project = tmp_path / "project"
    project.mkdir()
    config = project / "rat_config.json"
    config_mk = project / "config.mk"
    config.write_text(json.dumps(_minimal_config()))
    config_mk.write_text("# preserve config.mk\n")
    protected = config if destination_name == "rat_config.json" else config_mk
    other = config_mk if protected == config else config
    other_original = other.read_bytes()
    protected.unlink()
    external_target = tmp_path / f"external-{destination_name}"
    external_original = (
        json.dumps(_minimal_config())
        if destination_name == "rat_config.json"
        else "external target\n"
    )

    if destination_kind == "directory":
        protected.mkdir()
    elif destination_kind == "symlink":
        external_target.write_text(external_original)
        protected.symlink_to(external_target)
    else:
        os.mkfifo(protected)

    result = subprocess.run(
        ["bash", str(GENERATE_CONFIG), str(project), "safe-project"],
        text=True,
        capture_output=True,
        check=False,
        timeout=10,
    )

    assert result.returncode != 0
    assert "EDA Tool Detection" not in result.stdout
    assert other.read_bytes() == other_original
    if destination_kind == "directory":
        assert protected.is_dir()
        assert list(protected.iterdir()) == []
    elif destination_kind == "symlink":
        assert protected.is_symlink()
        assert external_target.read_text() == external_original
    else:
        assert stat.S_ISFIFO(protected.stat().st_mode)
