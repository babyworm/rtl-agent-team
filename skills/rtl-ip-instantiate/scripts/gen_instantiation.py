#!/usr/bin/env python3
"""gen_instantiation.py — convention-compliant IP wrapper skeleton generator.

Parses a third-party IP's Verilog/SystemVerilog module header (ANSI-style
port list; vendor naming such as CamelCase or ALL-CAPS is expected) and
emits a project-convention wrapper skeleton. Stdlib-only (regex parsing) —
no external dependencies. Used by the rtl-ip-instantiate skill to produce
the deterministic starting point that `rtl-coder` then hand-tunes
(functional port names, clock-domain merging, polarity adaptation).

Deterministic mapping contract:
  - Wrapper module `{ip_name}_wrapper` (leading `vendor_` stripped from
    `{ip_name}`); vendor IP instantiated as `u_{ip_name}`.
  - Parameters passed through 1:1; non-ALL_CAPS vendor parameter names are
    renamed to UPPER_SNAKE_CASE on the wrapper side and width expressions
    are rewritten accordingly. Each carries a `// PARAM:` TODO comment.
  - Clock-like ports map to `clk` / `{domain}_clk`; reset-like ports map to
    `rst_n` / `{domain}_rst_n` (a TODO comment is added when the vendor
    reset has no active-low marker). All other ports map to snake_case with
    an `i_`/`o_`/`io_` prefix from the declared direction (any vendor
    `i_`/`o_`/`io_` prefix or `_i`/`_o`/`_io` suffix is stripped first).
  - `--tie PORT=VALUE[:reason]` excludes PORT from the wrapper interface and
    ties it in the instance with a `// TIED:` comment (`NC` leaves an output
    unconnected). Every vendor port is therefore either mapped or tied —
    no silent unconnected ports.

Usage:
    python3 gen_instantiation.py vendor_ip.v \
        [-o rtl/ip_wrappers/{wrapper}.sv] [--module NAME] \
        [--wrapper-name NAME] [--domain sys] \
        [--tie "EMA=3'b010:vendor-recommended margin"] ...

Exit codes: 0 = success, 2 = parse/usage error.
"""

import argparse
import re
import sys
from pathlib import Path

DIRECTION_MAP = {"input": "in", "output": "out", "inout": "inout"}
DIR_PREFIX = {"in": "i_", "out": "o_", "inout": "io_"}
DIR_KEYWORD = {"in": "input", "out": "output", "inout": "inout"}

RULE_WIDTH = 71  # total width of `// ─── title ───` section rules


class ParseError(Exception):
    """Raised when the vendor source cannot be parsed into a module header."""


# ---------------------------------------------------------------------------
# SV header parsing (same approach as rtl-ipxact-gen/scripts/gen_ipxact.py)
# ---------------------------------------------------------------------------

def strip_comments(text):
    """Remove // line comments and /* */ block comments."""
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.DOTALL)
    text = re.sub(r"//[^\n]*", "", text)
    return text


def extract_balanced(text, start):
    """Return (contents, index_after_close) for the paren group at `start`."""
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
    r"((?:logic|wire|reg|bit|var|tri)\s+)?"
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
    """Parse ANSI port list into [{name, direction, range}] (range = raw text)."""
    ports = []
    current_dir = None
    current_packed = ""
    for chunk in split_top_level(port_text):
        m = PORT_RE.match(chunk)
        if not m:
            raise ParseError(
                f"unsupported port declaration: {chunk!r} "
                "(interface ports and non-ANSI styles are not supported)"
            )
        direction_kw, type_kw, packed, name, unpacked = m.groups()
        packed = packed.strip()
        # Grouped ANSI ports ("input wire [7:0] DataIn, DataIn2"): bare
        # declarators inherit the group's packed range; any explicit
        # direction/type/range resets it (IEEE 1800).
        if direction_kw:
            current_dir = DIRECTION_MAP[direction_kw]
        if direction_kw or type_kw or packed:
            current_packed = packed
        if current_dir is None:
            raise ParseError(
                f"port '{name}' has no direction keyword "
                "(non-ANSI port list not supported)"
            )
        if unpacked.strip():
            print(f"WARNING: port '{name}': unpacked dimensions "
                  f"{unpacked.strip()!r} dropped — hand-map this port",
                  file=sys.stderr)
        rng = None
        dims = re.findall(r"\[([^\]]*)\]", current_packed or "")
        if dims:
            if len(dims) > 1:
                print(f"WARNING: port '{name}': multiple packed dimensions — "
                      "only the first is kept", file=sys.stderr)
            rng = " ".join(dims[0].split())
        ports.append({"name": name, "direction": current_dir, "range": rng})
    return ports


