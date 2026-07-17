#!/usr/bin/env python3
"""gen_ipxact.py — IEEE 1685-2014 IP-XACT component XML generator.

Parses a SystemVerilog module header (ANSI-style port list) and emits an
IP-XACT component descriptor. Stdlib-only (regex parsing + xml.etree) — no
external dependencies. Used by the rtl-ipxact-gen skill as the deterministic
fallback when the `sv_to_ipxact` CLI is unavailable.

Scope (deterministic extraction only):
  - vendor/library/name/version VLNV header
  - model/ports: direction from input/output/inout keyword, vector widths
    (parameterized widths preserved as expressions, never resolved to literals)
  - parameters from the #(...) header with default values
  - fileSets referencing the RTL source

Interpretive mapping (bus interface classification, memory maps) is NOT done
here — it stays with the ipxact-generator agent per the skill's
Responsibility_Boundary.

Usage:
    python3 gen_ipxact.py rtl/pixel_fifo/pixel_fifo.sv \
        [-o ipxact/pixel_fifo.xml] [--module NAME] \
        [--vendor rtl_team] [--library rtl_lib] [--ip-version 1.0]

Exit codes: 0 = success, 2 = parse/usage error.
"""

import argparse
import re
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

IPXACT_NS = "http://www.accellera.org/XMLSchema/IPXACT/1685-2014"
XSI_NS = "http://www.w3.org/2001/XMLSchema-instance"
SCHEMA_LOCATION = (
    "http://www.accellera.org/XMLSchema/IPXACT/1685-2014 "
    "http://www.accellera.org/XMLSchema/IPXACT/1685-2014/index.xsd"
)

DIRECTION_MAP = {"input": "in", "output": "out", "inout": "inout"}
PREFIX_DIRECTION = {"i_": "in", "o_": "out", "io_": "inout"}

CLOCK_RE = re.compile(r"^(\w+_)?clk$")
RESET_RE = re.compile(r"^(\w+_)?rst_n$")


class ParseError(Exception):
    """Raised when the SV source cannot be parsed into a module header."""


def strip_comments(text):
    """Remove // line comments and /* */ block comments."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def extract_balanced(text, start):
    """Return (contents, index_after_close) for the paren group opening at `start`."""
    if text[start] != "(":
        raise ParseError(f"expected '(' at offset {start}")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    raise ParseError("unbalanced parentheses in module header")


def split_top_level(text, sep=","):
    """Split on `sep` ignoring separators nested in (), [], {}."""
    parts, depth, current = [], 0, []
    for ch in text:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        if ch == sep and depth == 0:
            parts.append("".join(current))
            current = []
        else:
            current.append(ch)
    parts.append("".join(current))
    return [p.strip() for p in parts if p.strip()]


def find_module_header(text, module_name=None):
    """Locate a module declaration; return (name, param_text, port_text)."""
    for m in re.finditer(r"\bmodule\s+(\w+)", text):
        name = m.group(1)
        if module_name and name != module_name:
            continue
        pos = m.end()
        while pos < len(text) and text[pos] in " \t\n\r":
            pos += 1
        param_text = ""
        if pos < len(text) and text[pos] == "#":
            pos += 1
            while pos < len(text) and text[pos] in " \t\n\r":
                pos += 1
            param_text, pos = extract_balanced(text, pos)
            while pos < len(text) and text[pos] in " \t\n\r":
                pos += 1
        if pos >= len(text) or text[pos] != "(":
            raise ParseError(
                f"module '{name}': no ANSI port list found "
                "(non-ANSI/1995-style headers are not supported)"
            )
        port_text, _ = extract_balanced(text, pos)
        return name, param_text, port_text
    if module_name:
        raise ParseError(f"module '{module_name}' not found in source")
    raise ParseError("no module declaration found in source")


PARAM_RE = re.compile(
    r"^(?:parameter|localparam)?\s*"
    r"(?:(?:int|integer|longint|shortint|byte|logic|bit|string|real|realtime|time|signed|unsigned)\s+)*"
    r"(?:\[[^\]]*\]\s*)?"
    r"(\w+)\s*=\s*(.+)$",
    re.DOTALL,
)

PORT_RE = re.compile(
    r"^(input|output|inout)?\s*"
    r"(?:(?:logic|wire|reg|bit|var|tri)\s+)?"
    r"(?:(?:signed|unsigned)\s+)?"
    r"((?:\[[^\]]*\]\s*)*)"
    r"(\w+)\s*"
    r"((?:\[[^\]]*\]\s*)*)$",
    re.DOTALL,
)


def parse_parameters(param_text):
    """Parse #(...) contents into [(name, default_value)] preserving order."""
    params = []
    for chunk in split_top_level(param_text):
        m = PARAM_RE.match(chunk)
        if not m:
            print(f"WARNING: unparsed parameter entry skipped: {chunk!r}",
                  file=sys.stderr)
            continue
        name, value = m.group(1), " ".join(m.group(2).split())
        params.append((name, value))
    return params


