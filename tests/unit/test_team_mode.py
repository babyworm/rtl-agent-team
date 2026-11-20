"""Tests for Claude Code native team integration.

Validates:
- team-config.json creation and cleanup logic
- Phase handoff gates shared by sequential and team runs
- Worker preamble file existence
- Team orchestrator agent structural integrity
"""

import json
import re
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT
from tests.contracts import read_contract

AGENTS_DIR = REPO_ROOT / "agents"
SKILLS_DIR = REPO_ROOT / "skills"
AGENT_LIB_DIR = REPO_ROOT / "plugin_docs" / "agent-lib"
TEMPLATE_DIR = SKILLS_DIR / "rtl-p4-rapid-impl-policy" / "templates"


class TestTeamConfigLifecycle:
    """Validate team-config.json creation and cleanup."""

    def test_team_config_template_exists(self):
        template = TEMPLATE_DIR / "team-config.json"
        assert template.exists()

    def test_team_config_template_valid_json(self):
        template = TEMPLATE_DIR / "team-config.json"
        data = json.loads(read_contract(template))
        assert isinstance(data["team_mode"], bool)
        assert data["team_mode"] is False
        assert data["team_name"] == ""
        assert data["leader_session_id"] == ""
        assert data["phase"] == ""
        assert "{{TIMESTAMP}}" in data["created_at"]

    def test_team_config_creation(self, tmp_path):
        """Simulate team-config.json creation as the skill would."""
        state_dir = tmp_path / ".rat" / "state"
        state_dir.mkdir(parents=True)
        config = {
            "team_mode": True,
            "team_name": "p5-verify",
            "leader_session_id": "session-abc-123",
            "phase": "p5",
            "created_at": "2026-03-05T00:00:00Z"
        }
        config_file = state_dir / "team-config.json"
        config_file.write_text(json.dumps(config, indent=2))

        loaded = json.loads(read_contract(config_file))
        assert loaded["team_mode"] is True
        assert loaded["team_name"] == "p5-verify"
        assert loaded["leader_session_id"] == "session-abc-123"
        assert loaded["phase"] == "p5"

    def test_team_config_cleanup(self, tmp_path):
        """Removing team-config.json restores normal Stop hook behavior."""
        state_dir = tmp_path / ".rat" / "state"
        state_dir.mkdir(parents=True)
        config_file = state_dir / "team-config.json"
        config_file.write_text(json.dumps({"team_mode": True, "team_name": "test"}))
        assert config_file.exists()
        config_file.unlink()
        assert not config_file.exists()


def test_full_p4_requires_synthesizability():
    skill = "rtl-p4-implement"
    criteria = json.loads(read_contract(REPO_ROOT / "skill-completion-criteria.json"))
    registry = json.loads(read_contract(REPO_ROOT / "phase-registry.json"))
    assert "synthesizability-pass" in criteria[skill].split("|")
    assert criteria[skill] == registry["skills"][skill]["completion_criteria"]


@pytest.mark.parametrize(("criteria", "expected"), [
    (None, "FAIL"), ([], "FAIL"), (["Carry is retained in bit 8."], "PASS"),
])
def test_p3_handoff_accepts_legacy_criteria_but_requires_an_oracle(tmp_path, criteria, expected):
    docs = tmp_path / "docs/phase-3-uarch"
    docs.mkdir(parents=True)
    (docs / "adder.md").write_text("An 8-bit adder exposes its carry at bit 8.")
    requirement = {"id": "REQ-U-001"}
    if criteria is not None:
        requirement["acceptance_criteria"] = criteria
    (docs / "iron-requirements.json").write_text(json.dumps([requirement]))
    (docs / "open-requirements.json").write_text("[]")
    (docs / "judgment.json").write_text(json.dumps({"confidence": "high", "material_ambiguities": []}))
    (tmp_path / "bfm").mkdir()
    (tmp_path / "bfm/adder.cpp").write_text("unsigned add(unsigned a, unsigned b) { return a + b; }")

    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts/gates/phase_gate.py"), "--root", str(tmp_path), "--phase", "3"],
        capture_output=True, text=True, timeout=15,
    )
    report = json.loads(result.stdout)
    assert report["verdict"] == expected
    assert [item["check"] for item in report["checks"] if not item["passed"]] == (
        [] if expected == "PASS" else ["acceptance:REQ-U-001"]
    )