# ---------------------------------------------------------------------------
# Convention mapping
# ---------------------------------------------------------------------------

def snake_case(name):
    """CamelCase / ALL-CAPS vendor name → snake_case."""
    s = re.sub(r"(.)([A-Z][a-z]+)", r"\1_\2", name)
    s = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", s)
    s = re.sub(r"__+", "_", s)
    return s.lower().strip("_")


def all_caps(name):
    """Vendor parameter name → UPPER_SNAKE_CASE."""
    return snake_case(name).upper()


def classify_port(vendor_name):
    """Return ('clock'|'reset'|'data', base_snake) for a vendor port name."""
    base = snake_case(vendor_name)
    base = re.sub(r"_(ni|no|io|i|o)$", "", base)  # vendor direction suffixes
    if re.search(r"(^|_)(clk|clock)", base) or base.endswith(("clk", "clock")):
        return "clock", base
    if "rst" in base or "reset" in base:
        return "reset", base
    return "data", base


def clock_wrapper_name(base, domain):
    """Vendor clock base → `clk` or `{domain}_clk`."""
    dom = re.sub(r"_?(clock|clk)_?", "", base, count=1).strip("_")
    if not dom:
        return f"{domain}_clk" if domain else "clk"
    if not re.match(r"[a-z_]", dom):
        dom = base  # e.g. 'clk2' → domain '2' is not an identifier
    return f"{dom}_clk"


def reset_wrapper_name(base, domain):
    """Vendor reset base → `rst_n` or `{domain}_rst_n` (+ polarity flag)."""
    # Active-low only on an explicit n/b token adjacent to rst/reset
    # (rst_n, rstn, rstb, areset_n ...). A broad endswith(("n","b")) fallback
    # would misclassify names like reset_main/chain as active-low and drop
    # the polarity-review TODO from the generated wrapper.
    active_low = bool(re.search(r"(rst|reset)_?(n|b)($|_)", base))
    dom = re.sub(r"_?a?(rst|reset)_?(n|b)?_?", "", base, count=1).strip("_")
    if dom and not re.match(r"[a-z_]", dom):
        dom = base
    if not dom:
        name = f"{domain}_rst_n" if domain else "rst_n"
    else:
        name = f"{dom}_rst_n"
    return name, active_low


def data_wrapper_name(base, direction):
    """Vendor data base → `i_`/`o_`/`io_` prefixed snake_case name."""
    stripped = re.sub(r"^(io|i|o)_", "", base)
    return DIR_PREFIX[direction] + (stripped or base)


def parse_tie_args(tie_args, port_names):
    """Parse --tie 'PORT=VALUE[:reason]' entries; validate port names."""
    ties = {}
    for entry in tie_args or []:
        if "=" not in entry:
            raise ParseError(f"--tie {entry!r}: expected PORT=VALUE[:reason]")
        port, rest = entry.split("=", 1)
        port = port.strip()
        value, _, reason = rest.partition(":")
        value, reason = value.strip(), reason.strip()
        if not value:
            raise ParseError(f"--tie {entry!r}: empty tie value")
        if port not in port_names:
            raise ParseError(
                f"--tie {entry!r}: port '{port}' not found in module "
                f"(ports: {', '.join(sorted(port_names))})")
        ties[port] = (value, reason or "TODO — document reason")
    return ties


