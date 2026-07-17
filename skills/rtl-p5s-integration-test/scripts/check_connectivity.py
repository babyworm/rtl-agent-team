#!/usr/bin/env python3
"""check_connectivity.py — Tier 4 static connectivity checker for rtl-p5s-integration-test.

Parses a top-level SystemVerilog module plus its submodule definitions
(regex + balanced-paren parsing, same approach as rtl-ipxact-gen's
gen_ipxact.py) and verifies port connectivity at every module boundary
before dynamic simulation is run:

  - unknown_port        (error)   named connection to a port the submodule
                                  does not declare
  - undeclared_signal   (error)   connection expression references a signal
                                  not declared in the top module
  - width_mismatch      (error)   port and connected signal widths differ,
                                  where both are literal or simple-parameter
                                  resolvable
  - dangling_port       (error/warning) explicitly empty connection `.p()` —
                                  error for inputs (undriven), warning for
                                  outputs/inouts (unused)
  - unconnected_port    (warning) submodule port omitted from the connection
                                  list entirely
  - undriven_output     (error)   top-level output driven by no instance
                                  output, assign, or procedural assignment
  - missing_module_def  (warning) instantiated module whose definition file
                                  was not provided — connectivity unchecked
  - positional_connection / wildcard_connection (warning) — not analyzed

Scope limitations (kept honest — deterministic checks only):
  - ANSI port lists only (IEEE 1800-2009 style); non-ANSI headers are a
    parse error.
  - Width resolution handles integer literals, parameter/localparam chains,
    `$clog2`, and + - * / % arithmetic. Anything else (generate blocks,
    typedefs, interfaces, hierarchical refs, functions) is skipped and
    counted in `summary.width_checks.skipped` — never guessed.
  - Unsized literals (`'0`, `'1`, plain decimals) are context-sized in SV,
    so their width is not checked.
  - The undriven-output check is a textual heuristic (instance output
    connections, `assign` LHS, `<=`/`=` procedural LHS); unusual coding
    styles may mask a genuinely undriven output. It is skipped entirely
    when any instance uses positional or `.*` connections (unanalyzed →
    the check would be unsound).
  - Only the top module's body is analyzed; nested hierarchy below the
    submodules is out of scope (run per-level if needed).

Output: deterministic JSON (no timestamps) — violations list with
file/line/instance/port + severity, and summary counts. Feeds the
`connectivity` category of `sim/top/integration_results.json` (see
references/integration-test-conventions.md).

Usage:
    python3 check_connectivity.py rtl/top/dut_top.sv rtl/sub_a/sub_a.sv ... \
        [--top dut_top] [-o connectivity_report.json]

Exit codes: 0 = PASS (no errors; warnings allowed), 1 = FAIL, 2 = usage/parse error.
"""

import argparse
import json
import re
import sys
from pathlib import Path

DIRECTION_MAP = {"input": "input", "output": "output", "inout": "inout"}

SV_KEYWORDS = frozenset("""
module endmodule input output inout logic wire reg bit var tri parameter
localparam assign always always_ff always_comb always_latch begin end if else
case casez casex endcase for while generate endgenerate genvar posedge negedge
or and not signed unsigned int integer initial function endfunction task
endtask typedef enum struct unique priority default return const static
""".split())

PORT_RE = re.compile(
    r"^(input|output|inout)?\s*"
    r"(?:(?:logic|wire|reg|bit|var|tri)\s+)?"
    r"(?:(?:signed|unsigned)\s+)?"
    r"((?:\[[^\]]*\]\s*)*)"
    r"(\w+)\s*"
    r"((?:\[[^\]]*\]\s*)*)$",
    re.DOTALL,
)

PARAM_RE = re.compile(
    r"^(?:parameter|localparam)?\s*"
    r"(?:(?:int|integer|longint|shortint|byte|logic|bit|unsigned|signed)\s+)*"
    r"(?:\[[^\]]*\]\s*)?"
    r"(\w+)\s*=\s*(.+)$",
    re.DOTALL,
)

