import os
import re
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
README = REPO_ROOT / "README.md"
README_KR = REPO_ROOT / "README_kr.md"
EDA_GUIDE = REPO_ROOT / "plugin_docs" / "eda-setup-guide.md"
DOCKERFILE = REPO_ROOT / "docker" / "Dockerfile"
RAT_SETUP_SKILL = REPO_ROOT / "skills" / "rat-setup" / "SKILL.md"
INSTALL_COMMANDS = REPO_ROOT / "skills" / "rat-setup" / "references" / "install-commands.md"
DOCKER_ENVIRONMENT = REPO_ROOT / "skills" / "rat-setup" / "references" / "docker-environment.md"
TOOL_CHECK_COMMANDS = REPO_ROOT / "skills" / "rat-setup" / "references" / "tool-check-commands.md"
PLUGIN_DEBUG = REPO_ROOT / "skills" / "rat-plugin-debug" / "SKILL.md"
TOOL_RUNNER = REPO_ROOT / "skills" / "rat-init-project" / "templates" / "lib" / "tool-runner.sh"
PROJECT_INSTALLER = REPO_ROOT / "skills" / "rat-init-project" / "scripts" / "install_project_templates.sh"
SLANG_INSTALLER = REPO_ROOT / "scripts" / "install-slang-server.sh"
POST_INSTALL = REPO_ROOT / "scripts" / "post-install.sh"
CONTRIBUTING = REPO_ROOT / "CONTRIBUTING.md"
TEST_README = REPO_ROOT / "tests" / "README.md"
TEST_GUIDE = REPO_ROOT / "tests" / "TEST-GUIDE.md"
LOCAL_CI = REPO_ROOT / "scripts" / "local-ci-check.sh"
CODEC_RD = REPO_ROOT / "skills" / "codec-rd-eval" / "SKILL.md"
COCOTB_ECOSYSTEM = (
    REPO_ROOT / "skills" / "rtl-p5s-func-verify" / "references" / "cocotb-ecosystem.md"
)
FUNC_VERIFY_POLICY = REPO_ROOT / "skills" / "rtl-p5s-func-verify-policy" / "SKILL.md"


def _bash_blocks(path: Path) -> list[str]:
    return re.findall(r"```bash\n(.*?)\n```", path.read_text(), re.DOTALL)


def test_dockerfile_pins_compatible_slang_and_svlens_versions() -> None:
    # Given: the published EDA image definition.
    content = DOCKERFILE.read_text()

    # When: its source-build versions are inspected.
    arguments = dict(re.findall(r"^ARG ([A-Z_]+)=(\S+)$", content, re.MULTILINE))

    # Then: the reviewed compatible pair is pinned.
    assert arguments["SLANG_VERSION"] == "v11.0"
    assert arguments["SVLENS_VERSION"] == "v0.3.6"
    assert "git clone --depth 1 --branch ${SVLENS_VERSION}" in content


def test_dockerfile_separates_required_and_optional_image_checks() -> None:
    # Given: the image verification layer.
    verification = DOCKERFILE.read_text().rsplit("RUN set -eu;", 1)[1]

    # When: its check routing and success marker are inspected.
    ready = verification.index('echo "=== All required tools ready ==="')

    # Then: required checks precede success and optional failures use a separate path.
    assert "check_required()" in verification
    assert "check_optional()" in verification
    assert verification.index("check_required svlens svlens --version") < ready
    assert verification.index("check_required slang slang --version") < ready
    assert verification.index("check_optional verible-verilog-lint") < ready
    assert "&& \\\n    verible-verilog-lint" not in verification


def test_debug_first_line_helper_preserves_a_present_tool_failure() -> None:
    # Given: the diagnostic helper and a tool that emits output before failing.
    content = PLUGIN_DEBUG.read_text()
    helper = re.search(
        r"^first_line_or_not_found\(\) \{.*?^\}",
        content,
        re.DOTALL | re.MULTILINE,
    )
    assert helper is not None
    script = (
        f"{helper.group(0)}\n"
        "failing_tool() { printf 'broken tool\\n'; return 23; }\n"
        "first_line_or_not_found failing_tool failing_tool\n"
    )

    # When: the helper formats that tool's first output line.
    result = subprocess.run(
        ["bash", "-c", script],
        text=True,
        capture_output=True,
        check=False,
    )

    # Then: formatting does not replace the tool's failure status.
    assert result.returncode == 23
    assert "broken tool" in result.stderr