def parse_ports(port_text):
    """Parse ANSI port list into [{name, direction, left, right}]."""
    ports = []
    current_dir = None
    for chunk in split_top_level(port_text):
        m = PORT_RE.match(chunk)
        if not m:
            raise ParseError(
                f"unsupported port declaration: {chunk!r} "
                "(interface ports and non-ANSI styles are not supported)"
            )
        direction_kw, packed, name, unpacked = m.groups()
        if direction_kw:
            current_dir = DIRECTION_MAP[direction_kw]
        if current_dir is None:
            raise ParseError(
                f"port '{name}' has no direction keyword "
                "(non-ANSI port list not supported)"
            )
        if unpacked.strip():
            print(f"WARNING: port '{name}': unpacked dimensions "
                  f"{unpacked.strip()!r} not representable in IP-XACT wire "
                  "vectors — recorded as scalar-per-name", file=sys.stderr)
        left = right = None
        dims = re.findall(r"\[([^\]]*)\]", packed or "")
        if dims:
            if len(dims) > 1:
                print(f"WARNING: port '{name}': multiple packed dimensions — "
                      "only the first is emitted", file=sys.stderr)
            parts = split_top_level(dims[0], ":")
            if len(parts) != 2:
                raise ParseError(f"port '{name}': malformed range [{dims[0]}]")
            left, right = parts[0], parts[1]
        check_prefix_convention(name, current_dir)
        ports.append({"name": name, "direction": current_dir,
                      "left": left, "right": right})
    return ports


def check_prefix_convention(name, direction):
    """Warn when i_/o_/io_ prefix disagrees with the declared direction."""
    if CLOCK_RE.match(name) or RESET_RE.match(name):
        return  # clock/reset are exempt from the prefix rule
    for prefix, prefix_dir in sorted(PREFIX_DIRECTION.items(),
                                     key=lambda kv: -len(kv[0])):
        if name.startswith(prefix):
            if prefix_dir != direction:
                print(f"WARNING: port '{name}': prefix '{prefix}' implies "
                      f"'{prefix_dir}' but declared '{direction}' — "
                      "declaration keyword wins", file=sys.stderr)
            return
    print(f"WARNING: port '{name}' lacks i_/o_/io_ prefix "
          "(project convention; clock/reset exempt)", file=sys.stderr)


def port_role_description(name):
    """Clock/reset role annotation for the port description element."""
    if CLOCK_RE.match(name):
        return "Clock (rising-edge active)"
    if RESET_RE.match(name):
        return "Reset (active-low, asynchronous)"
    return None