DECL_RE = re.compile(
    r"\b(?:logic|wire|reg|bit)\b"
    r"(?:\s+(?:signed|unsigned))?"
    r"\s*((?:\[[^\]]*\]\s*)*)"
    r"(\w+(?:\s*\[[^\]]*\])*(?:\s*=\s*[^,;]+)?"
    r"(?:\s*,\s*\w+(?:\s*\[[^\]]*\])*(?:\s*=\s*[^,;]+)?)*)\s*;")

LOCALPARAM_RE = re.compile(
    r"\blocalparam\b(?:\s+(?:int|integer|unsigned|signed))?"
    r"\s*(?:\[[^\]]*\]\s*)?(\w+)\s*=\s*([^;,]+)[;,]")

CLOG2_RE = re.compile(r"\$clog2\s*\(([^()]*)\)")
SIZED_LITERAL_RE = re.compile(r"^(\d+)\s*'\s*[sS]?[bBoOdDhH]\s*[0-9a-fA-FxXzZ_?]+$")
BASED_LITERAL_SUB_RE = re.compile(r"\d*\s*'\s*[sS]?[bBoOdDhH]\s*[0-9a-fA-FxXzZ_?]+")


class ParseError(Exception):
    """Raised when the SV source cannot be parsed."""


# ---------------------------------------------------------------------------
# Text utilities (offset-preserving so line numbers stay valid)
# ---------------------------------------------------------------------------

def strip_comments_preserve(text):
    """Blank out comments and string literals, preserving offsets/newlines."""
    out = []
    i, n = 0, len(text)
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            j = n if j == -1 else j
            out.append(" " * (j - i))
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i)
            j = n if j == -1 else j + 2
            out.append("".join(c if c == "\n" else " " for c in text[i:j]))
            i = j
        elif text[i] == '"':
            j = i + 1
            while j < n and text[j] != '"':
                j += 2 if text[j] == "\\" else 1
            j = min(j + 1, n)
            out.append("".join(c if c == "\n" else " " for c in text[i:j]))
            i = j
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def line_of(text, pos):
    return text.count("\n", 0, pos) + 1


def skip_ws(text, i):
    while i < len(text) and text[i] in " \t\n\r":
        i += 1
    return i


def extract_balanced(text, start):
    """Return (contents, index_after_close) for the paren group at `start`."""
    if start >= len(text) or text[start] != "(":
        raise ParseError(f"expected '(' at offset {start}")
    depth = 0
    for i in range(start, len(text)):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return text[start + 1:i], i + 1
    raise ParseError("unbalanced parentheses")


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


# ---------------------------------------------------------------------------
# Module definition parsing
# ---------------------------------------------------------------------------

def parse_parameters(param_text):
    """Parse #(...) contents into ordered [(name, default_expr)]."""
    params = []
    for chunk in split_top_level(param_text):
        m = PARAM_RE.match(chunk)
        if not m:
            continue
        params.append((m.group(1), " ".join(m.group(2).split())))
    return params


def parse_ports(port_text, module_name):
    """Parse ANSI port list into ordered [{name, direction, range, unpacked}]."""
    ports = []
    current_dir = None
    current_packed = ""
    for chunk in split_top_level(port_text):
        m = PORT_RE.match(chunk)
        if not m:
            raise ParseError(
                f"module '{module_name}': unsupported port declaration "
                f"{chunk!r} (interface ports / non-ANSI styles not supported)")
        direction_kw, packed, name, unpacked = m.groups()
        packed = packed.strip()
        if direction_kw:
            current_dir = DIRECTION_MAP[direction_kw]
            current_packed = packed  # new declaration resets group type/range
        elif packed:
            current_packed = packed  # explicit type/range starts a new group
        if current_dir is None:
            raise ParseError(
                f"module '{module_name}': port '{name}' has no direction "
                "keyword (non-ANSI port list not supported)")
        # Bare declarators in grouped ANSI declarations ("input logic [7:0]
        # a, b") inherit the group's packed type/range (IEEE 1800) — without
        # this, second-and-later grouped ports were width-checked as scalars.
        eff_packed = packed or current_packed
        ports.append({"name": name, "direction": current_dir,
                      "range": eff_packed or None,
                      "unpacked": bool(unpacked.strip())})
    return ports