class TestTeamOrchestratorStructure:
    """Validate team orchestrator and worker preamble files."""

    def test_p5_verify_team_orchestrator_exists(self):
        agent = AGENTS_DIR / "p5-verify-orchestrator.md"
        assert agent.exists()

    def test_p5_verify_team_orchestrator_has_frontmatter(self):
        agent = AGENTS_DIR / "p5-verify-orchestrator.md"
        content = read_contract(agent)
        assert content.startswith("---")
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = parts[1]
        assert "name: p5-verify-orchestrator" in fm
        assert "model: fable" in fm
        assert "skills:" in fm

    def test_p5_verify_team_orchestrator_has_coordination_teammate_role(self):
        """Orchestrator must have Coordination Teammate Role (Orchestrator as Teammate pattern)."""
        agent = AGENTS_DIR / "p5-verify-orchestrator.md"
        content = read_contract(agent)
        assert "Coordination Teammate Role" in content
        assert "FORBIDDEN" in content
        assert "TaskCreate" in content
        assert "TaskList" in content or "TaskUpdate" in content

    def test_p5_verify_team_orchestrator_references_dependency_graph(self):
        agent = AGENTS_DIR / "p5-verify-orchestrator.md"
        content = read_contract(agent)
        assert "blockedBy" in content or "blocked by" in content.lower()

    def test_p5_verify_team_skill_exists(self):
        skill = SKILLS_DIR / "rtl-p5-verify" / "SKILL.md"
        assert skill.exists()

    def test_p5_verify_team_skill_is_user_invocable(self):
        skill = SKILLS_DIR / "rtl-p5-verify" / "SKILL.md"
        content = read_contract(skill)
        assert "user-invocable: true" in content

    def test_p5_verify_team_skill_delegates_to_orchestrator(self):
        skill = SKILLS_DIR / "rtl-p5-verify" / "SKILL.md"
        content = read_contract(skill)
        assert 'rtl-agent-team:p5-verify-orchestrator' in content

    def test_worker_preamble_exists(self):
        preamble = AGENT_LIB_DIR / "team-worker-preamble.md"
        assert preamble.exists()

    def test_worker_preamble_has_lifecycle_sections(self):
        preamble = AGENT_LIB_DIR / "team-worker-preamble.md"
        content = read_contract(preamble)
        assert "Initialization" in content
        assert "Task Claim" in content or "Task Execution" in content
        assert "Shutdown" in content
        assert "Error Handling" in content

    def test_worker_protocol_template_exists(self):
        """plugin_docs/agent-lib/team-worker-protocol.md must exist."""
        protocol = AGENT_LIB_DIR / "team-worker-protocol.md"
        assert protocol.exists()

    def test_worker_protocol_has_key_steps(self):
        """Protocol template must have INIT, CLAIM, EXECUTE, REPORT, SHUTDOWN."""
        protocol = AGENT_LIB_DIR / "team-worker-protocol.md"
        content = read_contract(protocol)
        for step in ["INIT", "CLAIM", "EXECUTE", "REPORT", "SHUTDOWN"]:
            assert step in content, f"Protocol missing step: {step}"

    def test_specialist_agents_have_team_worker_protocol(self):
        """11 specialist agents must have Team Worker Protocol section."""
        agents = [
            "rtl-coder", "lint-checker", "rtl-critic", "testbench-dev", "eda-runner",
            "sva-extractor", "cdc-checker", "protocol-checker",
            "func-verifier", "coverage-analyst", "perf-verifier",
        ]
        missing = []
        for name in agents:
            agent_file = AGENTS_DIR / f"{name}.md"
            assert agent_file.exists(), f"Missing agent: {name}"
            content = read_contract(agent_file)
            if "## Team Worker Protocol" not in content:
                missing.append(name)
        assert missing == [], f"Agents missing Team Worker Protocol section: {missing}"

    # --- P4 Team Orchestrator ---

    def test_p4_implement_team_orchestrator_exists(self):
        agent = AGENTS_DIR / "p4-implement-orchestrator.md"
        assert agent.exists()

    def test_p4_implement_team_orchestrator_has_frontmatter(self):
        agent = AGENTS_DIR / "p4-implement-orchestrator.md"
        content = read_contract(agent)
        assert content.startswith("---")
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = parts[1]
        assert "name: p4-implement-orchestrator" in fm
        assert "model: fable" in fm
        assert "skills:" in fm

    def test_p4_implement_team_orchestrator_has_coordination_teammate_role(self):
        """Orchestrator must have Coordination Teammate Role (Orchestrator as Teammate pattern)."""
        agent = AGENTS_DIR / "p4-implement-orchestrator.md"
        content = read_contract(agent)
        assert "Coordination Teammate Role" in content
        assert "FORBIDDEN" in content
        assert "TaskCreate" in content
        assert "TaskList" in content or "TaskUpdate" in content

    def test_p4_implement_team_orchestrator_references_10_wave(self):
        agent = AGENTS_DIR / "p4-implement-orchestrator.md"
        content = read_contract(agent)
        assert "Wave 1" in content or "W1" in content
        assert "Wave 10" in content or "W10" in content
        assert "blockedBy" in content

    def test_p4_implement_team_skill_exists(self):
        skill = SKILLS_DIR / "rtl-p4-implement" / "SKILL.md"
        assert skill.exists()

    def test_p4_implement_team_skill_is_user_invocable(self):
        skill = SKILLS_DIR / "rtl-p4-implement" / "SKILL.md"
        content = read_contract(skill)
        assert "user-invocable: true" in content

    def test_p4_implement_team_skill_delegates_to_orchestrator(self):
        skill = SKILLS_DIR / "rtl-p4-implement" / "SKILL.md"
        content = read_contract(skill)
        assert "rtl-agent-team:p4-implement-orchestrator" in content


