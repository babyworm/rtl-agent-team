"""Exercise the optional cross-review CLI with a local Codex executable double."""
import json
from pathlib import Path
import subprocess
import sys

import pytest

from tests.conftest import REPO_ROOT

SKILL = REPO_ROOT / "skills" / "codex-cross-review"
APPROVAL = {"verdict": "APPROVE", "findings": [], "resolved_items": [], "summary": "Checked."}


@pytest.fixture
def project(tmp_path, monkeypatch):
    tools = tmp_path / "bin"
    tools.mkdir()
    fake = tools / "codex"
    fake.write_text(f"#!{sys.executable}\n" + '''
import json, os, sys
from pathlib import Path

args = sys.argv[1:]
record = {"args": args, "cwd": str(Path.cwd())}
if args[:1] == ["exec"]:
    record["prompt"] = sys.stdin.read()
with Path(os.environ["FAKE_CALLS"]).open("a") as log:
    print(json.dumps(record), file=log)
if args == ["debug", "models"]:
    print(json.dumps({"models": [{"slug": "fixture-sol", "priority": 0},
                                 {"slug": "fixture-astra", "priority": 0}]}))
elif args[:1] == ["exec"]:
    if os.environ.get("FAKE_EXIT"):
        sys.exit(int(os.environ["FAKE_EXIT"]))
    Path(args[args.index("-o") + 1]).write_text(os.environ["FAKE_RESPONSE"])
else:
    sys.exit(2)
''')
    fake.chmod(0o755)
    root = tmp_path / "work space"
    root.mkdir()
    monkeypatch.setenv("PATH", str(tools))
    monkeypatch.setenv("FAKE_CALLS", str(root / "calls.jsonl"))
    monkeypatch.setenv("FAKE_RESPONSE", json.dumps(APPROVAL))
    monkeypatch.delenv("FAKE_EXIT", raising=False)
    monkeypatch.delenv("TMUX", raising=False)
    return root


def review(root, action, *args):
    return subprocess.run(
        [sys.executable, str(SKILL / "scripts" / "review.py"), action, "--root", str(root), *args],
        stdin=subprocess.DEVNULL, text=True, capture_output=True, timeout=10, check=False,
    )


def prepare(root, phase):
    folder = root / ".rat" / "cross-review" / f"phase-{phase}"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "prompt-round-1.txt").write_text(f"Check phase {phase}.\n")
    return folder


def recorded_calls(root):
    log = root / "calls.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


@pytest.mark.parametrize(("config", "choice", "expected"), [
    (None, "project", "off"),
    ({}, "project", "off"),
    ({"review": {}}, "project", "off"),
    ({"review": {"codex_cross_review": False}}, "project", "off"),
    ({"review": {"codex_cross_review": True}}, "project", "on"),
    ({"review": {"codex_cross_review": True}}, "off", "off"),
    ({"review": {"codex_cross_review": False}}, "on", "on"),
    (None, "on", "on"),
])
def test_enabled_resolves_choice_without_starting_codex(project, config, choice, expected):
    if config is not None:
        (project / "rat_config.json").write_text(json.dumps(config))
    result = review(project, "enabled", "--choice", choice)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == expected
    if expected == "off":
        result = review(project, "run", "--phase", "4", "--choice", choice)
        assert result.returncode == 0, result.stderr
        assert not (project / ".rat").exists()
    assert not recorded_calls(project)


@pytest.mark.parametrize("invalid", [
    "{", "[]", '{"review":null}', '{"review":{"codex_cross_review":"false"}}',
    '{"review":{"codex_cross_review":1}}',
])
def test_invalid_project_choice_fails_without_starting_codex(project, invalid):
    (project / "rat_config.json").write_text(invalid)
    result = review(project, "enabled")
    assert result.returncode != 0
    assert not recorded_calls(project)


