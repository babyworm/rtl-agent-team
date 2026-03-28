"""Tests for audit logging infrastructure.

Validates:
- audit-util.sh: session init, trace append, prompt save, prune
- rtl-audit-init.sh: SessionStart hook behavior
- rtl-audit-subagent.sh: SubagentStart/Stop diagnostic capture
- rtl-audit-spawn-complete.sh: PostToolUse:TaskCreate trace
- Hook trace extensions in spawn-context, edit-tracker, skill-activation
"""

import json
import os
from pathlib import Path

import pytest

from tests.conftest import HOOKS_DIR, REPO_ROOT, run_hook


# ── audit-util.sh tests ─────────────────────────────────────────────────────


class TestAuditUtil:
    """Tests for hooks/lib/audit-util.sh utility functions."""

    def _source_and_run(self, tmp_project, script, env=None):
        """Source audit-util.sh and run a shell snippet, return stdout."""
        import subprocess

        preamble = f"""
SCRIPT_DIR="{HOOKS_DIR}"
. "{HOOKS_DIR}/lib/json-util.sh"
jsonu_detect_parser
. "{HOOKS_DIR}/lib/flock-util.sh"
. "{HOOKS_DIR}/lib/rat-dir-util.sh"
. "{HOOKS_DIR}/lib/audit-util.sh"
"""
        merged_env = {**os.environ, **(env or {})}
        result = subprocess.run(
            ["sh", "-c", preamble + script],
            capture_output=True,
            text=True,
            env=merged_env,
            timeout=10,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode

    def test_init_session_creates_directory(self, tmp_project):
        stdout, _, rc = self._source_and_run(
            tmp_project,
            f'audit_init_session "{tmp_project}" && echo OK',
        )
        assert "OK" in stdout
        audit_dir = tmp_project / ".rat" / "audit"
        assert audit_dir.exists()

    def test_init_session_creates_session_id_file(self, tmp_project):
        self._source_and_run(
            tmp_project,
            f'audit_init_session "{tmp_project}"',
        )
        sid_file = tmp_project / ".rat" / "audit" / "session-id.txt"
        assert sid_file.exists()
        assert len(sid_file.read_text().strip()) > 0

    def test_init_session_uses_claude_session_id(self, tmp_project):
        self._source_and_run(
            tmp_project,
            f'audit_init_session "{tmp_project}"',
            env={"CLAUDE_SESSION_ID": "test-session-123"},
        )
        sid_file = tmp_project / ".rat" / "audit" / "session-id.txt"
        assert sid_file.read_text().strip() == "test-session-123"

    def test_init_session_creates_prompts_dir(self, tmp_project):
        self._source_and_run(
            tmp_project,
            f'audit_init_session "{tmp_project}"',
            env={"CLAUDE_SESSION_ID": "sess-001"},
        )
        prompts = tmp_project / ".rat" / "audit" / "sess-001" / "prompts"
        assert prompts.is_dir()

    def test_init_session_rejects_non_rtl_project(self, tmp_path):
        """Should return 1 for directories without RTL markers."""
        stdout, _, rc = self._source_and_run(
            tmp_path,
            f'audit_init_session "{tmp_path}" && echo OK || echo SKIP',
        )
        assert "SKIP" in stdout

    def test_session_id_cached(self, tmp_project):
        stdout, _, _ = self._source_and_run(
            tmp_project,
            f'audit_init_session "{tmp_project}" && '
            f'ID1=$(audit_session_id "{tmp_project}") && '
            f'ID2=$(audit_session_id "{tmp_project}") && '
            f'[ "$ID1" = "$ID2" ] && echo MATCH || echo MISMATCH',
        )
        assert "MATCH" in stdout

    def test_trace_append_creates_jsonl(self, tmp_project):
        self._source_and_run(
            tmp_project,
            f'audit_init_session "{tmp_project}" && '
            f'audit_trace_append "{tmp_project}" '
            f'\'{{"event":"test","agent":"tester","status":"started"}}\'',
            env={"CLAUDE_SESSION_ID": "trace-test"},
        )
        trace = tmp_project / ".rat" / "audit" / "trace-test" / "trace.jsonl"
        assert trace.exists()
        line = json.loads(trace.read_text().strip())
        assert line["event"] == "test"
        assert line["agent"] == "tester"
        assert line["seq"] == 1
        assert "ts" in line

    def test_trace_append_increments_seq(self, tmp_project):
        self._source_and_run(
            tmp_project,
            f'audit_init_session "{tmp_project}" && '
            f'audit_trace_append "{tmp_project}" \'{{"event":"e1","agent":"a"}}\' >/dev/null && '
            f'audit_trace_append "{tmp_project}" \'{{"event":"e2","agent":"a"}}\' >/dev/null && '
            f'audit_trace_append "{tmp_project}" \'{{"event":"e3","agent":"a"}}\'',
            env={"CLAUDE_SESSION_ID": "seq-test"},
        )
        trace = tmp_project / ".rat" / "audit" / "seq-test" / "trace.jsonl"
        lines = [json.loads(l) for l in trace.read_text().strip().splitlines()]
        assert len(lines) == 3
        assert [l["seq"] for l in lines] == [1, 2, 3]
        assert [l["event"] for l in lines] == ["e1", "e2", "e3"]

    def test_trace_append_returns_seq(self, tmp_project):
        stdout, _, _ = self._source_and_run(
            tmp_project,
            f'audit_init_session "{tmp_project}" && '
            f'SEQ=$(audit_trace_append "{tmp_project}" \'{{"event":"x","agent":"a"}}\') && '
            f'echo "SEQ=$SEQ"',
            env={"CLAUDE_SESSION_ID": "ret-test"},
        )
        assert "SEQ=1" in stdout

    def test_save_prompt(self, tmp_project):
        self._source_and_run(
            tmp_project,
            f'audit_init_session "{tmp_project}" && '
            f'audit_save_prompt "{tmp_project}" "1" "spec-analyst" "Analyze the spec"',
            env={"CLAUDE_SESSION_ID": "prompt-test"},
        )
        prompt_file = (
            tmp_project
            / ".rat"
            / "audit"
            / "prompt-test"
            / "prompts"
            / "001_spec-analyst.md"
        )
        assert prompt_file.exists()
        assert "Analyze the spec" in prompt_file.read_text()

    def test_save_prompt_zero_pads_seq(self, tmp_project):
        self._source_and_run(
            tmp_project,
            f'audit_init_session "{tmp_project}" && '
            f'audit_save_prompt "{tmp_project}" "42" "agent-x" "content"',
            env={"CLAUDE_SESSION_ID": "pad-test"},
        )
        files = list(
            (tmp_project / ".rat" / "audit" / "pad-test" / "prompts").glob(
                "*.md"
            )
        )
        assert any("042_agent-x.md" in f.name for f in files)

    def test_validate_session_id_rejects_path_traversal(self, tmp_project):
        """Path traversal attempts like ../../etc, .., a/b/c should be sanitized."""
        for bad_id in ["../../etc", "..", "a/b/c", "../passwd"]:
            stdout, _, rc = self._source_and_run(
                tmp_project,
                f'RESULT=$(_audit_validate_session_id "{bad_id}") && '
                f'[ "$RESULT" != "{bad_id}" ] && echo REJECTED || echo ACCEPTED',
            )
            assert "REJECTED" in stdout, (
                f"Path traversal ID {bad_id!r} was not rejected"
            )

    def test_validate_session_id_rejects_hidden(self, tmp_project):
        """Hidden directory names like .hidden should be sanitized."""
        stdout, _, rc = self._source_and_run(
            tmp_project,
            'RESULT=$(_audit_validate_session_id ".hidden") && '
            '[ "$RESULT" != ".hidden" ] && echo REJECTED || echo ACCEPTED',
        )
        assert "REJECTED" in stdout

    def test_validate_session_id_rejects_empty(self, tmp_project):
        """Empty string should be sanitized to a generated fallback."""
        stdout, _, rc = self._source_and_run(
            tmp_project,
            'RESULT=$(_audit_validate_session_id "") && '
            '[ -n "$RESULT" ] && echo NONEMPTY || echo EMPTY',
        )
        assert "NONEMPTY" in stdout

    def test_validate_session_id_accepts_valid(self, tmp_project):
        """Normal alphanumeric IDs should pass through unchanged."""
        for valid_id in ["abc-123", "session_2024", "test-run-42", "A1B2C3"]:
            stdout, _, rc = self._source_and_run(
                tmp_project,
                f'RESULT=$(_audit_validate_session_id "{valid_id}") && '
                f'[ "$RESULT" = "{valid_id}" ] && echo PASS || echo FAIL',
            )
            assert "PASS" in stdout, (
                f"Valid session ID {valid_id!r} was not accepted"
            )

    def test_prune_removes_old_sessions(self, tmp_project):
        audit_dir = tmp_project / ".rat" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        # Create 12 session dirs with deterministic mtimes
        base_time = 1000000000  # fixed epoch
        for i in range(12):
            d = audit_dir / f"session-{i:03d}"
            d.mkdir()
            (d / "trace.jsonl").write_text(f'{{"seq":{i}}}\n')
            os.utime(str(d), (base_time + i * 10, base_time + i * 10))

        self._source_and_run(
            tmp_project,
            f'audit_prune "{tmp_project}" 10',
        )
        remaining = [d for d in audit_dir.iterdir() if d.is_dir()]
        assert len(remaining) <= 10


# ── rtl-audit-init.sh tests ─────────────────────────────────────────────────


class TestAuditInitHook:
    """Tests for hooks/rtl-audit-init.sh SessionStart hook."""

    HOOK = HOOKS_DIR / "rtl-audit-init.sh"

    def test_creates_audit_dir_for_rtl_project(self, tmp_project):
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        audit_dir = tmp_project / ".rat" / "audit"
        assert audit_dir.exists()

    def test_creates_session_id_file(self, tmp_project):
        run_hook(self.HOOK, {"cwd": str(tmp_project)})
        sid_file = tmp_project / ".rat" / "audit" / "session-id.txt"
        assert sid_file.exists()

    def test_logs_session_start_event(self, tmp_project):
        run_hook(
            self.HOOK,
            {"cwd": str(tmp_project)},
            env={"CLAUDE_SESSION_ID": "init-test"},
        )
        trace = (
            tmp_project / ".rat" / "audit" / "init-test" / "trace.jsonl"
        )
        assert trace.exists()
        line = json.loads(trace.read_text().strip().splitlines()[0])
        assert line["event"] == "session_start"

    def test_skips_non_rtl_project(self, tmp_path):
        """Non-RTL directories should not get audit initialized."""
        result = run_hook(self.HOOK, {"cwd": str(tmp_path)})
        audit_dir = tmp_path / ".rat" / "audit"
        assert not audit_dir.exists()

    def test_silent_output(self, tmp_project):
        """SessionStart audit hook should produce no stdout JSON."""
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        # run_hook returns raw_stdout for non-JSON output
        assert "raw_stdout" in result or result == {}


# ── rtl-audit-subagent.sh tests ──────────────────────────────────────────────


class TestAuditSubagentHook:
    """Tests for hooks/rtl-audit-subagent.sh diagnostic hook."""

    HOOK = HOOKS_DIR / "rtl-audit-subagent.sh"

    def test_logs_to_diagnostic_file(self, tmp_project):
        (tmp_project / ".rat" / "audit").mkdir(parents=True, exist_ok=True)
        sid_file = tmp_project / ".rat" / "audit" / "session-id.txt"
        sid_file.write_text("subagent-test")
        (tmp_project / ".rat" / "audit" / "subagent-test").mkdir()

        run_hook(self.HOOK, {"cwd": str(tmp_project), "agent_type": "rtl-agent-team:spec-analyst"})
        diag = (
            tmp_project
            / ".rat"
            / "audit"
            / "subagent-test"
            / "subagent-debug.jsonl"
        )
        assert diag.exists()
        line = json.loads(diag.read_text().strip().splitlines()[0])
        assert "ts" in line
        assert "raw_input" in line

    def test_skips_without_audit_dir(self, tmp_path):
        """No audit dir → no-op (no crash)."""
        run_hook(self.HOOK, {"cwd": str(tmp_path)})
        # Should not crash — just exit silently


# ── rtl-audit-spawn-complete.sh tests ────────────────────────────────────────


class TestAuditSpawnComplete:
    """Tests for hooks/rtl-audit-spawn-complete.sh PostToolUse:TaskCreate."""

    HOOK = HOOKS_DIR / "rtl-audit-spawn-complete.sh"

    def _setup_audit(self, tmp_project, sid="spawn-complete-test"):
        audit_dir = tmp_project / ".rat" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        (audit_dir / "session-id.txt").write_text(sid)
        (audit_dir / sid).mkdir(exist_ok=True)

    def test_logs_spawn_complete_for_rtl_agent(self, tmp_project):
        self._setup_audit(tmp_project)
        result = run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "subagent_type": "rtl-agent-team:spec-analyst"},
        )
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "SPAWN OK" in ctx
        assert "spec-analyst" in ctx

        trace = (
            tmp_project
            / ".rat"
            / "audit"
            / "spawn-complete-test"
            / "trace.jsonl"
        )
        assert trace.exists()
        line = json.loads(trace.read_text().strip())
        assert line["event"] == "spawn_complete"
        assert line["agent"] == "spec-analyst"

    def test_ignores_non_rtl_agent(self, tmp_project):
        result = run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "subagent_type": "oh-my-claudecode:executor"},
        )
        assert result["continue"] is True
        assert "hookSpecificOutput" not in result

    def test_ignores_missing_subagent_type(self, tmp_project):
        result = run_hook(self.HOOK, {"cwd": str(tmp_project)})
        assert result["continue"] is True

    def test_graceful_without_audit_session(self, tmp_project):
        result = run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "subagent_type": "rtl-agent-team:rtl-coder"},
        )
        assert result["continue"] is True