class TestAutopilotTeamAwareness:
    """Validate autopilot orchestrator team-awareness routing."""

    def test_autopilot_references_p4_team_orchestrator(self):
        agent = AGENTS_DIR / "autopilot-orchestrator.md"
        content = read_contract(agent)
        assert "p4-implement-orchestrator" in content

    def test_autopilot_references_p5_team_orchestrator(self):
        agent = AGENTS_DIR / "autopilot-orchestrator.md"
        content = read_contract(agent)
        assert "p5-verify-orchestrator" in content

    def test_sequential_autopilot_forwards_review_scope_to_each_phase(self):
        agent = read_contract(AGENTS_DIR / "autopilot-orchestrator.md")
        rows = re.findall(r"^\| ([1-6]) \| `rtl-agent-team:([\w-]+)` \|$", agent, re.M)
        assert [int(phase) for phase, _owner in rows] == list(range(1, 7))
        assert all((AGENTS_DIR / f"{owner}.md").exists() for _phase, owner in rows)
        dispatch = agent.split("Task(subagent_type=phase_owner,", 1)[1].split('```', 1)[0]
        assert "MODE=sequential" in dispatch and "{review_scope}" in dispatch
        template = json.loads((SKILLS_DIR / "rat-auto-design/templates/autopilot-state.json").read_text())
        assert template["review_scope"] is None