def test_docker_run_surfaces_use_mount_user_and_writable_home() -> None:
    # Given: every shipped Docker run surface.
    surfaces = [
        DOCKERFILE.read_text(),
        DOCKER_ENVIRONMENT.read_text(),
        TOOL_RUNNER.read_text(),
        README.read_text(),
        README_KR.read_text(),
        EDA_GUIDE.read_text(),
    ]

    # When: Docker container creation commands are selected.
    commands = [
        line
        for content in surfaces
        for line in content.splitlines()
        if "docker run " in line
    ]

    # Then: no project volume uses -v and each persistent/project run declares identity and HOME.
    assert all(" -v " not in command for command in commands)
    combined = "\n".join(surfaces)
    assert '--mount "type=bind,src=$(pwd),dst=/workspace"' in combined
    assert combined.count('--user "$(id -u):$(id -g)"') >= 6
    assert combined.count("--env HOME=/tmp") >= 6


def test_host_install_and_test_guidance_uses_virtual_environments() -> None:
    # Given: the user-facing host Python installation surfaces.
    setup = RAT_SETUP_SKILL.read_text()
    contributing = CONTRIBUTING.read_text()
    test_readme = TEST_README.read_text()
    test_guide = TEST_GUIDE.read_text()

    # When: local installation commands are inspected.
    local_guidance = "\n".join([setup, contributing, test_readme])

    # Then: setup and contributor paths avoid externally managed system Python.
    assert "pip install --user" not in local_guidance
    assert "RAT_EDA_VENV" in setup
    assert '.venv/bin/python" -m pip install' in contributing
    assert '.venv/bin/python" -m pip install' in test_readme
    assert '.venv/bin/python" -m pip install' in test_guide
    operational_guidance = "\n".join(
        path.read_text()
        for path in (LOCAL_CI, CODEC_RD, COCOTB_ECOSYSTEM, FUNC_VERIFY_POLICY)
    )
    assert re.search(r"(?<!-m )\bpip3? install", operational_guidance) is None


def test_env_source_probe_uses_positional_arguments_and_suppresses_banners() -> None:
    # Given: both setup execution points and the matching EDA guide.
    combined = "\n".join([RAT_SETUP_SKILL.read_text(), EDA_GUIDE.read_text()])

    # When: the env_source probe contract is inspected.
    unsafe_concatenation = 'bash -c "$env_source && command -v $tool"'
    safe_probe = "eval \"$1\" >/dev/null 2>&1 && command -v -- \"$2\""

    # Then: comments and banners cannot swallow or contaminate command -v output.
    assert unsafe_concatenation not in combined
    assert combined.count(safe_probe) >= 3


def test_shell_version_comparisons_are_portable() -> None:
    # Given: both host-facing installers that compare dotted versions.
    slang_source = SLANG_INSTALLER.read_text()
    project_source = PROJECT_INSTALLER.read_text()
    helper = re.search(
        r"^version_gte\(\) \{.*?^\}", slang_source, re.DOTALL | re.MULTILINE
    )
    assert helper is not None

    # When: representative equal, newer, and older versions are compared.
    result = subprocess.run(
        ["bash", "-c", (
            "set -euo pipefail\n"
            f"{helper.group(0)}\n"
            "version_gte 3.20 3.20\n"
            "version_gte 3.21.1 3.20\n"
            "! version_gte 3.19.9 3.20\n"
        )],
        text=True,
        capture_output=True,
        check=False,
    )

    # Then: no GNU-only ordering or grep extension is required.
    assert result.returncode == 0, result.stderr
    assert "sort -V" not in slang_source + project_source
    assert "grep -oP" not in slang_source


def test_project_template_update_uses_numeric_version_order(tmp_path: Path) -> None:
    # Given: a deployed synthesis wrapper with a lexically misleading older version.
    workspace = tmp_path / "project"
    workspace.mkdir()
    first = subprocess.run(
        ["bash", str(PROJECT_INSTALLER), str(workspace)],
        text=True,
        capture_output=True,
        check=False,
    )
    assert first.returncode == 0, first.stderr
    deployed = workspace / "syn" / "scripts" / "run_syn.sh"
    deployed.write_text("# rat-version: 0.8.19\nolder-user-copy\n")

    # When: update mode compares it with the shipped 0.11.3 wrapper.
    update = subprocess.run(
        ["bash", str(PROJECT_INSTALLER), "--update", str(workspace)],
        text=True,
        capture_output=True,
        check=False,
    )

    # Then: numeric ordering updates 0.8.19 to 0.11.3.
    assert update.returncode == 0, update.stderr
    assert "# rat-version: 0.11.3" in deployed.read_text()

    # Given: a user copy newer than the shipped wrapper.
    deployed.write_text("# rat-version: 9.0.0\nnewer-user-copy\n")

    # When: update mode runs again.
    newer = subprocess.run(
        ["bash", str(PROJECT_INSTALLER), "--update", str(workspace)],
        text=True,
        capture_output=True,
        check=False,
    )

    # Then: the newer user copy remains untouched.
    assert newer.returncode == 0, newer.stderr
    assert "newer-user-copy" in deployed.read_text()