def parse_modules(path, text):
    """Extract all module definitions from one (comment-stripped) file."""
    modules = []
    for m in re.finditer(r"\bmodule\s+(\w+)", text):
        name = m.group(1)
        pos = skip_ws(text, m.end())
        param_text = ""
        if pos < len(text) and text[pos] == "#":
            pos = skip_ws(text, pos + 1)
            param_text, pos = extract_balanced(text, pos)
            pos = skip_ws(text, pos)
        if pos >= len(text) or text[pos] != "(":
            raise ParseError(
                f"{path}: module '{name}': no ANSI port list found "
                "(non-ANSI/1995-style headers are not supported)")
        port_text, after = extract_balanced(text, pos)
        end = re.compile(r"\bendmodule\b").search(text, after)
        body_end = end.start() if end else len(text)
        modules.append({
            "name": name,
            "file": path,
            "header_start": m.start(),
            "header_line": line_of(text, m.start()),
            "params": parse_parameters(param_text) if param_text else [],
            "ports": parse_ports(port_text, name),
            "body_span": (after, body_end),
            "text": text,
        })
    return modules


# ---------------------------------------------------------------------------
# Constant expression evaluation (literal + simple parameter widths only)
# ---------------------------------------------------------------------------

def eval_const(expr, env, _depth=0):
    """Evaluate an integer constant expression; return int or None."""
    if expr is None or _depth > 16:
        return None
    expr = expr.strip()
    if not expr:
        return None
    # Resolve $clog2(...) innermost-first.
    while True:
        m = CLOG2_RE.search(expr)
        if not m:
            break
        inner = eval_const(m.group(1), env, _depth + 1)
        if inner is None:
            return None
        val = 0 if inner <= 1 else (inner - 1).bit_length()
        expr = expr[:m.start()] + str(val) + expr[m.end():]
    # Substitute identifiers from the parameter environment.
    def sub_ident(m):
        name = m.group(0)
        if name in env:
            val = env[name]
            if isinstance(val, str):
                val = eval_const(val, env, _depth + 1)
            return str(val) if val is not None else name
        return name
    expr = re.sub(r"\b[a-zA-Z_]\w*\b", sub_ident, expr)
    if re.search(r"[a-zA-Z_$'\"]", expr):
        return None  # unresolved identifier / unsupported construct
    if not re.fullmatch(r"[\d\s()+\-*/%]+", expr):
        return None
    # SV integer arithmetic: force integer division, then evaluate via a
    # restricted AST walker — never eval(). The char whitelist above still
    # admits '**' (two '*'), and eval('9**9**9') would grind on unbounded
    # big-int math; the walker rejects Pow and bounds operand magnitudes.
    return _safe_int_eval(re.sub(r"(?<![/])/(?![/])", "//", expr))


_EVAL_LIMIT = 1 << 32  # widths/params are small; anything larger is not a width


def _safe_int_eval(expr):
    """Evaluate int expr allowing only + - * // % and parentheses; None otherwise."""
    import ast

    try:
        tree = ast.parse(expr, mode="eval")
    except (SyntaxError, ValueError, RecursionError):
        return None

    def walk(node):
        if isinstance(node, ast.Expression):
            return walk(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, int):
            return node.value if abs(node.value) <= _EVAL_LIMIT else None
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
            v = walk(node.operand)
            if v is None:
                return None
            return v if isinstance(node.op, ast.UAdd) else -v
        if isinstance(node, ast.BinOp) and isinstance(
            node.op, (ast.Add, ast.Sub, ast.Mult, ast.FloorDiv, ast.Mod)
        ):
            lhs, rhs = walk(node.left), walk(node.right)
            if lhs is None or rhs is None:
                return None
            if isinstance(node.op, (ast.FloorDiv, ast.Mod)) and rhs == 0:
                return None
            if isinstance(node.op, ast.Add):
                v = lhs + rhs
            elif isinstance(node.op, ast.Sub):
                v = lhs - rhs
            elif isinstance(node.op, ast.Mult):
                v = lhs * rhs
            elif isinstance(node.op, ast.FloorDiv):
                v = lhs // rhs
            else:
                v = lhs % rhs
            return v if abs(v) <= _EVAL_LIMIT else None
        return None  # Pow ('**') and everything else → unresolvable (skipped)

    try:
        return walk(tree)
    except RecursionError:
        return None