# ── Trace extension tests ────────────────────────────────────────────────────


class TestEditTrackerArtifactTrace:
    """Tests for artifact_write trace in rtl-edit-tracker.sh."""

    HOOK = HOOKS_DIR / "rtl-edit-tracker.sh"

    def _setup_audit(self, tmp_project, sid="artifact-test"):
        audit_dir = tmp_project / ".rat" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        (audit_dir / "session-id.txt").write_text(sid)
        (audit_dir / sid).mkdir(exist_ok=True)

    def test_docs_file_logs_artifact_trace(self, tmp_project):
        self._setup_audit(tmp_project)
        result = run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "file_path": f"{tmp_project}/docs/phase-1-research/spec.md"},
        )
        assert result["continue"] is True
        trace = (
            tmp_project / ".rat" / "audit" / "artifact-test" / "trace.jsonl"
        )
        assert trace.exists()
        line = json.loads(trace.read_text().strip())
        assert line["event"] == "artifact_write"
        assert "spec.md" in line["detail"]

    def test_reviews_file_logs_artifact_trace(self, tmp_project):
        self._setup_audit(tmp_project)
        result = run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "file_path": f"{tmp_project}/reviews/phase-6-review/design-note.md"},
        )
        assert result["continue"] is True
        trace = (
            tmp_project / ".rat" / "audit" / "artifact-test" / "trace.jsonl"
        )
        assert trace.exists()

    def test_rtl_file_does_not_log_artifact_trace(self, tmp_project):
        """RTL files should go through the RTL tracking path, not artifact trace."""
        self._setup_audit(tmp_project)
        run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "file_path": "rtl/module/top.sv"},
        )
        trace = (
            tmp_project / ".rat" / "audit" / "artifact-test" / "trace.jsonl"
        )
        # RTL files should NOT create artifact_write trace
        if trace.exists():
            content = trace.read_text().strip()
            if content:
                line = json.loads(content)
                assert line["event"] != "artifact_write"

    def test_random_file_no_artifact_trace(self, tmp_project):
        self._setup_audit(tmp_project)
        run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "file_path": "src/utils.py"},
        )
        trace = (
            tmp_project / ".rat" / "audit" / "artifact-test" / "trace.jsonl"
        )
        assert not trace.exists()