def map_ports(ports, ties, domain):
    """Assign wrapper names/kinds; returns mapped port list (ties excluded)."""
    mapped, seen = [], {}
    for p in ports:
        if p["name"] in ties:
            continue
        kind, base = classify_port(p["name"])
        todo = None
        if kind == "clock":
            wname = clock_wrapper_name(base, domain)
        elif kind == "reset":
            wname, active_low = reset_wrapper_name(base, domain)
            if not active_low:
                todo = "TODO: verify polarity (project resets are active-low)"
        else:
            wname = data_wrapper_name(base, p["direction"])
        if wname in seen:
            raise ParseError(
                f"wrapper name collision: vendor ports '{seen[wname]}' and "
                f"'{p['name']}' both map to '{wname}' — hand-map one of them")
        seen[wname] = p["name"]
        mapped.append({**p, "kind": kind, "wrapper": wname, "todo": todo})
    return mapped


# ---------------------------------------------------------------------------
# Emission
# ---------------------------------------------------------------------------

def rule(title, indent="  "):
    head = f"{indent}// ─── {title} "
    return head + "─" * max(RULE_WIDTH - len(head), 3)


def emit_wrapper(ip_name, wrapper_name, params, mapped, ties, tie_order):
    """Render the wrapper skeleton; returns (text, todo_count)."""
    todo_count = 0
    lines = [
        f"// {wrapper_name}.sv — Convention-compliant wrapper skeleton "
        f"for {ip_name}",
        "// Translates vendor port naming to project conventions:",
    ]
    sample = mapped[:3]
    lines.append(
        f"//   Vendor: {'/'.join(p['name'] for p in sample)}  →  "
        f"Project: {'/'.join(p['wrapper'] for p in sample)}")
    lines += [
        "//",
        "// Generated by rtl-agent-team:rtl-ip-instantiate (gen_instantiation.py)",
        "// Hand-tune before delivery: merge/rename clock domains, give mapped",
        "// ports functional names, verify polarities, resolve TODO markers.",
        "",
    ]

    # Module header with parameter pass-through
    if params:
        lines.append(f"module {wrapper_name} #(")
        lines.append(rule("Parameters (UPPER_SNAKE_CASE)"))
        decls = []
        for vend, wrap, value in params:
            kw = "parameter int" if re.fullmatch(r"\d+", value) else "parameter"
            decls.append((f"{kw} {wrap} = {value}", vend))
        width = max(len(d) for d, _ in decls) + 1
        for i, (decl, vend) in enumerate(decls):
            comma = "," if i < len(decls) - 1 else ""
            lines.append(f"  {decl + comma:<{width}}  "
                         f"// PARAM: TODO — describe purpose (vendor: {vend})")
            todo_count += 1
        lines.append(") (")
    else:
        lines.append(f"module {wrapper_name} (")

    # Wrapper port declarations, grouped by kind
    groups = [
        ("Clock / Reset (project convention)",
         [p for p in mapped if p["kind"] in ("clock", "reset")]),
        ("Input ports (i_ prefix)",
         [p for p in mapped if p["kind"] == "data" and p["direction"] == "in"]),
        ("Output ports (o_ prefix)",
         [p for p in mapped if p["kind"] == "data" and p["direction"] == "out"]),
        ("Inout ports (io_ prefix)",
         [p for p in mapped if p["kind"] == "data" and p["direction"] == "inout"]),
    ]
    groups = [(t, ps) for t, ps in groups if ps]
    rng_w = max((len(f"[{p['range']}]") for p in mapped if p["range"]),
                default=0)
    flat = [p for _, ps in groups for p in ps]
    for gi, (title, ps) in enumerate(groups):
        if gi:
            lines.append("")
        lines.append(rule(title))
        for p in ps:
            rng = f"[{p['range']}]" if p["range"] else ""
            comma = "," if p is not flat[-1] else ""
            pad = f"{rng:<{rng_w}} " if rng_w else ""
            decl = (f"  {DIR_KEYWORD[p['direction']]:<6} logic "
                    f"{pad}{p['wrapper']}{comma}")
            if p["todo"]:
                decl += f"  // {p['todo']}"
                todo_count += 1
            lines.append(decl)
    lines.append(");")
    lines.append("")

    # Vendor IP instance
    lines.append(rule("Vendor IP Instance"))
    if params:
        lines.append(f"  {ip_name} #(")
        vw = max(len(v) for v, _, _ in params)
        for i, (vend, wrap, _) in enumerate(params):
            comma = "," if i < len(params) - 1 else ""
            lines.append(f"    .{vend:<{vw}} ({wrap}){comma}")
        lines.append(f"  ) u_{short_name(ip_name)} (")
    else:
        lines.append(f"  {ip_name} u_{short_name(ip_name)} (")

    name_w = max(len(p["name"]) for p in mapped + [{"name": t} for t in tie_order]) \
        if (mapped or tie_order) else 0
    conns = []  # (vendor, connection, comment)
    cr = [p for p in mapped if p["kind"] in ("clock", "reset")]
    data = [p for p in mapped if p["kind"] == "data"]
    if cr:
        conns.append(("// Clock/Reset mapping", None, None))
        conns.append(("//   Vendor  →  Project", None, None))
        conns += [(p["name"], p["wrapper"], None) for p in cr]
    if data:
        if cr:
            conns.append(("", None, None))
        conns.append(("// Data port mapping", None, None))
        conns += [(p["name"], p["wrapper"], None) for p in data]
    if tie_order:
        conns.append(("", None, None))
        conns.append((rule("Tie-offs (unused vendor ports)",
                           indent="    ").lstrip(), None, None))
        for t in tie_order:
            value, reason = ties[t]
            conn = "/* NC */" if value.upper() == "NC" else value
            conns.append((t, conn, f"// TIED: {reason}"))
            if "TODO" in reason:
                todo_count += 1
    real = [c for c in conns if c[1] is not None]
    stmts = {}
    for vend, conn, _ in real:
        comma = "," if (vend, conn) != (real[-1][0], real[-1][1]) else ""
        stmts[vend] = f".{vend:<{name_w}}  ({conn}){comma}"
    stmt_w = max((len(s) for s in stmts.values()), default=0)
    for vend, conn, comment in conns:
        if conn is None:
            lines.append(f"    {vend}".rstrip())
        elif comment:
            lines.append(f"    {stmts[vend]:<{stmt_w}}  {comment}")
        else:
            lines.append(f"    {stmts[vend]}")
    lines.append("  );")

    # Tie-off documentation table
    if tie_order:
        lines.append("")
        lines.append(rule("Tie-off Documentation"))
        rows = [(t, ties[t][0], ties[t][1]) for t in tie_order]
        widths = [max(len(h), *(len(r[i]) for r in rows))
                  for i, h in enumerate(("Vendor Port", "Tied To", "Reason"))]
        header = ("Vendor Port", "Tied To", "Reason")
        lines.append("  // | " + " | ".join(h.ljust(w) for h, w
                                            in zip(header, widths)) + " |")
        lines.append("  // |" + "|".join("-" * (w + 2) for w in widths) + "|")
        for r in rows:
            lines.append("  // | " + " | ".join(c.ljust(w) for c, w
                                                in zip(r, widths)) + " |")

    lines += ["", "endmodule", ""]
    return "\n".join(lines), todo_count