def range_width(range_text, env):
    """Width of packed range(s) like '[7:0]' or '[A-1:0][1:0]'; None if unresolvable."""
    if not range_text:
        return 1
    width = 1
    for dim in re.findall(r"\[([^\]]*)\]", range_text):
        parts = split_top_level(dim, ":")
        if len(parts) != 2:
            return None
        left = eval_const(parts[0], env)
        right = eval_const(parts[1], env)
        if left is None or right is None:
            return None
        width *= abs(left - right) + 1
    return width


def collect_identifiers(expr):
    """Identifiers referenced in a connection expression (literals removed)."""
    cleaned = BASED_LITERAL_SUB_RE.sub(" ", expr)
    cleaned = re.sub(r"\$\w+", " ", cleaned)  # system functions
    return [i for i in re.findall(r"\b[a-zA-Z_]\w*\b", cleaned)
            if i not in SV_KEYWORDS]


def expr_width(expr, signals, env):
    """Width of a connection expression; None when not resolvable."""
    expr = expr.strip()
    if not expr:
        return None
    m = SIZED_LITERAL_RE.match(expr)
    if m:
        return int(m.group(1))
    if re.fullmatch(r"\d+", expr) or re.fullmatch(r"'\s*[01xXzZ]", expr):
        return None  # unsized literal: context-sized in SV
    if re.fullmatch(r"\w+", expr):
        if expr in signals:
            rng, unpacked = signals[expr]
            return None if unpacked else range_width(rng, env)
        return None  # parameter or unknown — width not checked
    m = re.fullmatch(r"(\w+)\s*\[([^\]]+)\]", expr)
    if m:
        base, idx = m.group(1), m.group(2)
        if base not in signals:
            return None
        parts = split_top_level(idx, ":")
        if len(parts) == 1:
            return 1 if eval_const(parts[0], env) is not None else None
        if len(parts) == 2:
            left = eval_const(parts[0], env)
            right = eval_const(parts[1], env)
            if left is None or right is None:
                return None
            return abs(left - right) + 1
        return None
    if expr.startswith("{") and expr.endswith("}"):
        inner = expr[1:-1]
        m = re.fullmatch(r"\s*(\w+|\d+)\s*\{(.*)\}\s*", inner, re.DOTALL)
        if m:  # replication {N{...}}
            count = eval_const(m.group(1), env)
            inner_w = expr_width("{" + m.group(2) + "}", signals, env)
            return count * inner_w if count and inner_w else None
        total = 0
        for part in split_top_level(inner):
            w = expr_width(part, signals, env)
            if w is None:
                return None
            total += w
        return total
    return None


# ---------------------------------------------------------------------------
# Top module body analysis
# ---------------------------------------------------------------------------

def collect_top_env(top):
    """Parameter environment for the top module (params + localparams)."""
    env = dict(top["params"])
    body = top["text"][top["body_span"][0]:top["body_span"][1]]
    for m in LOCALPARAM_RE.finditer(body):
        env[m.group(1)] = " ".join(m.group(2).split())
    return env


def collect_signals(top):
    """Map name → (packed_range|None, has_unpacked) for top ports + body decls."""
    signals = {}
    for p in top["ports"]:
        signals[p["name"]] = (p["range"], p["unpacked"])
    start, end = top["body_span"]
    body = top["text"][start:end]
    for m in DECL_RE.finditer(body):
        packed = m.group(1).strip() or None
        for item in split_top_level(m.group(2)):
            item = item.split("=", 1)[0].strip()
            nm = re.match(r"(\w+)((?:\s*\[[^\]]*\])*)", item)
            if nm:
                signals[nm.group(1)] = (packed, bool(nm.group(2).strip()))
    return signals