class TestTeamIntegrationInfrastructure:
    """Validate Phase 4 full integration artifacts."""

    def test_team_fallback_doc_exists(self):
        fallback = AGENT_LIB_DIR / "team-fallback.md"
        assert fallback.exists()

    def test_team_fallback_covers_key_scenarios(self):
        fallback = AGENT_LIB_DIR / "team-fallback.md"
        content = read_contract(fallback)
        assert "TeamCreate Failure" in content
        assert "SendMessage Failure" in content
        assert "Worker Crash" in content
        assert "Leader Crash" in content
        assert "Coordinator Crash" in content

    def test_team_progress_hook_exists(self):
        hook = REPO_ROOT / "hooks" / "rtl-team-progress.sh"
        assert hook.exists()

    def test_team_progress_hook_registered_in_hooks_json(self):
        hooks_data = json.loads(read_contract(REPO_ROOT / "hooks" / "hooks.json"))
        post_entries = hooks_data["hooks"]["PostToolUse"]
        matchers = [e["matcher"] for e in post_entries]
        assert "TaskUpdate" in matchers

    def test_team_progress_hook_checks_team_config(self):
        hook = REPO_ROOT / "hooks" / "rtl-team-progress.sh"
        content = read_contract(hook)
        assert "team-config.json" in content

    def test_plugin_version_bumped(self):
        plugin = json.loads(read_contract(REPO_ROOT / ".claude-plugin" / "plugin.json"))
        major, minor, patch = plugin["version"].split(".")
        assert int(minor) >= 6 or int(major) >= 1, "Version should be >= 0.6.0 for Orchestrator as Teammate"

    def test_claude_md_has_team_mode_section(self):
        claude_md = read_contract(REPO_ROOT / "CLAUDE.md")
        assert "Native Team Mode" in claude_md

    def test_autopilot_skill_documents_team_mode(self):
        skill = SKILLS_DIR / "rat-auto-design" / "SKILL.md"
        content = read_contract(skill)
        assert "--no-team" in content or "team mode" in content.lower()


class TestP1P3TeamOrchestratorStructure:
    """Validate P1-P3 team orchestrator and skill structural integrity."""

    TEAM_ORCHESTRATORS = [
        ("p1-research-orchestrator", "p1-spec-research"),
        ("p2-arch-orchestrator", "p2-arch-design"),
        ("p3-uarch-orchestrator", "rtl-p3-uarch-design"),
    ]

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_orchestrator_exists(self, agent_name, skill_name):
        agent = AGENTS_DIR / f"{agent_name}.md"
        assert agent.exists(), f"Missing team orchestrator: {agent_name}"

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_orchestrator_has_frontmatter(self, agent_name, skill_name):
        agent = AGENTS_DIR / f"{agent_name}.md"
        content = read_contract(agent)
        assert content.startswith("---")
        parts = content.split("---", 2)
        assert len(parts) >= 3
        fm = parts[1]
        assert f"name: {agent_name}" in fm
        assert "model: fable" in fm
        assert "skills:" in fm

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_orchestrator_has_coordination_teammate_role(self, agent_name, skill_name):
        """Orchestrators must have Coordination Teammate Role section."""
        agent = AGENTS_DIR / f"{agent_name}.md"
        content = read_contract(agent)
        assert "Coordination Teammate Role" in content
        assert "FORBIDDEN" in content
        assert "TaskCreate" in content

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_orchestrator_references_dependency_graph(self, agent_name, skill_name):
        agent = AGENTS_DIR / f"{agent_name}.md"
        content = read_contract(agent)
        assert "blockedBy" in content or "blocked by" in content.lower()

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_skill_exists(self, agent_name, skill_name):
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        assert skill.exists(), f"Missing team skill: {skill_name}"

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_skill_is_user_invocable(self, agent_name, skill_name):
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = read_contract(skill)
        assert "user-invocable: true" in content

    @pytest.mark.parametrize("agent_name,skill_name", TEAM_ORCHESTRATORS)
    def test_team_skill_delegates_to_orchestrator(self, agent_name, skill_name):
        skill = SKILLS_DIR / skill_name / "SKILL.md"
        content = read_contract(skill)
        assert f"rtl-agent-team:{agent_name}" in content