def build_component(module, ports, params, source_path, vendor, library,
                    ip_version):
    """Build the ipxact:component ElementTree (IEEE 1685-2014 element order)."""
    ET.register_namespace("ipxact", IPXACT_NS)
    ET.register_namespace("xsi", XSI_NS)

    def q(tag):
        return f"{{{IPXACT_NS}}}{tag}"

    comp = ET.Element(q("component"),
                      {f"{{{XSI_NS}}}schemaLocation": SCHEMA_LOCATION})
    ET.SubElement(comp, q("vendor")).text = vendor
    ET.SubElement(comp, q("library")).text = library
    ET.SubElement(comp, q("name")).text = module
    ET.SubElement(comp, q("version")).text = ip_version

    # busInterfaces intentionally omitted: bus classification is interpretive
    # (LLM/agent responsibility), and an empty busInterfaces element is not
    # schema-valid.

    model = ET.SubElement(comp, q("model"))
    ports_el = ET.SubElement(model, q("ports"))
    for p in ports:
        port_el = ET.SubElement(ports_el, q("port"))
        ET.SubElement(port_el, q("name")).text = p["name"]
        role = port_role_description(p["name"])
        if role:
            ET.SubElement(port_el, q("description")).text = role
        wire = ET.SubElement(port_el, q("wire"))
        ET.SubElement(wire, q("direction")).text = p["direction"]
        if p["left"] is not None:
            vectors = ET.SubElement(wire, q("vectors"))
            vector = ET.SubElement(vectors, q("vector"))
            ET.SubElement(vector, q("left")).text = p["left"]
            ET.SubElement(vector, q("right")).text = p["right"]

    file_sets = ET.SubElement(comp, q("fileSets"))
    file_set = ET.SubElement(file_sets, q("fileSet"))
    ET.SubElement(file_set, q("name")).text = "rtlSource"
    file_el = ET.SubElement(file_set, q("file"))
    ET.SubElement(file_el, q("name")).text = source_path
    ET.SubElement(file_el, q("fileType")).text = "systemVerilogSource"

    ET.SubElement(comp, q("description")).text = (
        f"IP-XACT component for module '{module}' generated by "
        "rtl-agent-team:rtl-ipxact-gen (gen_ipxact.py). Bus interface and "
        "memory map sections are added by the ipxact-generator agent."
    )

    if params:
        params_el = ET.SubElement(comp, q("parameters"))
        for name, value in params:
            param_el = ET.SubElement(params_el, q("parameter"),
                                     {"parameterId": name})
            ET.SubElement(param_el, q("name")).text = name
            ET.SubElement(param_el, q("value")).text = value

    return ET.ElementTree(comp)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate IEEE 1685-2014 IP-XACT component XML from a "
                    "SystemVerilog module header.")
    parser.add_argument("input", help="SystemVerilog source file (.sv)")
    parser.add_argument("-o", "--output",
                        help="output XML path (default: ipxact/{module}.xml)")
    parser.add_argument("--module",
                        help="module name to extract (default: first module)")
    parser.add_argument("--vendor", default="rtl_team",
                        help="ipxact:vendor value (default: rtl_team)")
    parser.add_argument("--library", default="rtl_lib",
                        help="ipxact:library value (default: rtl_lib)")
    parser.add_argument("--ip-version", default=None,
                        help="ipxact:version value (default: RTL parameter "
                             "VERSION if present, else 1.0)")
    args = parser.parse_args(argv)

    src = Path(args.input)
    if not src.is_file():
        print(f"ERROR: input file not found: {src}", file=sys.stderr)
        return 2

    try:
        text = strip_comments(src.read_text())
        module, param_text, port_text = find_module_header(text, args.module)
        params = parse_parameters(param_text) if param_text else []
        ports = parse_ports(port_text)
    except ParseError as exc:
        print(f"ERROR: {src}: {exc}", file=sys.stderr)
        return 2

    if not ports:
        print(f"ERROR: {src}: module '{module}' has an empty port list",
              file=sys.stderr)
        return 2

    ip_version = args.ip_version
    if ip_version is None:
        version_param = dict(params).get("VERSION")
        ip_version = version_param.strip("\"'") if version_param else "1.0"

    tree = build_component(module, ports, params, src.as_posix(),
                           args.vendor, args.library, ip_version)
    ET.indent(tree, space="  ")

    out = Path(args.output) if args.output else Path("ipxact") / f"{module}.xml"
    out.parent.mkdir(parents=True, exist_ok=True)
    tree.write(out, encoding="UTF-8", xml_declaration=True)

    # Well-formedness self-check (re-parse what we wrote).
    ET.parse(out)

    vec_count = sum(1 for p in ports if p["left"] is not None)
    print(f"Generated {out}: module={module} ports={len(ports)} "
          f"(vector={vec_count}, scalar={len(ports) - vec_count}) "
          f"parameters={len(params)} vlnv={args.vendor}:{args.library}:"
          f"{module}:{ip_version}")
    print("Well-formedness check: PASS (xml.etree re-parse)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
