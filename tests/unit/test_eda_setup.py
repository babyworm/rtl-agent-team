"""Site discovery, conservative configuration, and remote readiness contracts."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT

SETUP = REPO_ROOT / "scripts/eda_setup.py"
RUNNER = REPO_ROOT / "scripts/eda_runner.py"


def executable(path, body):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body)
    path.chmod(0o755)
    return path


def call(*args, env=None, runner=SETUP):
    return subprocess.run([sys.executable, str(runner), *map(str, args)],
                          env={**os.environ, **(env or {})}, capture_output=True, text=True, timeout=20)


@pytest.fixture
def site(tmp_path):
    tools = tmp_path / "bin"
    executable(tools / "ssh", f'''#!{sys.executable}
import subprocess,sys
print("A login banner, not JSON",flush=True)
raise SystemExit(subprocess.call(sys.argv[-1],shell=True,executable="/bin/sh"))
''')
    executable(tools / "python3", "#!/bin/sh\nexit 1\n")
    (tools / "python3.11").symlink_to(sys.executable)
    executable(tools / "xrun", "#!/bin/sh\nprintf 'Xcelium fixture\\n'\n")
    executable(tools / "sg_shell", "#!/bin/sh\nexit 0\n")
    executable(tools / "vcs", "#!/bin/sh\nprintf 'error while loading shared libraries: libnsl.so.1\\n'\n")
    profile = tmp_path / "sites/synthetic-site.json"
    env = {"PATH": str(tools) + os.pathsep + os.environ["PATH"]}
    result = call("discover", "--host", "eda-fixture.example.invalid", "--paths-only", "--output", profile, env=env)
    assert result.returncode == 0, result.stderr
    return profile, env


def test_remote_profile_selects_supported_python_and_separates_license(site):
    profile, _ = site
    value = json.loads(profile.read_text())
    assert value["execution"]["host"] == "eda-fixture.example.invalid"
    assert value["python_version"] >= [3, 9]
    assert value["tools"]["simulators"]["xrun"]["detected"]
    assert value["evidence_level"] == "executable_paths"
    assert value["license_checked"] is False
    assert profile.stat().st_mode & 0o777 == 0o600


def test_remote_discovery_does_not_reuse_a_local_python_path(site, tmp_path):
    _, env = site
    config = tmp_path / "local.json"
    config.write_text('{"execution":{"backend":"local","python":"/local-only/python"}}')
    result = call("discover", "--host", "eda-fixture.example.invalid", "--config", config, env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["execution"]["python"] != "/local-only/python"


def test_discovery_sources_shared_setup_and_checks_execution_on_host(site, tmp_path):
    _, env = site
    vendor = tmp_path / "vendor bin"
    xrun = executable(vendor / "xrun", '#!/bin/sh\ntest "$FIXTURE_ENV" = loaded || exit 3\n'
                      'test -s "rat_setup_tb.sv" || exit 4\nprintf "RAT_SETUP_SIM_PASS\\n"\n')
    executable(vendor / "vcs", '#!/bin/sh\nprintf "error while loading shared libraries: missing.so\\n"\n')
    executable(vendor / "vsim", '#!/bin/sh\nexec 1>&- 2>&-\nexec sleep 6\n')
    executable(vendor / "dc_shell", '#!/bin/sh\nprintf "FLEXnet Licensing checkout error:\\n"\n')
    executable(vendor / "imc", '#!/bin/sh\ntest "$1" = -exec && test -f "$2" && echo RAT_SETUP_TCL_READY\n')
    setup = tmp_path / "setup script.sh"
    setup.write_text(f'export PATH="{vendor}:$PATH"\nexport FIXTURE_ENV=loaded\necho setup-banner\n')
    result = call("discover", "--host", "eda-fixture.example.invalid", "--env-script", setup,
                  "--probe-timeout", "1", env=env)
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout)
    assert value["evidence_level"] == "tool_readiness"
    sims = value["tools"]["simulators"]
    assert sims["xrun"]["path"] == str(xrun)
    assert sims["xrun"]["setup_status"] == "workload_passed"
    assert sims["xrun"]["probe"]["license_checked"]
    assert sims["vcs"]["setup_status"] == "loader_failed"
    assert sims["vsim"]["setup_status"] == "timeout"
    assert "output" not in sims["vcs"]["probe"]
    assert value["tools"]["synthesis"]["dc_shell"]["setup_status"] == "license_failed"
    imc = value["tools"]["coverage"]["imc"]
    assert imc["setup_status"] == "command_passed"
    assert imc["probe"]["license_checked"] is False


def test_discovery_preserves_configured_check_and_requires_workload_evidence(tmp_path):
    tool = executable(tmp_path / "imc", '#!/bin/sh\nprintf "%s\\n" "IMC launched"\n')
    source = tmp_path / "candidate.json"
    source.write_text(json.dumps({"tools": {"coverage": {"imc": {
        "path": str(tool), "setup_check": {"args": ["test"], "expected_line": "MERGED", "licensed": True}
    }}}}))
    profile = tmp_path / "profile.json"
    result = call("discover", "--config", source, "--output", profile)
    assert result.returncode == 0, result.stderr
    imc = json.loads(profile.read_text())["tools"]["coverage"]["imc"]
    assert imc["setup_status"] == "workload_unverified"
    assert imc["probe"]["license_checked"] is False
    root = tmp_path / "project"
    result = call("configure", "--profile", profile, "--root", root)
    assert result.returncode == 0, result.stderr
    persisted = json.loads((root / "rat_config.json").read_text())["tools"]["coverage"]["imc"]
    assert persisted["setup_check"] == imc["setup_check"]
    assert persisted["setup_status"] == "workload_unverified"


def test_probe_detects_loader_failure_despite_zero_exit(site, tmp_path):
    profile, env = site
    result = call("probe", "--profile", profile, "--tool", "simulators.vcs", "--record", "--", "-ID", env=env)
    assert result.returncode == 1
    value = json.loads(result.stdout)
    assert value["exit_code"] == 0
    assert value["status"] == "failed"
    assert "libnsl" in value["output"]
    root = tmp_path / "project"
    configured = call("configure", "--profile", profile, "--root", root, env=env)
    assert configured.returncode == 0
    assert json.loads(configured.stdout)["preferences"]["simulator"] == "xrun"
    value = json.loads(configured.stdout)
    value["preferences"]["simulator"] = "vcs"
    (root / "rat_config.json").write_text(json.dumps(value))
    readiness = call("capabilities", "--root", root, "--phase", "p4", "--framework", "sv", "--probe-remote", env=env, runner=RUNNER)
    assert readiness.returncode == 1
    assert "simulator" in json.loads(readiness.stdout)["missing"]


def test_successful_version_probe_does_not_claim_license(site):
    profile, env = site
    result = call("probe", "--profile", profile, "--tool", "simulators.xrun", "--", "-version", env=env)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["license_checked"] is False


def test_probe_timeout_is_bounded(site, tmp_path):
    profile, env = site
    sleeping = executable(tmp_path / "sleeper", "#!/bin/sh\nsleep 10\n")
    value = json.loads(profile.read_text())
    value["tools"]["simulators"]["xrun"]["path"] = str(sleeping)
    profile.write_text(json.dumps(value))
    result = call("probe", "--profile", profile, "--tool", "simulators.xrun", "--timeout", "0.05", "--", "-version", env=env)
    assert result.returncode == 1
    assert json.loads(result.stdout)["exit_code"] == 124


def test_dry_run_writes_nothing_and_workspace_is_project_specific(site, tmp_path):
    profile, env = site
    proposed = []
    for base in ("first", "second"):
        root = tmp_path / base / "same-name"
        result = call("configure", "--profile", profile, "--root", root, "--dry-run", env=env)
        assert result.returncode == 0, result.stderr
        assert not root.exists()
        proposed.append(json.loads(result.stdout)["execution"]["workspace"])
    assert proposed[0] != proposed[1]


def test_configuration_preserves_user_values_and_explicit_preference(site, tmp_path):
    profile, env = site
    root = tmp_path / "project"
    root.mkdir()
    old = {"technology": {"db": "/site/cells.db", "nand2_area_um2": 8.5},
           "execution": {"outputs": ["sim", "syn"], "timeout_seconds": 72},
           "tools": {"simulators": {"xrun": {"path": "/custom/xrun", "license_wait_args": ["-site-wait"]}}},
           "preferences": {"simulator": "vcs"}}
    (root / "rat_config.json").write_text(json.dumps(old))
    result = call("configure", "--profile", profile, "--root", root, "--prefer", "simulator=xrun", env=env)
    assert result.returncode == 0, result.stderr
    value = json.loads((root / "rat_config.json").read_text())
    assert value["technology"] == old["technology"]
    assert value["execution"]["outputs"] == ["sim", "syn"]
    assert value["execution"]["timeout_seconds"] == 72
    assert value["preferences"]["simulator"] == "xrun"
    assert value["tools"]["simulators"]["xrun"]["path"] == "/custom/xrun"
    assert value["tools"]["simulators"]["xrun"]["license_wait_args"] == ["-site-wait"]
    assert value["tools"]["simulators"]["xrun"]["detected"] is False


@pytest.mark.parametrize("destination_kind", ["symlink", "hardlink"])
def test_configure_rejects_linked_destination(site, tmp_path, destination_kind):
    profile, env = site
    root = tmp_path / "project"
    root.mkdir()
    target = tmp_path / "user.json"
    target.write_text("{}")
    destination = root / "rat_config.json"
    if destination_kind == "symlink":
        destination.symlink_to(target)
    else:
        os.link(target, destination)
    result = call("configure", "--profile", profile, "--root", root, env=env)
    assert result.returncode == 2
    assert target.read_text() == "{}"


@pytest.mark.parametrize("relative", [".rat/fixture-site.json", "scripts/fixture-site.json"])
def test_private_site_output_cannot_be_written_into_plugin_repository(site, relative):
    profile, env = site
    destination = REPO_ROOT / relative
    assert not destination.exists()
    result = call("discover", "--host", "eda-fixture.example.invalid", "--output", destination, env=env)
    assert result.returncode == 2
    assert "outside the plugin repository" in result.stderr
    assert not destination.exists()


def test_project_site_configuration_cannot_be_written_into_plugin_repository(site):
    profile, env = site
    destination = REPO_ROOT / ".rat/fixture-project-config"
    assert not destination.exists()
    result = call("configure", "--profile", profile, "--root", destination, env=env)
    assert result.returncode == 2
    assert "outside the plugin repository" in result.stderr
    assert not destination.exists()


def test_other_site_requires_resolution_of_host_specific_overrides(site, tmp_path):
    profile, env = site
    root = tmp_path / "project"
    root.mkdir()
    destination = root / "rat_config.json"
    destination.write_text('{"execution":{"host":"other-site"}}')
    before = destination.read_text()
    result = call("configure", "--profile", profile, "--root", root, env=env)
    assert result.returncode == 2
    assert "another site" in result.stderr
    assert destination.read_text() == before


def test_existing_lsf_queue_and_workspace_are_preserved(site, tmp_path):
    profile, env = site
    root = tmp_path / "project"
    root.mkdir()
    (root / "rat_config.json").write_text(json.dumps({"execution": {
        "backend": "lsf", "host": "eda-fixture.example.invalid", "queue": "site-queue", "workspace": "/private/project"}}))
    result = call("configure", "--profile", profile, "--root", root, env=env)
    assert result.returncode == 0
    execution = json.loads(result.stdout)["execution"]
    assert execution["backend"] == "lsf"
    assert execution["queue"] == "site-queue"
    assert execution["workspace"] == "/private/project"


def test_host_options_are_not_accepted_as_a_hostname(tmp_path):
    result = call("discover", "--host=-oProxyCommand=touch /tmp/unexpected")
    assert result.returncode == 2
    assert "SSH host alias" in result.stderr


def test_remote_readiness_is_opt_in_and_honors_configured_simulator(site, tmp_path):
    profile, env = site
    root = tmp_path / "project"
    result = call("configure", "--profile", profile, "--root", root, "--prefer", "simulator=xrun", env=env)
    assert result.returncode == 0, result.stderr
    unprobed = call("capabilities", "--root", root, "--phase", "p4", "--framework", "sv", env=env, runner=RUNNER)
    assert json.loads(unprobed.stdout)["scope"] == "remote_unprobed"
    probed = call("capabilities", "--root", root, "--phase", "p4", "--framework", "sv", "--probe-remote", env=env, runner=RUNNER)
    assert probed.returncode == 0, probed.stdout + probed.stderr
    value = json.loads(probed.stdout)
    assert value["scope"] == "ssh"
    assert value["capabilities"]["simulator"] == "xrun"
    assert value["license_checked"] is False


def test_remote_signoff_checks_library_on_execution_host(site, tmp_path):
    profile, env = site
    root = tmp_path / "project"
    call("configure", "--profile", profile, "--root", root, env=env)
    value = json.loads((root / "rat_config.json").read_text())
    value["technology"] = {"db": "/missing-site/library.db"}
    (root / "rat_config.json").write_text(json.dumps(value))
    result = call("capabilities", "--root", root, "--phase", "p1", "--signoff", "--probe-remote", env=env, runner=RUNNER)
    assert result.returncode == 1
    assert "technology.db for timing signoff" in json.loads(result.stdout)["missing"]


def test_remote_capabilities_cannot_probe_the_local_host_by_accident(tmp_path):
    (tmp_path / "rat_config.json").write_text('{"execution":{"backend":"ssh"}}')
    result = call("capabilities", "--root", tmp_path, "--phase", "p1", "--probe-remote", runner=RUNNER)
    assert result.returncode == 2


def test_site_defaults_fill_only_unset_or_auto_detected_choices(site, tmp_path):
    profile, env = site
    data = json.loads(profile.read_text())
    data["preferences"] = {"simulator": "xrun"}
    data["technology"] = {"db": "/site/default.db"}
    profile.write_text(json.dumps(data))
    cases = {"auto": ({"simulator": "vcs", "_auto": {"simulator": "vcs"}}, {}),
             "explicit": ({"simulator": "vcs"}, {"db": "/project/cells.db"})}
    for name, (preferences, technology) in cases.items():
        root = tmp_path / name
        root.mkdir()
        (root / "rat_config.json").write_text(json.dumps({"preferences": preferences, "technology": technology}))
        result = call("configure", "--profile", profile, "--root", root, env=env)
        assert result.returncode == 0, result.stderr
        value = json.loads((root / "rat_config.json").read_text())
        expected = ("xrun", "/site/default.db") if name == "auto" else ("vcs", "/project/cells.db")
        assert (value["preferences"]["simulator"], value["technology"]["db"]) == expected


def test_runner_uses_private_settings_before_project_init(tmp_path):
    root = tmp_path / "fresh project"
    root.mkdir()
    data = tmp_path / "user data"
    (data / "sites").mkdir(parents=True)
    env = {"RAT_DATA_DIR": str(data)}
    machine = data / "env-config.json"
    machine.write_text(json.dumps({"preferences": {"simulator": "iverilog"}}))

    def get(key):
        return call("get", "--root", root, "--key", key, env=env, runner=RUNNER)

    assert get("preferences.simulator").stdout.strip() == "iverilog"
    machine.write_text(json.dumps({"default_site": "lab", "preferences": {"simulator": "iverilog"}}))
    assert get("preferences.simulator").returncode == 2  # A missing selected site must not run locally.
    assert list(root.iterdir()) == []
    profile = {
        "measured_at": 1, "home": "/home/fixture",
        "execution": {"backend": "ssh", "host": "example.invalid"},
        "tools": {"simulators": {"xrun": {"path": "/opt/fixture/xrun", "detected": True,
                                          "env_source": "exit 1", "env_shell": "bash"}}},
        "preferences": {"simulator": "xrun"}, "technology": {"db": "/opt/fixture/cells.db"},
    }
    (data / "sites/lab.json").write_text(json.dumps(profile))
    assert get("preferences.simulator").stdout.strip() == "xrun"
    assert get("technology.db").stdout.strip() == "/opt/fixture/cells.db"
    assert get("execution.workspace").stdout.startswith("/home/fixture/")
    assert call("available", "--root", root, "--tool", "xrun", env=env, runner=RUNNER).returncode == 0
    assert call("available", "--root", root, "--tool", "sh", env=env, runner=RUNNER).returncode == 1
    assert list(root.iterdir()) == []
    (root / "rat_config.json").write_text('{"execution":{"backend":"local"}}')
    assert get("execution.backend").stdout.strip() == "local"
    assert not get("execution.host").stdout.strip()
    assert not get("technology.db").stdout.strip()