class TestSpecToUarchTeamStructure:
    """Validate spec-to-uarch-team orchestrator (pipeline, NOT a team)."""

    def test_orchestrator_exists(self):
        agent = AGENTS_DIR / "spec-to-uarch-orchestrator.md"
        assert agent.exists()

    def test_orchestrator_has_frontmatter(self):
        agent = AGENTS_DIR / "spec-to-uarch-orchestrator.md"
        content = read_contract(agent)
        assert content.startswith("---")
        parts = content.split("---", 2)
        fm = parts[1]
        assert "name: spec-to-uarch-orchestrator" in fm
        assert "model: fable" in fm

    def test_orchestrator_does_not_create_team(self):
        content = read_contract(AGENTS_DIR / 'spec-to-uarch-orchestrator.md')
        assert 'FORBIDDEN: TeamCreate' in content
        assert 'main session' in content

    def test_orchestrator_delegates_to_phase_teams(self):
        content = read_contract(AGENTS_DIR / 'spec-to-uarch-orchestrator.md')
        assert 'each phase through its Action Skill' in content
        assert 'do not create nested teams' in content

    def test_skill_exists(self):
        skill = SKILLS_DIR / "rat-p1p3-spec-uarch" / "SKILL.md"
        assert skill.exists()

    def test_skill_is_user_invocable(self):
        skill = SKILLS_DIR / "rat-p1p3-spec-uarch" / "SKILL.md"
        content = read_contract(skill)
        assert "user-invocable: true" in content

    def test_skill_sequences_phase_team_skills(self):
        """Pipeline skill team mode invokes the phase skills with team in the arguments."""
        skill = SKILLS_DIR / "rat-p1p3-spec-uarch" / "SKILL.md"
        content = read_contract(skill)
        assert 'Skill(skill="rtl-agent-team:p1-spec-research", args="team $ARGUMENTS {review_scope}")' in content
        assert 'Skill(skill="rtl-agent-team:p2-arch-design", args="team Phase 1 artifacts complete {review_scope}")' in content
        assert 'Skill(skill="rtl-agent-team:rtl-p3-uarch-design", args="team Phase 2 artifacts complete {review_scope}")' in content


# ── P1-P3 Agent Worker Protocol ─────────────────────────────────────────────


class TestP1P3AgentsHaveProtocol:
    """Validate that all 16 P1-P3 specialist agents have Team Worker Protocol."""

    P1_P3_AGENTS = [
        "spec-analyst", "vcodec-chief-standard-expert", "rtl-architect",
        "vcodec-architecture-expert", "arch-designer", "power-analyzer",
        "vcodec-syntax-entropy-expert", "vcodec-intra-pred-expert",
        "vcodec-me-expert", "vcodec-mc-expert",
        "vcodec-transform-quant-expert", "vcodec-filter-recon-expert",
        "video-processing-expert", "ref-model-dev", "bfm-dev", "timing-advisor",
    ]

    def test_all_agents_have_team_worker_protocol(self):
        missing = []
        for name in self.P1_P3_AGENTS:
            agent_file = AGENTS_DIR / f"{name}.md"
            assert agent_file.exists(), f"Missing agent: {name}"
            content = read_contract(agent_file)
            if "## Team Worker Protocol" not in content:
                missing.append(name)
        assert missing == [], f"P1-P3 agents missing Team Worker Protocol: {missing}"


class TestWriteRestrictedProtocol:
    """Validate write-restricted agents have SendMessage-to-leader pattern."""

    WRITE_RESTRICTED = [
        "vcodec-architecture-expert",
        "arch-designer",
        "timing-advisor",
    ]

    def test_write_restricted_agents_have_sendmessage_note(self):
        missing = []
        for name in self.WRITE_RESTRICTED:
            agent_file = AGENTS_DIR / f"{name}.md"
            content = read_contract(agent_file)
            if "Write-restricted" not in content and "write-restricted" not in content:
                missing.append(name)
        assert missing == [], f"Write-restricted agents missing SendMessage note: {missing}"

    def test_write_restricted_mentioned_in_orchestrators(self):
        for name in ('p1-research','p2-arch','p3-uarch','p4-implement','p5-verify'):
            content = read_contract(AGENTS_DIR / (name + '-orchestrator.md'))
            assert 'restricted writes' in content
            assert '.rat/scratch/' in content