def find_instances(top, module_defs):
    """Locate instantiations of known modules inside the top module body."""
    text = top["text"]
    start, end = top["body_span"]
    instances = []
    for mod_name in module_defs:
        if mod_name == top["name"]:
            continue
        for m in re.finditer(rf"\b{re.escape(mod_name)}\b", text[start:end]):
            pos = start + m.end()
            i = skip_ws(text, pos)
            overrides_text = None
            try:
                if i < end and text[i] == "#":
                    i = skip_ws(text, i + 1)
                    overrides_text, i = extract_balanced(text, i)
                    i = skip_ws(text, i)
                nm = re.match(r"[a-zA-Z_]\w*", text[i:end])
                if not nm:
                    continue
                inst_name = nm.group(0)
                i = skip_ws(text, i + nm.end())
                if i >= end or text[i] != "(":
                    continue
                conn_text, conn_end = extract_balanced(text, i)
            except ParseError:
                continue
            instances.append({
                "module": mod_name,
                "instance": inst_name,
                "line": line_of(text, start + m.start()),
                "overrides_text": overrides_text,
                "conn_text": conn_text,
                "conn_start": i + 1,
            })
    instances.sort(key=lambda x: x["line"])
    return instances


def find_unknown_instantiations(top, module_defs):
    """Heuristic: `<type> [#(...)] <inst> ( .` where <type> is undefined."""
    text = top["text"]
    start, end = top["body_span"]
    body = text[start:end]
    unknown = []
    pattern = re.compile(
        r"\b([a-zA-Z_]\w*)\s*(?:#\s*\((?:[^()]|\([^()]*\))*\)\s*)?"
        r"([a-zA-Z_]\w*)\s*\(\s*\.")
    for m in pattern.finditer(body):
        mod, inst = m.group(1), m.group(2)
        if mod in SV_KEYWORDS or inst in SV_KEYWORDS:
            continue
        if mod in module_defs:
            continue
        unknown.append({"module": mod, "instance": inst,
                        "line": line_of(text, start + m.start())})
    return unknown


CONN_RE = re.compile(
    r"\.\s*(\*|[a-zA-Z_]\w*)\s*(\(((?:[^()]|\([^()]*\))*)\))?")


def parse_connections(inst, text):
    """Parse named connections; returns (connections, has_positional, has_wildcard)."""
    conns = []
    has_wildcard = False
    covered_spans = []
    base = inst["conn_start"]
    for m in CONN_RE.finditer(inst["conn_text"]):
        covered_spans.append(m.span())
        if m.group(1) == "*":
            has_wildcard = True
            continue
        expr = m.group(3) if m.group(2) is not None else m.group(1)
        conns.append({"port": m.group(1),
                      "expr": (expr or "").strip(),
                      "explicit_empty": m.group(2) is not None
                                        and not (expr or "").strip(),
                      "line": line_of(text, base + m.start())})
    # Positional detection: any top-level chunk that is not a named/.* form.
    has_positional = any(not c.startswith(".")
                         for c in split_top_level(inst["conn_text"]))
    return conns, has_positional, has_wildcard


def collect_driven_names(top, instances, module_defs, text):
    """Textual heuristic for names driven inside the top module body."""
    start, end = top["body_span"]
    body = text[start:end]
    driven = set()
    for m in re.finditer(r"\bassign\b([^;=]*)=", body):
        driven.update(collect_identifiers(m.group(1)))
    for m in re.finditer(r"(\w+)\s*(?:\[[^\]]*\]\s*)*(?:<=|=)(?!=)", body):
        driven.add(m.group(1))
    for inst in instances:
        mdef = module_defs.get(inst["module"])
        if not mdef:
            continue
        directions = {p["name"]: p["direction"] for p in mdef["ports"]}
        conns, _, _ = parse_connections(inst, text)
        for c in conns:
            if directions.get(c["port"]) in ("output", "inout") and c["expr"]:
                driven.update(collect_identifiers(c["expr"]))
    return driven


# ---------------------------------------------------------------------------
# Checking
# ---------------------------------------------------------------------------

