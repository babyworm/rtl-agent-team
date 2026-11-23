#!/usr/bin/env python3
"""Compare judgment prompts on fixed fixtures, with one response per case/model."""

import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import time

ROOT = Path(__file__).resolve().parents[1]
CASES = ROOT / "evals/judgment/cases.json"
SCHEMA = ROOT / "evals/judgment/schema.json"


def read_version(path, reference=None):
    if reference:
        return subprocess.run(["git", "show", f"{reference}:{path}"], cwd=ROOT,
                              capture_output=True, text=True, check=True).stdout
    return (ROOT / path).read_text()


def runtime_prompt(agent, reference=None):
    if agent == "router":
        routing=read_version("skills/rtl-orchestrate/SKILL.md",reference)
        routing=routing.split("<!-- SESSIONSTART_HOOK_EXPORT_START -->",1)[1].split("<!-- SESSIONSTART_HOOK_EXPORT_END -->",1)[0]
        if reference:
            paths=subprocess.run(["git","ls-tree","-r","--name-only",reference,"skills"],cwd=ROOT,
                                 capture_output=True,text=True,check=True).stdout.splitlines()
            paths=[path for path in paths if path.endswith("/SKILL.md")]
        else: paths=[str(path.relative_to(ROOT)) for path in sorted((ROOT/"skills").glob("*/SKILL.md"))]
        descriptions=[]
        for path in paths:
            frontmatter=read_version(path,reference).split("---",2)[1]
            name=re.search(r"(?m)^name:\s*(.+)",frontmatter)[1]
            description=re.search(r"(?m)^description:\s*(.+)",frontmatter)[1]
            descriptions.append(name+": "+description)
        return routing+"\n\nAvailable skill registry:\n"+"\n".join(descriptions)
    text = read_version(f"agents/{agent}.md", reference)
    parts = text.split("---", 2)
    frontmatter = parts[1]
    body = parts[2].strip()
    skills = re.search(r"(?m)^skills:\s*\[([^\]]*)\]", frontmatter)
    if skills:
        for name in skills[1].split(","):
            name = name.strip().strip("\"'")
            if name:
                skill = read_version(f"skills/{name}/SKILL.md", reference)
                body += "\n\n" + skill.split("---", 2)[2].strip()
    workflow = f"runtime/workflows/{agent}-sequential.md"
    if not reference and (ROOT / workflow).is_file():
        body += "\n\n" + read_version(workflow)
    return body


def grade(response, expected):
    if not isinstance(response, dict):
        return ["response is not a JSON object"]
    failures=[]
    for key,value in expected.items():
        actual=response.get(key)
        if key=="route" and isinstance(actual,str): actual=actual.removeprefix("/rtl-agent-team:").removeprefix("rtl-agent-team:")
        if actual!=value: failures.append(key)
    return failures


def evaluate(case, model, reference, destination, schema, case_budget):
    system = runtime_prompt(case["agent"], reference)
    instruction = ("This is a read-only judgment evaluation. Context bootstrap, artifact reads, and the one required review "
                   "are already complete. The following fixture supplies the authoritative remaining state. "
                   "Do not call tools, initialize a project, write files, or schedule agents. Return only the JSON assessment.\n\n"
                   + case["task"])
    destination.mkdir(parents=True, exist_ok=True)
    started = time.monotonic()
    response = None
    record = {"case": case["id"], "model_requested": model, "reference": reference or "working-tree",
              "prompt_bytes": len(system.encode()), "prompt_words": len(system.split()),
              "prompt_sha256": hashlib.sha256(system.encode()).hexdigest()}
    (destination / "system_prompt.txt").write_text(system)
    with tempfile.TemporaryDirectory(prefix="rat-prompt-eval-") as directory:
        work = Path(directory)
        if model.startswith("gpt-"):
            output = work / "response.json"
            command = ["codex", "exec", "--ephemeral", "--skip-git-repo-check", "--sandbox", "read-only",
                       "--output-schema", str(SCHEMA), "--output-last-message", str(output), "--model", model,
                       "--json", "-"]
            prompt = system + "\n\n" + instruction
        else:
            command = ["claude", "--print", "--model", model, "--tools", "", "--disable-slash-commands",
                       "--strict-mcp-config", "--mcp-config", '{"mcpServers":{}}', "--setting-sources", "",
                       "--settings", '{"disableAllHooks":true}', "--no-session-persistence",
                       "--max-budget-usd", str(case_budget), "--output-format", "json", "--json-schema", json.dumps(schema),
                       "--system-prompt", system]
            prompt = instruction
        try:
            result = subprocess.run(command, input=prompt, cwd=work, capture_output=True, text=True, timeout=180)
            (destination / "stdout.txt").write_text(result.stdout)
            (destination / "stderr.txt").write_text(result.stderr)
            record["exit_code"] = result.returncode
            if model.startswith("gpt-"):
                if output.exists():
                    response = json.loads(output.read_text())
            else:
                envelope = json.loads(result.stdout)
                if envelope.get("is_error"):
                    record["unavailable"] = envelope.get("api_error", envelope.get("result", "provider error"))
                    raise ValueError("provider unavailable: " + record["unavailable"])
                response = envelope.get("structured_output")
                if response is None and envelope.get("result"):
                    response = json.loads(envelope["result"])
                record["model_usage"] = envelope.get("modelUsage", {})
                record["cost_usd"] = envelope.get("total_cost_usd")
            record["response"] = response
            record["failures"] = grade(response, case["expected"])
        except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
            record["error"] = str(exc)
            record["failures"] = ["execution unavailable or response invalid"]
    record["elapsed_seconds"] = time.monotonic() - started
    (destination / "result.json").write_text(json.dumps(record, indent=2) + "\n")
    return record


def main():
    global CASES, SCHEMA
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", choices=["judgment", "routing"], default="judgment")
    parser.add_argument("--models", default="fable,opus,gpt-6.1-sol")
    parser.add_argument("--variant", choices=["baseline", "current", "both"], default="current")
    parser.add_argument("--baseline-ref", default="0db2ba5")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--case", action="append")
    parser.add_argument("--claude-case-budget", type=float, default=0.5)
    args = parser.parse_args()
    CASES=ROOT / ("evals/"+args.suite+"/cases.json")
    SCHEMA=ROOT / ("evals/"+args.suite+"/schema.json")
    cases = json.loads(CASES.read_text())
    schema = json.loads(SCHEMA.read_text())
    variants = ["baseline", "current"] if args.variant == "both" else [args.variant]
    results = []
    unavailable_models = {}
    for variant in variants:
        for model in args.models.split(","):
            for case in cases:
                if args.case and case["id"] not in args.case:
                    continue
                reference = args.baseline_ref if variant == "baseline" else None
                if model in unavailable_models:
                    result={"case":case["id"],"model_requested":model,"reference":reference or "working-tree",
                            "unavailable":unavailable_models[model],"failures":["provider unavailable; request skipped"],
                            "elapsed_seconds":0.0}
                else:
                    result = evaluate(case, model, reference, args.output / variant / model / case["id"], schema, args.claude_case_budget)
                    if result.get("unavailable"): unavailable_models[model]=result["unavailable"]
                results.append(result)
                verdict = "PASS" if not result["failures"] else "FAIL"
                print(f"{variant} {model} {case['id']}: {verdict} ({result['elapsed_seconds']:.1f}s)", flush=True)
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / f"summary-{args.variant}.json").write_text(json.dumps(results, indent=2) + "\n")
    return int(any(result["failures"] for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