@pytest.mark.parametrize(("options", "model"), [
    ([], "fixture-sol"),
    (["--tier", "complex"], "fixture-astra"),
    (["--model", "user-selected-model"], "user-selected-model"),
])
def test_one_read_only_exchange_with_selected_model(project, options, model):
    (project / "rat_config.json").write_text(json.dumps({"review": {"codex_cross_review": True}}))
    folder = prepare(project, "5a")
    result = review(project, "run", "--phase", "5a", *options)
    assert result.returncode == 0, result.stderr
    exchanges = [call for call in recorded_calls(project) if call["args"][:1] == ["exec"]]
    assert len(exchanges) == 1
    assert exchanges[0]["cwd"] == str(project)
    assert exchanges[0]["prompt"] == (folder / "prompt-round-1.txt").read_text()
    args = exchanges[0]["args"]
    assert args[args.index("-s") + 1] == "read-only"
    assert Path(args[args.index("--output-schema") + 1]) == SKILL / "review-schema.json"
    assert args[args.index("-m") + 1] == model
    assert json.loads((folder / "round-1.json").read_text()) == APPROVAL


def test_functional_and_silicon_reviews_have_independent_results(project, monkeypatch):
    finding = {"id": "F1", "severity": "major", "category": "correctness", "file": "dut.sv",
               "line": 17, "description": "Unexpected reset value.", "suggestion": None}
    responses = {"5a": {**APPROVAL, "verdict": "REQUEST_CHANGES", "findings": [finding]},
                 "5b": APPROVAL}
    for phase, response in responses.items():
        prepare(project, phase)
        monkeypatch.setenv("FAKE_RESPONSE", json.dumps(response))
        result = review(project, "run", "--phase", phase, "--choice", "on")
        assert result.returncode == 0, result.stderr
    for phase, response in responses.items():
        output = project / ".rat" / "cross-review" / f"phase-{phase}" / "round-1.json"
        assert json.loads(output.read_text()) == response
    assert len([call for call in recorded_calls(project) if call["args"][:1] == ["exec"]]) == 2


@pytest.mark.parametrize(("failure", "expected_runs"), [
    ("command error", 1), ("bad JSON", 1), ("bad verdict", 1), ("bad finding", 1),
    ("missing prompt", 0), ("empty prompt", 0),
])
def test_failed_review_does_not_retry_or_leave_completion_marker(project, monkeypatch, failure, expected_runs):
    folder = prepare(project, "5b")
    marker = project / ".rat" / "state" / "cross-review-phase-5b-done"
    marker.parent.mkdir()
    marker.touch()
    if failure == "command error":
        monkeypatch.setenv("FAKE_EXIT", "7")
    elif failure == "bad JSON":
        monkeypatch.setenv("FAKE_RESPONSE", "{")
    elif failure == "bad verdict":
        monkeypatch.setenv("FAKE_RESPONSE", json.dumps({**APPROVAL, "verdict": "MAYBE"}))
    elif failure == "bad finding":
        monkeypatch.setenv("FAKE_RESPONSE", json.dumps({**APPROVAL, "findings": ["unsupported claim"]}))
    elif failure == "missing prompt":
        (folder / "prompt-round-1.txt").unlink()
    else:
        (folder / "prompt-round-1.txt").write_text("   \n")
    result = review(project, "run", "--phase", "5b", "--choice", "on")
    assert result.returncode != 0
    assert not marker.exists()
    assert not (folder / "round-1.json").exists()
    assert len([call for call in recorded_calls(project) if call["args"][:1] == ["exec"]]) == expected_runs


@pytest.mark.parametrize(("choice", "phase", "verdict"), [
    ("2,3", "3", "on"), ("2,3", "1", "off"),
    ("5", "5A", "on"), ("5", "5b", "on"), ("5A", "5b", "off"),
])
def test_run_scope_overrides_project_per_phase(project, choice, phase, verdict):
    (project / "rat_config.json").write_text('{"review":{"codex_cross_review":true}}')
    result = review(project, "enabled", "--choice", choice, "--phase", phase)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == verdict
    assert not recorded_calls(project)