def check_top(top, module_defs, file_labels):
    """Run all static connectivity checks; return (violations, summary)."""
    text = top["text"]
    top_file = file_labels[top["file"]]
    env = collect_top_env(top)
    signals = collect_signals(top)
    instances = find_instances(top, module_defs)
    violations = []
    connections_checked = 0
    width_checked = 0
    width_skipped = 0
    has_unanalyzed_connections = False

    def add(severity, check, line, detail, instance=None, module=None,
            port=None, file=top_file):
        violations.append({
            "severity": severity, "check": check, "file": file, "line": line,
            "instance": instance, "module": module, "port": port,
            "detail": detail,
        })

    for u in find_unknown_instantiations(top, module_defs):
        add("warning", "missing_module_def", u["line"],
            f"module '{u['module']}' instantiated as '{u['instance']}' but "
            "no definition file was provided — connectivity not checked",
            instance=u["instance"], module=u["module"])

    for inst in instances:
        mdef = module_defs[inst["module"]]
        port_map = {p["name"]: p for p in mdef["ports"]}

        # Submodule parameter environment: defaults overridden per instance.
        sub_env = {}
        overrides = {}
        if inst["overrides_text"]:
            for chunk in split_top_level(inst["overrides_text"]):
                m = re.fullmatch(r"\.\s*(\w+)\s*\((.*)\)", chunk, re.DOTALL)
                if m:
                    overrides[m.group(1)] = m.group(2).strip()
        for name, default in mdef["params"]:
            src_expr = overrides.get(name, default)
            # Overrides are evaluated in the TOP env; defaults in sub env.
            val = eval_const(src_expr, env if name in overrides else sub_env)
            sub_env[name] = val if val is not None else src_expr

        conns, has_positional, has_wildcard = parse_connections(inst, text)
        if has_positional or has_wildcard:
            has_unanalyzed_connections = True
        if has_positional:
            add("warning", "positional_connection", inst["line"],
                "positional port connections are not analyzed — use named "
                "connections", instance=inst["instance"],
                module=inst["module"])
        if has_wildcard:
            add("warning", "wildcard_connection", inst["line"],
                "`.*` implicit connections are not analyzed",
                instance=inst["instance"], module=inst["module"])

        seen_ports = set()
        for c in conns:
            connections_checked += 1
            port = port_map.get(c["port"])
            if port is None:
                add("error", "unknown_port", c["line"],
                    f"module '{inst['module']}' has no port '{c['port']}'",
                    instance=inst["instance"], module=inst["module"],
                    port=c["port"])
                continue
            seen_ports.add(c["port"])
            if c["explicit_empty"]:
                severity = "error" if port["direction"] == "input" else "warning"
                add(severity, "dangling_port", c["line"],
                    f"{port['direction']} port '{c['port']}' is explicitly "
                    "unconnected `()`",
                    instance=inst["instance"], module=inst["module"],
                    port=c["port"])
                continue
            expr = c["expr"]
            for ident in collect_identifiers(expr):
                if ident not in signals and ident not in env:
                    add("error", "undeclared_signal", c["line"],
                        f"connection expression '{expr}' references "
                        f"'{ident}', which is not declared in "
                        f"'{top['name']}'",
                        instance=inst["instance"], module=inst["module"],
                        port=c["port"])
            port_w = (None if port["unpacked"]
                      else range_width(port["range"], sub_env))
            sig_w = expr_width(expr, signals, env)
            if port_w is None or sig_w is None:
                width_skipped += 1
            else:
                width_checked += 1
                if port_w != sig_w:
                    add("error", "width_mismatch", c["line"],
                        f"port '{c['port']}' width {port_w} != connection "
                        f"'{expr}' width {sig_w}",
                        instance=inst["instance"], module=inst["module"],
                        port=c["port"])

        if not has_wildcard and not has_positional:
            for pname, port in port_map.items():
                if pname not in seen_ports:
                    add("warning", "unconnected_port", inst["line"],
                        f"{port['direction']} port '{pname}' of "
                        f"'{inst['module']}' is not connected",
                        instance=inst["instance"], module=inst["module"],
                        port=pname)

    # The undriven-output check is unsound when any instance uses positional
    # or `.*` connections (those are not analyzed) — skip it rather than
    # emit false positives; the per-instance warnings already flag this.
    driven = (collect_driven_names(top, instances, module_defs, text)
              if not has_unanalyzed_connections else None)
    header_region = text[top["header_start"]:top["body_span"][0]]
    for p in top["ports"]:
        if (driven is not None and p["direction"] == "output"
                and p["name"] not in driven):
            offset = header_region.find(p["name"])
            line = (line_of(text, top["header_start"] + offset)
                    if offset >= 0 else top["header_line"])
            add("error", "undriven_output", line,
                f"top-level output '{p['name']}' is never driven "
                "(no instance output, assign, or procedural assignment)",
                port=p["name"])

    violations.sort(key=lambda v: (v["file"], v["line"],
                                   v["instance"] or "", v["port"] or "",
                                   v["check"]))
    errors = sum(1 for v in violations if v["severity"] == "error")
    warnings = sum(1 for v in violations if v["severity"] == "warning")
    summary = {
        "errors": errors,
        "warnings": warnings,
        "instances": len(instances),
        "connections_checked": connections_checked,
        "width_checks": {"checked": width_checked, "skipped": width_skipped},
    }
    return violations, summary


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Static port connectivity checker: verifies named "
                    "connections, literal/parameter-resolvable widths, "
                    "dangling ports, and undriven top-level outputs across "
                    "a top module and its submodules. Emits a deterministic "
                    "JSON violation report.",
        epilog="Limitations: ANSI port lists only; width resolution covers "
               "integer literals, parameter/localparam chains, $clog2, and "
               "+-*/%% arithmetic (anything else is skipped, never guessed); "
               "positional and `.*` connections are flagged but not "
               "analyzed; only the given top module's body is checked. "
               "Dynamic behavior (reset propagation, handshakes, data flow) "
               "is Tier 4 simulation territory — not this script.")
    parser.add_argument("files", nargs="+",
                        help="SystemVerilog sources: top-level module file "
                             "plus all submodule definition files")
    parser.add_argument("--top",
                        help="top module name (default: first module in the "
                             "first file)")
    parser.add_argument("-o", "--output",
                        help="output JSON path (default: stdout)")
    args = parser.parse_args(argv)

    module_defs = {}
    file_labels = {}
    order = []
    for f in args.files:
        path = Path(f)
        if not path.is_file():
            print(f"ERROR: input file not found: {f}", file=sys.stderr)
            return 2
        stripped = strip_comments_preserve(path.read_text())
        try:
            mods = parse_modules(f, stripped)
        except ParseError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
        file_labels[f] = f
        for mod in mods:
            if mod["name"] in module_defs:
                print(f"ERROR: module '{mod['name']}' defined in both "
                      f"{module_defs[mod['name']]['file']} and {f}",
                      file=sys.stderr)
                return 2
            module_defs[mod["name"]] = mod
            order.append(mod["name"])

    if not module_defs:
        print("ERROR: no module declarations found in the given files",
              file=sys.stderr)
        return 2

    if args.top:
        top = module_defs.get(args.top)
        if top is None:
            print(f"ERROR: top module '{args.top}' not found "
                  f"(parsed: {', '.join(sorted(module_defs))})",
                  file=sys.stderr)
            return 2
    else:
        first_file = args.files[0]
        top = next((module_defs[n] for n in order
                    if module_defs[n]["file"] == first_file), None)
        if top is None:
            print(f"ERROR: no module found in {first_file}", file=sys.stderr)
            return 2

    violations, summary = check_top(top, module_defs, file_labels)
    verdict = "PASS" if summary["errors"] == 0 else "FAIL"
    report = {
        "tool": "check_connectivity.py",
        "top_module": top["name"],
        "files": list(args.files),
        "modules_parsed": sorted(module_defs),
        "verdict": verdict,
        "summary": summary,
        "violations": violations,
    }

    payload = json.dumps(report, indent=2) + "\n"
    if args.output:
        out = Path(args.output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(payload)
        print(f"Wrote {out}: verdict={verdict} errors={summary['errors']} "
              f"warnings={summary['warnings']}")
    else:
        sys.stdout.write(payload)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