def test_post_install_probe_executes_each_tool_once(tmp_path: Path) -> None:
    # Given: a probe that succeeds once but would fail on a duplicate execution.
    source = POST_INSTALL.read_text()
    assert '"LINT GATE"' in source
    assert '"CDC GATE"' in source
    helper = re.search(
        r"^check_tool\(\) \{.*?^\}", source, re.DOTALL | re.MULTILINE
    )
    assert helper is not None
    marker = tmp_path / "probe-ran"
    script = (
        "set -euo pipefail\n"
        "GREEN= RED= YELLOW= NC=\n"
        "REQUIRED_FOUND=0 REQUIRED_TOTAL=0 OPTIONAL_FOUND=0 OPTIONAL_TOTAL=0\n"
        "MISSING_REQUIRED=()\n"
        f"MARKER={marker!s}\n"
        "flaky_probe() { if [ -e \"$MARKER\" ]; then return 23; fi; "
        ": > \"$MARKER\"; echo 'tool 1.0'; }\n"
        f"{helper.group(0)}\n"
        "check_tool demo flaky_probe no diagnostic\n"
    )

    # When: the post-install helper checks that probe.
    result = subprocess.run(
        ["bash", "-c", script],
        text=True,
        capture_output=True,
        check=False,
    )

    # Then: status and version come from one invocation without a pipeline race.
    assert result.returncode == 0, result.stderr
    assert "[OK]" in result.stdout


def test_tool_runner_missing_image_errors_use_only_plugin_build_context() -> None:
    # Given: the two Docker fallback error paths.
    content = TOOL_RUNNER.read_text()
    errors = "\n".join(line for line in content.splitlines() if "Build:" in line)

    # When: their suggested image build context is inspected.
    project_relative_context = re.search(r"(?:^|\s)docker/(?:[\"']|$)", errors)

    # Then: both point to the installed plugin's Dockerfile, never the project directory.
    assert errors.count("${CLAUDE_PLUGIN_ROOT}/docker/") == 2
    assert project_relative_context is None


def test_install_version_resolution_is_portable_and_fails_fast() -> None:
    # Given: the version discovery and install commands.
    content = INSTALL_COMMANDS.read_text()

    # When: version ordering, pins, and missing-tag guards are inspected.
    pins = dict(re.findall(r'^(SLANG_VERSION|SVLENS_VERSION)="([^"]+)"$', content, re.MULTILINE))

    # Then: discovery uses Python's portable numeric ordering and every reviewed pin is explicit.
    assert "sort -V" not in content
    assert "latest_stable_tag()" in content
    assert "set -euo pipefail" in content
    assert content.count(": \"${") >= 3
    assert pins == {"SLANG_VERSION": "v11.0", "SVLENS_VERSION": "v0.3.6"}


def test_local_and_global_install_blocks_resolve_their_own_versions() -> None:
    # Given: the two host installation blocks users run independently.
    content = INSTALL_COMMANDS.read_text()
    local_section = content.split("## Mode: `local`", 1)[1].split(
        "## Mode: `global`", 1
    )[0]
    global_section = content.split("## Mode: `global`", 1)[1].split("## macOS", 1)[0]
    local_install = re.findall(r"```bash\n(.*?)\n```", local_section, re.DOTALL)[0]
    global_install = re.findall(r"```bash\n(.*?)\n```", global_section, re.DOTALL)[0]

    # When: each block is detached from the preceding discovery example.
    required_assignments = (
        "latest_stable_tag()",
        "VERILATOR_LATEST_TAG=",
        "VERIBLE_LATEST_TAG=",
        "SYSTEMC_LATEST_TAG=",
        'SLANG_VERSION="v11.0"',
        'SVLENS_VERSION="v0.3.6"',
    )

    # Then: both remain fail-fast, pinned, self-resolving Bash programs.
    for block in (local_install, global_install):
        assert "set -euo pipefail" in block
        assert all(assignment in block for assignment in required_assignments)
        parsed = subprocess.run(
            ["bash", "-n"], input=block, text=True, capture_output=True
        )
        assert parsed.returncode == 0, parsed.stderr


