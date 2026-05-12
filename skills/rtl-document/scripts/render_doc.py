#!/usr/bin/env python3
"""Compose docs/rtl/<module>.md from extractor JSON + templates."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _read(p: Path) -> str:
    return p.read_text()


def _ports_table(ports: list[dict]) -> str:
    if not ports:
        return "_None._"
    rows = ["| Port Name | Direction | Width | Clock Domain | Kind | Description |",
            "|-----------|-----------|-------|--------------|------|-------------|"]
    for p in ports:
        rows.append(f"| {p['name']} | {p['dir']} | {p['width']} | "
                    f"{p.get('domain','?')} | {p['kind']} | <!-- LLM_FILL: port description --> |")
    return "\n".join(rows)


def _params_table(params: list[dict]) -> str:
    if not params:
        return "_None._"
    rows = ["| Parameter | Type | Default | Description |",
            "|-----------|------|---------|-------------|"]
    for p in params:
        rows.append(f"| {p['name']} | {p.get('type','?')} | {p['default']} | "
                    "<!-- LLM_FILL: parameter description --> |")
    return "\n".join(rows)


def _clock_table(domains: list[str]) -> str:
    if not domains:
        return "_None._"
    rows = ["| Domain | Clock | Reset | Usage |",
            "|--------|-------|-------|-------|"]
    for d in domains:
        rows.append(f"| {d} | {d}_clk | {d}_rst_n | <!-- LLM_FILL: clock domain usage --> |")
    return "\n".join(rows)


def _fsm_section(fsm_candidates: list[dict], template_dir: Path) -> str:
    if not fsm_candidates:
        return ""
    tmpl = _read(template_dir / "fsm-section-snippet.md")
    fsm = fsm_candidates[0]
    rows = [f"| {s} | _enum_ | <!-- LLM_FILL: FSM state semantics --> | <!-- LLM_FILL: transitions --> |"
            for s in fsm["states"]]
    transitions = "\n".join(f"  {s}" for s in fsm["states"])
    return tmpl.replace("{{FSM_ROWS}}", "\n".join(rows)) \
               .replace("{{FSM_TRANSITIONS}}", transitions)


def _instances_section(instances: list[dict]) -> str:
    if not instances:
        return ""
    rows = ["## Sub-Module Instances", "",
            "| Instance | Module | Purpose |",
            "|----------|--------|---------|"]
    for i in instances:
        rows.append(f"| {i['name']} | {i['module']} | <!-- LLM_FILL: instance purpose --> |")
    return "\n".join(rows)


def _block_diagram(instances: list[dict], module_name: str, template_dir: Path) -> str:
    if len(instances) < 2:
        return ""
    tmpl = _read(template_dir / "block-diagram-snippet.d2")
    nodes = "\n".join(f"  {i['name']}: {i['module']}" for i in instances)
    body = tmpl.replace("{{MODULE_NAME}}", module_name) \
               .replace("{{INSTANCE_NODES}}", nodes)
    return f"## Block Diagram\n\n```d2\n{body}\n```"


def _synth_summary(s: dict | None) -> str:
    if not s:
        return ""
    rows = ["## Synthesis Summary", ""]
    if "area_um2" in s:
        rows.append(f"- Area: **{s['area_um2']:.2f} um^2**")
    if "wns_ns" in s:
        rows.append(f"- WNS: **{s['wns_ns']:.3f} ns**")
    if "tns_ns" in s:
        rows.append(f"- TNS: **{s['tns_ns']:.3f} ns**")
    return "\n".join(rows)


def _convention_banner(viol: list[dict]) -> str:
    if not viol:
        return ""
    rows = ["> ### Convention Violations",
            ">",
            "> | Signal | Rule |",
            "> |--------|------|"]
    for v in viol:
        rows.append(f"> | {v['signal']} | {v['rule']} |")
    return "\n".join(rows)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--json", required=True)
    p.add_argument("--template-dir", required=True)
    p.add_argument("--out", required=True)
    args = p.parse_args()

    data = json.loads(Path(args.json).read_text())
    template_dir = Path(args.template_dir)
    body = _read(template_dir / "module-doc-template.md")

    body = (body
        .replace("{{MODULE_NAME}}", data["module_name"])
        .replace("{{FILE}}", data["file"])
        .replace("{{CONVENTION_BANNER}}", _convention_banner(data.get("convention_violations", [])))
        .replace("{{PARAMETERS_TABLE}}", _params_table(data.get("parameters", [])))
        .replace("{{PORTS_TABLE}}", _ports_table(data.get("ports", [])))
        .replace("{{CLOCK_DOMAINS_TABLE}}", _clock_table(data.get("clock_domains", [])))
        .replace("{{FSM_SECTION}}", _fsm_section(data.get("fsm_candidates", []), template_dir))
        .replace("{{INSTANCES_SECTION}}", _instances_section(data.get("instances", [])))
        .replace("{{BLOCK_DIAGRAM_SECTION}}", _block_diagram(data.get("instances", []), data["module_name"], template_dir))
        .replace("{{SYNTH_SUMMARY_SECTION}}", _synth_summary(data.get("synth_summary")))
    )

    body = re.sub(r"\n{3,}", "\n\n", body)
    Path(args.out).write_text(body)
    return 0


if __name__ == "__main__":
    sys.exit(main())