class TestSkillActivationTrace:
    """Tests for skill_invoke trace in rtl-skill-activation.sh."""

    HOOK = HOOKS_DIR / "rtl-skill-activation.sh"

    def _setup(self, tmp_project, sid="skill-trace-test"):
        # Setup marker
        rules = tmp_project / ".claude" / "rules"
        rules.mkdir(parents=True, exist_ok=True)
        (rules / "rtl-coding-conventions.md").touch()
        # Setup audit
        audit_dir = tmp_project / ".rat" / "audit"
        audit_dir.mkdir(parents=True, exist_ok=True)
        (audit_dir / "session-id.txt").write_text(sid)
        (audit_dir / sid).mkdir(exist_ok=True)

    def test_skill_invoke_logged_when_criteria_present(self, tmp_project):
        self._setup(tmp_project)
        # Create criteria file
        criteria = {"arch-review": "review_report_complete"}
        (tmp_project / "skill-completion-criteria.json").write_text(
            json.dumps(criteria)
        )

        result = run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "skill": "rtl-agent-team:arch-review"},
            env={"CLAUDE_PLUGIN_ROOT": str(tmp_project)},
        )
        assert result["continue"] is True
        ctx = result.get("hookSpecificOutput", {}).get("additionalContext", "")
        assert "ACTIVATED" in ctx

        trace = (
            tmp_project
            / ".rat"
            / "audit"
            / "skill-trace-test"
            / "trace.jsonl"
        )
        assert trace.exists()
        line = json.loads(trace.read_text().strip())
        assert line["event"] == "skill_invoke"
        assert line["agent"] == "arch-review"

    def test_no_trace_without_criteria(self, tmp_project):
        self._setup(tmp_project)
        # rtl-p7-exploration has no completion criteria → no activation → no trace
        result = run_hook(
            self.HOOK,
            {"cwd": str(tmp_project), "skill": "rtl-agent-team:rtl-p7-exploration"},
            env={"CLAUDE_PLUGIN_ROOT": str(REPO_ROOT)},
        )
        trace = (
            tmp_project
            / ".rat"
            / "audit"
            / "skill-trace-test"
            / "trace.jsonl"
        )
        # If no criteria for this skill, no trace should be written
        if trace.exists():
            for line_str in trace.read_text().strip().splitlines():
                line = json.loads(line_str)
                assert line["event"] != "skill_invoke" or line["agent"] != "rtl-p7-exploration"


