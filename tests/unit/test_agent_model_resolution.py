import json
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import resolve_agent_model as resolver


@pytest.mark.parametrize(("tier", "alias", "family"), [
    ("complex", "fable", "astra"), ("design", "opus", "sol"),
    ("straightforward", "sonnet", "terra"), ("trivial", "haiku", "luna"),
])
def test_host_native_families(monkeypatch, tier, alias, family):
    models = [
        {"slug": f"old-{family}", "priority": 5},
        {"slug": f"hidden-{family}", "priority": 1, "visibility": "hide"},
        {"slug": f"current-{family}", "priority": 2},
    ]
    monkeypatch.setattr(resolver, "catalog_output", lambda host: json.dumps({"models": models}))
    assert resolver.resolve("codex", tier) == f"current-{family}"
    assert resolver.resolve("claude", tier) == alias


def test_agy_uses_installed_native_families():
    catalog = ("Fetching available models...\n"
               "gemini-pro-orchestrator-example\tOrchestrator (Example)\n"
               "gemini-4-argon-high\tGemini 4 Argon (High)\n"
               "gemini-4-hydrogen-high\tGemini 4 Hydrogen (High)\n"
               "gemini-3.8-flash-medium\tGemini Flash (Medium)\n")
    assert resolver.agy_model(catalog, "complex") == "gemini-pro-orchestrator-example"
    assert resolver.agy_model(catalog, "design") == "gemini-4-argon-high"
    assert resolver.agy_model(catalog, "straightforward") == "gemini-4-hydrogen-high"
    assert resolver.agy_model(catalog, "trivial") == "gemini-3.8-flash-medium"
    assert resolver.agy_model("claude-opus-example\tClaude Opus\n", "complex") == ""


def test_grok_uses_advertised_default_and_fast_variant():
    catalog = "Default model: grok-example\n  * grok-example (default)\n  - grok-example-fast\n"
    assert resolver.grok_model(catalog, "design") == "grok-example"
    assert resolver.grok_model(catalog, "trivial") == "grok-example-fast"
    assert resolver.grok_model(catalog.split("  - ")[0], "trivial") == "grok-example"
    assert resolver.grok_model("Default model: missing\n", "complex") == ""


def test_native_fallback_and_explicit_id_without_cli(tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(tmp_path))
    script = Path(resolver.__file__)
    command = [sys.executable, str(script), "--host", "codex", "--agent", "rtl-architect"]
    assert subprocess.check_output(command, text=True) == ""
    assert subprocess.check_output(command + ["--model", "my-model"], text=True).strip() == "my-model"


def test_explicit_codex_family_selects_available_full_id(monkeypatch, capsys):
    monkeypatch.setattr(sys, "argv", ["resolver", "--host", "codex", "--agent", "rtl-architect",
                                      "--model", "sol"])
    catalog = {"models": [{"slug": "example-sol", "priority": 1}]}
    monkeypatch.setattr(resolver, "catalog_output", lambda host: json.dumps(catalog))
    resolver.main()
    assert capsys.readouterr().out.strip() == "example-sol"
    catalog["models"].clear()
    with pytest.raises(SystemExit) as error:
        resolver.main()
    assert error.value.code != 0


def test_unknown_agent_and_malformed_catalog():
    with pytest.raises(ValueError):
        resolver.agent_tier("../wrong")
    assert resolver.agent_tier("rtl-agent-team:rtl-architect") == "complex"
    assert resolver.agent_tier("eda-runner") == "straightforward"
    assert resolver.codex_model('{"models": {}}', "sol") == ""
    assert resolver.codex_model("unavailable", "sol") == ""
