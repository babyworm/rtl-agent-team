#!/usr/bin/env bash
# RTL Naming Convention Checker
# Supplements Verilator/Verible/slang with project-specific convention checks.
# Usage: bash check_conventions.sh <file_or_directory>
#
# Exit codes: 0 = PASS, 1 = FAIL (violations found)

set -euo pipefail

TARGET="${1:-.}"
VIOLATIONS=0
REPORT=""

add_violation() {
  local file="$1" line="$2" rule="$3" msg="$4"
  REPORT+="  CONVENTION  ${file}:${line}  ${rule}  ${msg}"$'\n'
  ((VIOLATIONS++))
}

check_file() {
  local file="$1"

  # Rule 1: No reg/wire — must use logic
  while IFS=: read -r lineno content; do
    add_violation "$file" "$lineno" "NO_REG_WIRE" "Use 'logic' instead: $content"
  done < <(grep -nE '^\s*(reg|wire)\b' "$file" 2>/dev/null || true)

  # Rule 2: Port suffix _i/_o — should use i_/o_ prefix
  while IFS=: read -r lineno content; do
    add_violation "$file" "$lineno" "PORT_SUFFIX" "Use i_/o_ prefix instead of _i/_o suffix: $content"
  done < <(grep -nE '\b\w+_(i|o)\b\s*[,;)]' "$file" 2>/dev/null || true)

  # Rule 3: Clock naming — should be clk (single) or {domain}_clk (multiple)
  # Note: bare 'clk' is VALID for single-domain designs per CLAUDE.md
  while IFS=: read -r lineno content; do
    add_violation "$file" "$lineno" "CLOCK_NAME" "Use clk (single domain) or {domain}_clk format (e.g., sys_clk): $content"
  done < <(grep -nE '\b(clk_i|clk_o)\b\s*[,;)]' "$file" 2>/dev/null || true)

  # Rule 4: Reset naming — should be rst_n (single) or {domain}_rst_n (multiple)
  # Note: bare 'rst_n' is VALID for single-domain designs per CLAUDE.md
  while IFS=: read -r lineno content; do
    add_violation "$file" "$lineno" "RESET_NAME" "Use rst_n (single domain) or {domain}_rst_n format (e.g., sys_rst_n): $content"
  done < <(grep -nE '\b(rst_ni)\b\s*[,;)]' "$file" 2>/dev/null || true)

  # Rule 5: Instance prefix u_ — flag instances without it
  while IFS=: read -r lineno content; do
    # Extract instance name (module_name instance_name (...))
    inst_name=$(echo "$content" | grep -oE '\b\w+\s+\w+\s*\(' | tail -1 | awk '{print $2}' | tr -d '(')
    if [[ -n "$inst_name" && ! "$inst_name" =~ ^u_ && ! "$inst_name" =~ ^gen_ ]]; then
      add_violation "$file" "$lineno" "INSTANCE_PREFIX" "Instance '$inst_name' missing u_ prefix: $content"
    fi
  done < <(grep -nE '^\s*\w+\s+\w+\s*\(' "$file" 2>/dev/null | grep -vE '^\s*(if|for|while|case|always|assign|function|task|module|generate|initial|assert|assume|cover)\b' || true)

  # Rule 6: Generate prefix gen_
  while IFS=: read -r lineno content; do
    gen_label=$(echo "$content" | grep -oE '\b\w+\s*:' | head -1 | tr -d ':' | xargs)
    if [[ -n "$gen_label" && ! "$gen_label" =~ ^gen_ ]]; then
      add_violation "$file" "$lineno" "GENERATE_PREFIX" "Generate block '$gen_label' missing gen_ prefix: $content"
    fi
  done < <(grep -nE '^\s*\w+\s*:\s*(for|if)\b' "$file" 2>/dev/null || true)
}

# Find all .sv/.v files
if [[ -d "$TARGET" ]]; then
  while IFS= read -r f; do
    check_file "$f"
  done < <(find "$TARGET" -name '*.sv' -o -name '*.v' | sort)
elif [[ -f "$TARGET" ]]; then
  check_file "$TARGET"
else
  echo "ERROR: Target '$TARGET' not found"
  exit 2
fi

# Report
echo "=== Convention Check Report ==="
echo "Files checked: $(if [[ -d "$TARGET" ]]; then find "$TARGET" -name '*.sv' -o -name '*.v' | wc -l; else echo 1; fi)"
echo "Violations: $VIOLATIONS"
echo ""

if [[ $VIOLATIONS -gt 0 ]]; then
  echo "$REPORT"
  echo "VERDICT: FAIL ($VIOLATIONS convention violations)"
  exit 1
else
  echo "VERDICT: PASS (no convention violations)"
  exit 0
fi