class TestAutopilotP1P3TeamAwareness:
    """Validate autopilot skill and orchestrator team-awareness for P1-P3."""

    def test_autopilot_skill_sequences_team_skills(self):
        """In team mode, autopilot skill invokes phase team skills."""
        skill = SKILLS_DIR / "rat-auto-design" / "SKILL.md"
        content = read_contract(skill)
        assert 'Skill(skill="rtl-agent-team:p1-spec-research", args="team $ARGUMENTS {review_scope}")' in content
        assert 'Skill(skill="rtl-agent-team:p2-arch-design", args="team Phase 1 complete {review_scope}")' in content
        assert 'Skill(skill="rtl-agent-team:rtl-p3-uarch-design", args="team Phase 2 complete {review_scope}")' in content
        assert 'Skill(skill="rtl-agent-team:rtl-p4-implement", args="team Phase 3 complete {review_scope}")' in content
        assert 'Skill(skill="rtl-agent-team:rtl-p5-verify", args="team Phase 4 complete {review_scope}")' in content

    def test_autopilot_orchestrator_references_p1_team_orchestrator(self):
        """Autopilot orchestrator (sequential mode) still references team orchestrators."""
        content = read_contract(AGENTS_DIR / "autopilot-orchestrator.md")
        assert "p1-research-orchestrator" in content

    def test_autopilot_orchestrator_references_p2_team_orchestrator(self):
        content = read_contract(AGENTS_DIR / "autopilot-orchestrator.md")
        assert "p2-arch-orchestrator" in content

    def test_autopilot_orchestrator_references_p3_team_orchestrator(self):
        content = read_contract(AGENTS_DIR / "autopilot-orchestrator.md")
        assert "p3-uarch-orchestrator" in content


# ── Skill as Leader Contract Tests ─────────────────────────────────────────


class TestTeamSkillContract:
    """Validate that team skills contain team lifecycle primitives (Skill as Leader)."""

    PHASE_TEAMS = {
        "p1-spec-research": "p1-research",
        "p2-arch-design": "p2-arch",
        "rtl-p3-uarch-design": "p3-uarch",
        "rtl-p4-implement": "p4-implement",
        "rtl-p5-verify": "p5-verify",
    }

    @pytest.mark.parametrize("skill_name,team", PHASE_TEAMS.items())
    def test_team_entrypoint_dispatches_to_phase_owner(self, skill_name, team):
        content = read_contract(SKILLS_DIR / skill_name / "SKILL.md")
        frontmatter = content.split("---", 2)[1]
        allowed = re.search(r"^allowed-tools: (.*)$", frontmatter, re.M).group(1)
        assert {"TeamCreate", "Agent", "SendMessage", "TeamDelete", "Write"} <= set(allowed.split(", "))

        sequential, team_section = content.split("## Team mode", 1)
        coordinator = f"rtl-agent-team:{team}-orchestrator"
        assert f'Task(subagent_type="{coordinator}"' in sequential
        assert coordinator in team_section and f"`{team}`" in team_section
        assert "$ARGUMENTS" in team_section
        resource = "runtime/workflows/team-leader.md"
        assert resource in team_section and resource not in sequential
        assert (REPO_ROOT / resource).is_file()
        assert "mandatory Codex cross-review" not in content
        assert not re.search(r'"worker_count":\s*[1-9]|while True:', team_section)

    def test_shared_leader_contract_preserves_lifecycle(self):
        leader = read_contract(REPO_ROOT / "runtime/workflows/team-leader.md")
        ordered = [
            "TeamCreate", "Write", ".rat/state/team-config.json",
            'name="coordinator"', "independent work", "completion message",
            "phase gate", "shutdown_request", "TeamDelete()", ".rat/state/team-config.json",
        ]
        start = 0
        for token in ordered:
            start = leader.index(token, start) + len(token)
        assert "sequential entry" in leader
        assert "mandatory Codex cross-review" not in leader
        assert not re.search(r'"worker_count":\s*[1-9]|while True:', leader)

    def test_team_orchestrators_signal_only_after_phase_gate(self):
        """v0.12.0: each team orchestrator's Signal completion bullet must fire
        ONLY after the phase gate / post-gate steps — never when the task graph
        merely drains ('when all tasks are done')."""
        orchestrators = [
            "p1-research-orchestrator",
            "p2-arch-orchestrator",
            "p3-uarch-orchestrator",
            "p4-implement-orchestrator",
            "p5-verify-orchestrator",
        ]
        for name in orchestrators:
            content = read_contract(AGENTS_DIR / f"{name}.md")
            assert "Signal completion" in content, (
                f"{name} missing Signal completion bullet"
            )
            assert "ONLY after the phase gate" in content, (
                f"{name} Signal completion must fire ONLY after the phase gate"
            )
            assert "when all tasks are done" not in content, (
                f"{name} must not use the old 'when all tasks are done' wording"
            )