def test_local_install_resolves_plugin_root_without_claude_environment() -> None:
    # Given: the standalone local install block and an unset Claude plugin root.
    local_section = INSTALL_COMMANDS.read_text().split("## Mode: `local`", 1)[1].split(
        "## Mode: `global`", 1
    )[0]
    local_install = re.findall(r"```bash\n(.*?)\n```", local_section, re.DOTALL)[0]
    resolver = re.search(
        r'^CLAUDE_PLUGIN_ROOT=.*\nSLANG_SERVER_INSTALLER=.*\n'
        r'\[\[ -f \"\$SLANG_SERVER_INSTALLER\" \]\].*$',
        local_install,
        re.MULTILINE,
    )
    assert resolver is not None
    assert resolver.start() < local_install.index('cd "$HOME/tools/verilator-src"')
    env = os.environ.copy()
    env.pop("CLAUDE_PLUGIN_ROOT", None)

    # When: only the plugin-root resolver runs from the repository checkout.
    result = subprocess.run(
        ["bash", "-c", f"set -euo pipefail\n{resolver.group(0)}\nprintf '%s\\n' \"$SLANG_SERVER_INSTALLER\""],
        cwd=REPO_ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    # Then: it validates and returns this checkout's installer without network access.
    assert result.returncode == 0, result.stderr
    assert Path(result.stdout.strip()) == SLANG_INSTALLER


def test_macos_install_block_builds_a_resolved_systemc_release() -> None:
    # Given: the macOS host installation block users run independently.
    macos_section = INSTALL_COMMANDS.read_text().split("## macOS (Homebrew)", 1)[1].split(
        "## Docker fallback", 1
    )[0]
    macos_install = re.findall(r"```bash\n(.*?)\n```", macos_section, re.DOTALL)[0]

    # When: its SystemC acquisition and build commands are inspected.
    parsed = subprocess.run(
        ["bash", "-n"], input=macos_install, text=True, capture_output=True, check=False
    )

    # Then: the block resolves, checks out, builds, and installs one concrete release.
    assert parsed.returncode == 0, parsed.stderr
    assert "latest_stable_tag()" in macos_install
    assert "SYSTEMC_LATEST_TAG=" in macos_install
    assert ': "${SYSTEMC_LATEST_TAG:?No SystemC release tag found}"' in macos_install
    assert 'git clone --depth 1 --branch "$SYSTEMC_LATEST_TAG"' in macos_install
    assert 'cmake -S "$HOME/tools/systemc-src"' in macos_install
    assert 'cmake --install "$HOME/tools/systemc-src/build"' in macos_install


def test_slang_server_installer_owns_only_binary_and_source() -> None:
    # Given: the standalone slang-server source installer.
    content = SLANG_INSTALLER.read_text()

    # When: its managed paths and embedded metadata are inspected.
    plugin_artifacts = (
        "setup_claude_plugin",
        "systemverilog-lsp",
        "/.claude/plugins/",
        '"1.1.2"',
    )

    # Then: install/uninstall manage the binary and source tree, not a duplicate plugin.
    assert all(artifact not in content for artifact in plugin_artifacts)
    assert 'rm -f "$INSTALL_DIR/slang-server"' in content
    assert 'rm -rf "$BUILD_DIR"' in content


def test_install_commands_pin_svlens_without_root_setup_scripts() -> None:
    # Given: local, global, and macOS install modes.
    content = INSTALL_COMMANDS.read_text()

    # When: svlens source acquisition and privilege boundaries are inspected.
    pinned_clones = content.count('git clone --depth 1 --branch "$SVLENS_VERSION"')

    # Then: every build is pinned and only final global installation uses sudo.
    assert pinned_clones == 3
    assert "sudo /tmp/svlens/scripts/setup-deps.sh" not in content
    assert "sudo cmake --install /tmp/svlens/build" in content


def test_install_commands_select_oss_cad_archive_for_host_architecture() -> None:
    # Given: the local OSS CAD Suite fallback.
    content = INSTALL_COMMANDS.read_text()

    # When: its archive architecture selection is inspected.
    oss_cad = content.split("# ===== Optional: OSS CAD Suite", 1)[1].split("```", 1)[0]

    # Then: both supported release assets are reachable from uname output.
    assert 'x86_64) OSS_CAD_ARCH="linux-x64"' in oss_cad
    assert 'aarch64|arm64) OSS_CAD_ARCH="linux-arm64"' in oss_cad
    assert "oss-cad-suite-${OSS_CAD_ARCH}-${OSS_CAD_DATE}.tgz" in oss_cad
    dockerfile = DOCKERFILE.read_text()
    assert 'case "$ARCH" in' in dockerfile
    assert "Unsupported OSS CAD Suite architecture: $ARCH" in dockerfile


def test_global_systemc_install_requires_resolved_version() -> None:
    # Given: the privileged host installation block.
    global_install = INSTALL_COMMANDS.read_text().split(
        "## Mode: `global`", 1
    )[1].split("## macOS", 1)[0]

    # When: its SystemC checkout version is inspected.
    version_assignment = (
        'SYSTEMC_TAG="${2:-${SYSTEMC_LATEST_TAG:?Run version discovery first}}"'
    )

    # Then: omission cannot silently build an arbitrary default branch.
    assert version_assignment in global_install
    assert '[ -n "$SYSTEMC_TAG" ] && git checkout' not in global_install


def test_install_modes_use_managed_cocotb_virtual_environments() -> None:
    # Given: all host installation modes.
    content = INSTALL_COMMANDS.read_text()

    # When: Python package installation and prerequisites are inspected.
    venv_creations = content.count("-m venv")

    # Then: each mode avoids externally-managed Python and exposes its environment on PATH.
    assert venv_creations >= 3
    assert "pip3 install cocotb" not in content
    assert "python3 -m pip install --user cocotb" not in content
    assert content.count('RAT_EDA_VENV/bin/python" -m pip install cocotb') >= 3
    assert "python3-venv" in content
    assert "curl" in content
    assert "brew install bash" in content
    assert "BASH_VERSINFO[0] >= 4" in content


def test_contributing_stages_named_paths_and_separates_local_plugin_testing() -> None:
    # Given: the contributor publication workflow.
    content = CONTRIBUTING.read_text()

    # When: staging and local plugin instructions are inspected.
    # v0.14.2: CONTRIBUTING.md became the English canonical document and the
    # Korean translation moved to CONTRIBUTING_kr.md, so these section splits key
    # off the English headings. test_doc_translation_pairs_stay_structurally_aligned
    # keeps the Korean copy in step.
    local_section = content.split("### Development environment setup", 1)[1].split(
        "### Filing an issue", 1
    )[0]

    # Then: broad staging is absent and local testing needs no marketplace publication.
    assert "git add -A" not in content
    assert "git diff --cached --check" in content
    assert "git diff --cached" in content
    assert 'claude --plugin-dir "$(pwd)"' in local_section
    assert "git push" not in local_section
    assert "marketplace update" not in local_section
    deployment = content.split("### Local testing vs. marketplace deployment", 1)[
        1
    ].split("\n---", 1)[0]
    staging_prose, staging_commands = deployment.split(
        "**Commands to run when deploying**", 1
    )
    for placeholder in (
        "agents/{agent-name}.md",
        "skills/{skill-name}/SKILL.md",
        "tests/unit/{test-name}.py",
    ):
        assert placeholder in staging_prose
        assert placeholder in staging_commands


def test_shipped_setup_bash_blocks_parse() -> None:
    # Given: every actual Bash block changed by the setup safety fix.
    paths = [INSTALL_COMMANDS, DOCKER_ENVIRONMENT, PLUGIN_DEBUG]

    # When: Bash parses each block without executing it.
    results = [
        (path, index, subprocess.run(["bash", "-n"], input=block, text=True, capture_output=True))
        for path in paths
        for index, block in enumerate(_bash_blocks(path), 1)
    ]

    # Then: all shipped snippets are syntactically valid.
    failures = [f"{path}:{index}: {result.stderr}" for path, index, result in results if result.returncode]
    assert failures == []


def test_tool_runner_is_valid_bash() -> None:
    # Given: the deployed Docker-aware runner.
    content = TOOL_RUNNER.read_text()

    # When: Bash parses it without executing Docker.
    result = subprocess.run(["bash", "-n"], input=content, text=True, capture_output=True)

    # Then: the template is a valid script.
    assert result.returncode == 0, result.stderr


def test_tool_check_first_line_commands_capture_status_before_formatting() -> None:
    # Given: discovery commands that format multi-line version output.
    content = TOOL_CHECK_COMMANDS.read_text()
    formatted = [line for line in content.splitlines() if "head -1" in line]

    # When: their status capture order is inspected.
    unsafe = [line for line in formatted if "rc=$?" not in line or line.index("rc=$?") > line.index("head -1")]

    # Then: every formatter saves the command status first.
    assert unsafe == []