def short_name(ip_name):
    """Instance/wrapper base name: strip a leading `vendor_` prefix."""
    return re.sub(r"^vendor_", "", ip_name)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Generate a convention-compliant SV wrapper skeleton "
                    "from a third-party IP module header.")
    parser.add_argument("input", help="vendor Verilog/SV source file")
    parser.add_argument("-o", "--output",
                        help="output SV path "
                             "(default: rtl/ip_wrappers/{wrapper}.sv)")
    parser.add_argument("--module",
                        help="module name to wrap (default: first module)")
    parser.add_argument("--wrapper-name",
                        help="wrapper module name "
                             "(default: {ip_name}_wrapper, 'vendor_' stripped)")
    parser.add_argument("--domain", default=None,
                        help="clock/reset domain prefix for single-domain IPs "
                             "(e.g. 'sys' → sys_clk/sys_rst_n)")
    parser.add_argument("--tie", action="append", metavar="PORT=VALUE[:reason]",
                        help="tie off a vendor port instead of mapping it "
                             "(VALUE 'NC' leaves an output unconnected); "
                             "repeatable")
    args = parser.parse_args(argv)

    src = Path(args.input)
    if not src.is_file():
        print(f"ERROR: input file not found: {src}", file=sys.stderr)
        return 2

    try:
        text = strip_comments(src.read_text())
        ip_name, param_text, port_text = find_module_header(text, args.module)
        raw_params = parse_parameters(param_text) if param_text else []
        ports = parse_ports(port_text)
        if not ports:
            raise ParseError(f"module '{ip_name}' has an empty port list")

        ties = parse_tie_args(args.tie, {p["name"] for p in ports})
        tie_order = [p["name"] for p in ports if p["name"] in ties]

        # Parameter pass-through with UPPER_SNAKE_CASE rename where needed
        params, rename = [], {}
        for vend, value in raw_params:
            wrap = all_caps(vend)
            if wrap != vend:
                rename[vend] = wrap
                print(f"WARNING: parameter '{vend}' renamed to '{wrap}' on "
                      "the wrapper side (UPPER_SNAKE_CASE convention)",
                      file=sys.stderr)
            params.append((vend, wrap, value))
        if len({w for _, w, _ in params}) != len(params):
            raise ParseError("parameter rename collision — hand-map parameters")
        if rename:
            # Wrapper-side parameter DEFAULT expressions may reference other
            # renamed parameters (e.g. DEPTH = (1 << AddrWidth)) — rewrite
            # them through the full rename map or the emitted wrapper is
            # invalid SV. Vendor-instance param mapping keeps vendor names.
            for i, (vend, wrap, value) in enumerate(params):
                if value:
                    for v2, w2 in rename.items():
                        value = re.sub(rf"\b{re.escape(v2)}\b", w2, value)
                    params[i] = (vend, wrap, value)

        mapped = map_ports(ports, ties, args.domain)
        if not mapped:
            raise ParseError("all ports are tied off — nothing to wrap")
        for p in mapped:  # rewrite width expressions for renamed parameters
            if p["range"]:
                for vend, wrap in rename.items():
                    p["range"] = re.sub(rf"\b{re.escape(vend)}\b", wrap,
                                        p["range"])
    except ParseError as exc:
        print(f"ERROR: {src}: {exc}", file=sys.stderr)
        return 2

    wrapper_name = args.wrapper_name or f"{short_name(ip_name)}_wrapper"
    out = Path(args.output) if args.output \
        else Path("rtl/ip_wrappers") / f"{wrapper_name}.sv"
    text, todo_count = emit_wrapper(ip_name, wrapper_name, params, mapped,
                                    ties, tie_order)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text)

    print(f"Generated {out}: ip={ip_name} wrapper={wrapper_name} "
          f"ports={len(ports)} (mapped={len(mapped)}, tied={len(tie_order)}) "
          f"parameters={len(params)} todo_markers={todo_count}")
    print("Reminder: lint before delivery — "
          f"verible-verilog-lint {out} && slang {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