class TestTeamOrchestratorTeammateContract:
    """Validate orchestrators have Coordination Teammate Role and CAN use SendMessage."""

    ALL_TEAM_ORCHESTRATORS = [
        "p1-research-orchestrator",
        "p2-arch-orchestrator",
        "p3-uarch-orchestrator",
        "p4-implement-orchestrator",
        "p5-verify-orchestrator",
    ]

    @pytest.mark.parametrize("orch_name", ALL_TEAM_ORCHESTRATORS)
    def test_has_coordination_teammate_role_section(self, orch_name):
        """All team orchestrators must have Coordination Teammate Role section."""
        content = read_contract(AGENTS_DIR / f"{orch_name}.md")
        assert "Coordination Teammate Role" in content

    @pytest.mark.parametrize("orch_name", ALL_TEAM_ORCHESTRATORS)
    def test_lists_forbidden_operations(self, orch_name):
        """Coordination Teammate Role must list FORBIDDEN operations."""
        content = read_contract(AGENTS_DIR / f"{orch_name}.md")
        assert "FORBIDDEN" in content

    @pytest.mark.parametrize("orch_name", ALL_TEAM_ORCHESTRATORS)
    def test_sendmessage_not_in_forbidden(self, orch_name):
        """SendMessage must NOT be in FORBIDDEN list (coordinator needs it)."""
        content = read_contract(AGENTS_DIR / f"{orch_name}.md")
        # Extract the FORBIDDEN line
        for line in content.split('\n'):
            if 'FORBIDDEN' in line and '**' in line:
                assert 'SendMessage' not in line, \
                    f"{orch_name} still has SendMessage in FORBIDDEN"
                break

    @pytest.mark.parametrize("orch_name", ALL_TEAM_ORCHESTRATORS)
    def test_sendmessage_in_allowed(self, orch_name):
        """SendMessage must be in ALLOWED list."""
        content = read_contract(AGENTS_DIR / f"{orch_name}.md")
        for line in content.split('\n'):
            if 'ALLOWED' in line and '**' in line:
                assert 'SendMessage' in line, \
                    f"{orch_name} missing SendMessage in ALLOWED"
                break

    @pytest.mark.parametrize("orch_name", ALL_TEAM_ORCHESTRATORS)
    def test_uses_task_coordination(self, orch_name):
        """Orchestrators must use TaskCreate for coordination."""
        content = read_contract(AGENTS_DIR / f"{orch_name}.md")
        assert "TaskCreate" in content