# ── Audit file structure tests ───────────────────────────────────────────────


class TestAuditFileStructure:
    """Verify audit infrastructure files exist and are well-formed."""

    def test_audit_util_exists(self):
        assert (HOOKS_DIR / "lib" / "audit-util.sh").exists()

    def test_audit_init_hook_exists(self):
        assert (HOOKS_DIR / "rtl-audit-init.sh").exists()

    def test_audit_subagent_hook_exists(self):
        assert (HOOKS_DIR / "rtl-audit-subagent.sh").exists()

    def test_audit_spawn_complete_hook_exists(self):
        assert (HOOKS_DIR / "rtl-audit-spawn-complete.sh").exists()

    def test_audit_util_has_required_functions(self):
        content = (HOOKS_DIR / "lib" / "audit-util.sh").read_text()
        for func in [
            "audit_init_session",
            "audit_trace_append",
            "audit_save_prompt",
            "audit_session_id",
            "audit_prune",
        ]:
            assert func in content, f"Missing function: {func}"

    def test_audit_util_sources_dependencies(self):
        """audit-util.sh should be designed to work with json-util and flock-util."""
        content = (HOOKS_DIR / "lib" / "audit-util.sh").read_text()
        # It references flock functions
        assert "acquire_lock" in content
        assert "release_lock" in content

    def test_show_audit_script_exists(self):
        script = REPO_ROOT / "scripts" / "show-audit.sh"
        assert script.exists()

    def test_generate_audit_summary_script_exists(self):
        script = REPO_ROOT / "scripts" / "generate-audit-summary.sh"
        assert script.exists()

    def test_hooks_json_registers_audit_hooks(self):
        hooks = json.loads((HOOKS_DIR / "hooks.json").read_text())
        # SessionStart includes audit-init
        ss_commands = [
            h["command"]
            for h in hooks["hooks"]["SessionStart"][0]["hooks"]
        ]
        assert any("rtl-audit-init.sh" in c for c in ss_commands)

        # SubagentStart/Stop registered
        assert "SubagentStart" in hooks["hooks"]
        assert "SubagentStop" in hooks["hooks"]

        # PostToolUse:TaskCreate has spawn-complete
        tc_matchers = [e for e in hooks["hooks"]["PostToolUse"] if e["matcher"] == "TaskCreate"]
        assert len(tc_matchers) == 1
        tc_commands = [h["command"] for h in tc_matchers[0]["hooks"]]
        assert any("rtl-audit-spawn-complete.sh" in c for c in tc_commands)
