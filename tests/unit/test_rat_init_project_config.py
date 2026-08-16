import json
import os
import subprocess
from pathlib import Path

import pytest

from tests.conftest import REPO_ROOT, find_bash4


GENERATE_CONFIG = REPO_ROOT / "skills" / "rat-init-project" / "scripts" / "generate_config.sh"

# generate_config.sh self-guards on `BASH_VERSINFO[0] >= 4`; macOS ships bash 3.2.
BASH4 = find_bash4()
pytestmark = pytest.mark.skipif(
    BASH4 is None,
    reason="generate_config.sh requires bash >= 4 (macOS ships 3.2 — `brew install bash`)",
)


def _minimal_config():
    return {
        "preferences": {
            "simulator": "iverilog",
            "synthesis": "yosys",
            "lint": "verible",
            "formal": "sby",
            "cdc": "structural",
            "equivalence": "lec",
        },
        "technology": {
            "target": "",
            "liberty": "",
            "sram_lib": "",
            "nand2_cell_pattern": "NAND2X1",
            "nand2_area_um2": None,
        },
        "coverage": {"seeds": "7 11 13"},
    }


def _run_generator(project: Path, *, env: dict[str, str] | None = None):
    return subprocess.run(
        [BASH4, str(GENERATE_CONFIG), str(project), "generated-name"],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture(scope="module")
def regenerated_config(tmp_path_factory: pytest.TempPathFactory):
    # Given: a project config containing distinct user-owned values.
    project = tmp_path_factory.mktemp("rat-init-project")
    fake_yosys = project / "custom-tools" / "yosys"
    fake_yosys.parent.mkdir()
    fake_yosys.write_text("#!/bin/sh\nexit 0\n")
    fake_yosys.chmod(0o755)
    path_dc_shell = project / "path-tools" / "dc_shell"
    path_dc_shell.parent.mkdir()
    path_dc_shell.write_text("#!/bin/sh\nexit 0\n")
    path_dc_shell.chmod(0o755)
    liberty = project / "libs" / "user.lib"
    liberty.parent.mkdir()
    liberty.write_text("cell (USER_NAND2) {\n  area : 2.500;\n}\n")

    original = {
        "project": {
            "name": "user-project",
            "top_module": "user_top",
            "filelist": "rtl/user_files.f",
        },
        "tools": {
            "synthesis": {
                "yosys": {
                    "detected": False,
                    "path": str(fake_yosys),
                    "env_source": "",
                },
                "dc_shell": {
                    "detected": False,
                    "path": "/stale/non-executable/dc_shell",
                    "env_source": "",
                },
            }
        },
        "preferences": {
            "simulator": "iverilog",
            "synthesis": "yosys",
            "lint": "verible",
            "formal": "sby",
            "cdc": "structural",
            "equivalence": "lec",
        },
        "technology": {
            "target": "user-process",
            "liberty": "libs/user.lib",
            "sram_lib": "libs/user-sram.lib",
            "nand2_cell_pattern": "USER_NAND2",
            "nand2_area_um2": 1.75,
        },
        "coverage": {
            "targets": {
                "line": 91,
                "toggle": 82,
                "fsm": 73,
                "branch": 84,
                "functional": 96,
            },
            "seeds": "7 11 13",
            "max_fail_rate": 2,
        },
        "waivers": {
            "verilator": "waivers/verilator.vlt",
            "verible": "waivers/verible.rules",
            "spyglass_lint": "waivers/spyglass-lint.awl",
            "spyglass_cdc": "waivers/spyglass-cdc.awl",
            "cdc": "waivers/cdc.rules",
        },
    }
    (project / "rat_config.json").write_text(json.dumps(original))

    # When: the project config generator runs again.
    env = os.environ | {"PATH": f"{path_dc_shell.parent}:{os.environ['PATH']}"}
    subprocess.run(
        [BASH4, str(GENERATE_CONFIG), str(project), "generated-name"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    return json.loads((project / "rat_config.json").read_text()), fake_yosys, path_dc_shell


@pytest.mark.parametrize(
    ("field_path", "expected"),
    [
        (("project", "name"), "user-project"),
        (("project", "top_module"), "user_top"),
        (("project", "filelist"), "rtl/user_files.f"),
        (("preferences", "simulator"), "iverilog"),
        (("preferences", "synthesis"), "yosys"),
        (("preferences", "lint"), "verible"),
        (("preferences", "formal"), "sby"),
        (("preferences", "cdc"), "structural"),
        (("preferences", "equivalence"), "lec"),
        (("technology", "target"), "user-process"),
        (("technology", "liberty"), "libs/user.lib"),
        (("technology", "sram_lib"), "libs/user-sram.lib"),
        (("technology", "nand2_cell_pattern"), "USER_NAND2"),
        (("coverage", "targets", "line"), 91),
        (("coverage", "targets", "toggle"), 82),
        (("coverage", "targets", "fsm"), 73),
        (("coverage", "targets", "branch"), 84),
        (("coverage", "targets", "functional"), 96),
        (("coverage", "seeds"), "7 11 13"),
        (("coverage", "max_fail_rate"), 2),
        (("waivers", "verilator"), "waivers/verilator.vlt"),
        (("waivers", "verible"), "waivers/verible.rules"),
        (("waivers", "spyglass_lint"), "waivers/spyglass-lint.awl"),
        (("waivers", "spyglass_cdc"), "waivers/spyglass-cdc.awl"),
        (("waivers", "cdc"), "waivers/cdc.rules"),
    ],
)
def test_rerun_preserves_user_owned_field(regenerated_config, field_path, expected):
    config, _fake_yosys, _path_dc_shell = regenerated_config
    value = config
    for key in field_path:
        value = value[key]

    # Then: the selected user-owned field is unchanged.
    assert value == expected


def test_rerun_preserves_absolute_tool_path_without_env_source(regenerated_config):
    config, fake_yosys, _path_dc_shell = regenerated_config

    # Then: an executable absolute override remains the selected tool path.
    saved_path = Path(config["tools"]["synthesis"]["yosys"]["path"])
    assert saved_path == fake_yosys
    assert config["tools"]["synthesis"]["yosys"]["env_source"] == ""


def test_rerun_refreshes_stale_tool_path_from_path(regenerated_config):
    config, _fake_yosys, path_dc_shell = regenerated_config

    # Then: an unusable saved path is replaced by the executable found on PATH.
    saved_tool = config["tools"]["synthesis"]["dc_shell"]
    assert Path(saved_tool["path"]) == path_dc_shell
    assert saved_tool["detected"] is True


def test_rerun_ignores_executable_directory_as_saved_tool_path(tmp_path: Path):
    # Given: a searchable directory saved as a tool override and a real tool on PATH.
    project = tmp_path / "project"
    project.mkdir()
    saved_directory = project / "not-a-yosys-binary"
    saved_directory.mkdir()
    path_tools = project / "path-tools"
    path_tools.mkdir()
    path_yosys = path_tools / "yosys"
    path_yosys.write_text("#!/bin/sh\nexit 0\n")
    path_yosys.chmod(0o755)
    config = _minimal_config()
    config["tools"] = {
        "synthesis": {
            "yosys": {
                "detected": False,
                "path": str(saved_directory),
                "env_source": "",
            }
        }
    }
    (project / "rat_config.json").write_text(json.dumps(config))

    # When: the generator refreshes tool detection.
    env = os.environ | {"PATH": f"{path_tools}:{os.environ['PATH']}"}
    result = _run_generator(project, env=env)

    # Then: it ignores the directory and records the executable file from PATH.
    assert result.returncode == 0, result.stderr
    generated = json.loads((project / "rat_config.json").read_text())
    saved_tool = generated["tools"]["synthesis"]["yosys"]
    assert saved_tool["path"] == str(path_yosys)
    assert saved_tool["detected"] is True


def test_rerun_recomputes_nand2_area_from_current_liberty(regenerated_config):
    config, _fake_yosys, _path_dc_shell = regenerated_config

    # Then: the derived area reflects the current Liberty rather than the saved value.
    assert config["technology"]["nand2_area_um2"] == 2.5


def test_rerun_preserves_mode_without_gnu_chmod_reference(tmp_path: Path):
    # Given: managed files with restrictive modes and a chmod that rejects GNU flags.
    project = tmp_path / "project"
    project.mkdir()
    config_path = project / "rat_config.json"
    config_path.write_text(json.dumps(_minimal_config()))
    config_path.chmod(0o640)
    config_mk = project / "config.mk"
    config_mk.write_text("# existing\n")
    config_mk.chmod(0o640)
    shim_dir = tmp_path / "shim"
    shim_dir.mkdir()
    chmod_shim = shim_dir / "chmod"
    chmod_shim.write_text(
        "#!/bin/sh\n"
        "case \"${1:-}\" in --reference*) exit 91 ;; esac\n"
        "exec /bin/chmod \"$@\"\n"
    )
    chmod_shim.chmod(0o755)

    # When: the generator runs with only portable chmod behavior available.
    env = os.environ | {"PATH": f"{shim_dir}:{os.environ['PATH']}"}
    result = _run_generator(project, env=env)

    # Then: generation succeeds and both managed file modes are retained.
    assert result.returncode == 0, result.stderr
    assert config_path.stat().st_mode & 0o777 == 0o640
    assert config_mk.stat().st_mode & 0o777 == 0o640


def test_env_source_captures_only_tool_path_with_banner_and_trailing_comment(
    tmp_path: Path,
):
    # Given: an env setup command that prints a banner and ends in a comment.
    project = tmp_path / "project"
    tool_dir = project / "vendor tools" / "bin"
    tool_dir.mkdir(parents=True)
    vcs = tool_dir / "vcs"
    vcs.write_text("#!/bin/sh\nexit 0\n")
    vcs.chmod(0o755)
    setup = project / "vendor tools" / "setup.sh"
    setup.write_text(f'echo "SETUP BANNER"\nexport PATH="{tool_dir}:$PATH"\n')
    config = _minimal_config()
    config["tools"] = {
        "simulators": {
            "vcs": {
                "detected": False,
                "path": "",
                "env_source": f'source "{setup}" # keep this comment',
            }
        }
    }
    (project / "rat_config.json").write_text(json.dumps(config))

    # When: the generator probes the configured environment.
    result = _run_generator(project)

    # Then: only command -v output becomes the detected path.
    assert result.returncode == 0, result.stderr
    generated = json.loads((project / "rat_config.json").read_text())
    saved_tool = generated["tools"]["simulators"]["vcs"]
    assert saved_tool["path"] == str(vcs)
    assert saved_tool["env_source"] == f'source "{setup}" # keep this comment'
    assert "SETUP BANNER" not in result.stdout


@pytest.mark.parametrize(
    ("section", "key", "unsafe_value"),
    [
        ("preferences", "simulator", "$(warning injected)"),
        ("coverage", "seeds", "7 $(shell touch injected)"),
        ("coverage", "seeds", "7 not-a-number"),
        ("technology", "liberty", "$(shell touch injected)"),
    ],
)
def test_unsafe_make_input_does_not_replace_managed_files(
    tmp_path: Path,
    section: str,
    key: str,
    unsafe_value: str,
):
    # Given: unsafe JSON input and existing managed files.
    project = tmp_path / f"project-{section}-{key}-{len(unsafe_value)}"
    project.mkdir()
    config = _minimal_config()
    config[section][key] = unsafe_value
    config_path = project / "rat_config.json"
    original_config = json.dumps(config)
    config_path.write_text(original_config)
    config_mk = project / "config.mk"
    original_mk = "# keep-existing-config-mk\n"
    config_mk.write_text(original_mk)

    # When: generation validates values crossing into Make syntax.
    result = _run_generator(project)

    # Then: it fails before either managed file is replaced or code is executed.
    assert result.returncode != 0
    assert config_path.read_text() == original_config
    assert config_mk.read_text() == original_mk
    assert not (project / "injected").exists()


def test_config_mk_normalizes_seeds_and_escapes_safe_path(tmp_path: Path):
    # Given: safe preferences, irregular seed whitespace, and a Liberty path with spaces.
    project = tmp_path / "project with spaces"
    liberty = project / "libs" / "standard cells.lib"
    liberty.parent.mkdir(parents=True)
    liberty.write_text("cell (NAND2X1) {\n  area : 2.500;\n}\n")
    config = _minimal_config()
    config["technology"]["liberty"] = "libs/standard cells.lib"
    config["coverage"]["seeds"] = "7\t11  13"
    (project / "rat_config.json").write_text(json.dumps(config))

    # When: the generator emits the Make include.
    result = _run_generator(project)

    # Then: tokens are preserved safely and the path is escaped for Make recipes.
    assert result.returncode == 0, result.stderr
    config_mk = (project / "config.mk").read_text()
    assert "PREF_SIM     ?= iverilog" in config_mk
    assert "PREF_SYN     ?= yosys" in config_mk
    assert "LIBERTY      ?= libs/standard\\ cells.lib" in config_mk
    assert "SEEDS        ?= 7 11 13" in config_mk


def test_invalid_json_does_not_replace_existing_config_mk(tmp_path: Path):
    # Given: invalid JSON beside an existing Make include.
    project = tmp_path / "project"
    project.mkdir()
    config_path = project / "rat_config.json"
    original_config = "{ invalid json\n"
    config_path.write_text(original_config)
    config_mk = project / "config.mk"
    original_mk = "# keep-existing-config-mk\n"
    config_mk.write_text(original_mk)

    # When: generation attempts to parse the config.
    result = _run_generator(project)

    # Then: neither managed file is changed.
    assert result.returncode != 0
    assert config_path.read_text() == original_config
    assert config_mk.read_text() == original_mk


def test_bash_version_guard_precedes_associative_arrays():
    # Given: the generator source used by Bash on every platform.
    source = GENERATE_CONFIG.read_text()

    # When: the version gate and first associative-array use are located.
    guard = source.find("BASH_VERSINFO[0]")
    associative_array = source.find("declare -A")

    # Then: Bash 3 exits through a clear gate before unsupported syntax executes.
    assert 0 <= guard < associative_array