class TestWorkerSubagentPattern:
    """Validate worker preamble documents Task() specialist delegation and coordinator messaging."""

    def test_preamble_documents_specialist_delegation(self):
        """Preamble must document Task() specialist delegation pattern."""
        preamble = AGENT_LIB_DIR / "team-worker-preamble.md"
        content = read_contract(preamble)
        assert "Task(" in content or "specialist" in content.lower(), \
            "Preamble must document Task() specialist delegation"

    def test_preamble_sendmessage_to_coordinator(self):
        """Preamble must show SendMessage recipient as coordinator, not leader."""
        preamble = AGENT_LIB_DIR / "team-worker-preamble.md"
        content = read_contract(preamble)
        assert "coordinator" in content.lower(), \
            "Preamble must reference coordinator as SendMessage recipient"

    def test_protocol_report_step_targets_coordinator(self):
        """Protocol REPORT step must target coordinator."""
        protocol = AGENT_LIB_DIR / "team-worker-protocol.md"
        content = read_contract(protocol)
        assert "coordinator" in content.lower(), \
            "Protocol must reference coordinator in REPORT step"

    def test_protocol_has_delegate_step(self):
        """Protocol must document specialist Task() delegation."""
        protocol = AGENT_LIB_DIR / "team-worker-protocol.md"
        content = read_contract(protocol)
        assert "DELEGATE" in content, \
            "Protocol must have DELEGATE step for Task() specialist spawning"

    def test_specialist_agents_have_team_worker_protocol_expanded(self):
        """All 34 specialist agents (28 existing + 6 added) must have Team Worker Protocol."""
        missing = []
        for name in self._expanded_list():
            agent_file = AGENTS_DIR / f"{name}.md"
            if not agent_file.exists():
                continue
            content = read_contract(agent_file)
            if "## Team Worker Protocol" not in content:
                missing.append(name)
        assert missing == [], f"Agents missing Team Worker Protocol: {missing}"

    def test_inject_script_target_list_matches_tested_contract(self):
        """scripts/inject-worker-protocol.sh must target exactly this set.

        The script's DEFAULT_AGENTS list and the expanded list above are the only
        two places the worker-protocol membership set is written down. When they
        drift, running the documented sync script rewrites agents CI never asked
        for — v0.14.1 shipped a script listing 4 agents the tests did not require
        and omitting 5 they did.
        """
        script = read_contract(REPO_ROOT / "scripts" / "inject-worker-protocol.sh")
        script_agents = set()
        for var in ("P4_P5_AGENTS", "P1_P3_AGENTS", "VPROC_AGENTS", "MISC_AGENTS"):
            m = re.search(rf'^{var}="([^"]*)"', script, re.M)
            assert m, f"{var} not found in inject-worker-protocol.sh"
            script_agents.update(m.group(1).split())

        tested = set(self._expanded_list())
        assert script_agents == tested, (
            "inject-worker-protocol.sh default targets are out of sync with "
            "test_specialist_agents_have_team_worker_protocol_expanded.\n"
            f"  script-only: {sorted(script_agents - tested)}\n"
            f"  tests-only : {sorted(tested - script_agents)}"
        )

    @staticmethod
    def _expanded_list():
        return [
            "rtl-coder", "lint-checker", "rtl-critic", "testbench-dev", "eda-runner",
            "sva-extractor", "cdc-checker", "protocol-checker",
            "func-verifier", "coverage-analyst", "perf-verifier",
            "spec-analyst", "vcodec-chief-standard-expert", "rtl-architect",
            "vcodec-architecture-expert", "arch-designer", "power-analyzer",
            "vcodec-syntax-entropy-expert", "vcodec-intra-pred-expert",
            "vcodec-me-expert", "vcodec-mc-expert",
            "vcodec-transform-quant-expert", "vcodec-filter-recon-expert",
            "video-processing-expert", "ref-model-dev", "bfm-dev", "timing-advisor",
            "vproc-image-processing-expert", "vproc-denoise-expert", "vproc-color-format-expert",
            "constraint-writer", "synthesis-reporter", "ref-model-reviewer", "uarch-designer",
        ]
