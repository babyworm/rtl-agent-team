#!/usr/bin/env python3
"""stability_check.py — Content-based requirement alignment and stability report.

Compares two iron-requirements.json files (v1 vs v2) and produces a
stability report documenting what changed after adversarial clarification.

This is an INFORMATIONAL audit tool, not a gate.
The adversarial gate uses the challenge report directly.

Usage:
    python3 scripts/stability_check.py v1.json v2.json [-o report.md]
"""

import argparse
import json
import re
from datetime import datetime, timezone

# ═══ Tokenizer ═══════════════════════════════════════════════════════════════

STOPWORDS = {"the", "a", "an", "is", "are", "was", "were", "be", "been",
             "being", "have", "has", "had", "do", "does", "did", "will",
             "would", "shall", "should", "may", "might", "can", "could",
             "of", "in", "to", "for", "with", "on", "at", "from", "by",
             "and", "or", "not", "no", "but", "if", "then", "else",
             "this", "that", "these", "those", "it", "its"}


def tokenize(text):
    """Lowercase, split on non-alphanumeric (preserving underscores), remove stopwords."""
    tokens = re.findall(r'[a-z0-9_]+', text.lower())
    return set(t for t in tokens if t not in STOPWORDS and len(t) > 1)


def jaccard(set_a, set_b):
    """Jaccard similarity: |intersection| / |union|."""
    if not set_a and not set_b:
        return 1.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


# ═══ Pair Similarity ═════════════════════════════════════════════════════════

def compute_pair_similarity(r1, r2):
    """Per-pair similarity on structured fields. Returns 0.0-1.0."""
    score = 0.0

    # source match (25%) — section (15%) + line proximity (10%)
    src1 = r1.get("source") or {}
    src2 = r2.get("source") or {}
    sec_match = 1.0 if (src1.get("section") and src1.get("section") == src2.get("section")) else 0.0
    line1, line2 = src1.get("line", 0), src2.get("line", 0)
    line_proximity = 1.0 if (line1 and line2 and abs(line1 - line2) <= 5) else 0.0
    score += 0.15 * sec_match + 0.10 * line_proximity

    # type + priority match (15%)
    type_match = 1.0 if r1.get("type") == r2.get("type") else 0.0
    prio_match = 1.0 if r1.get("priority") == r2.get("priority") else 0.0
    score += 0.15 * (0.5 * type_match + 0.5 * prio_match)

    # acceptance_criteria overlap (30%) — tokenized Jaccard per AC item, averaged
    ac1 = r1.get("acceptance_criteria", [])
    ac2 = r2.get("acceptance_criteria", [])
    if ac1 and ac2:
        ac_sims = []
        for a1 in ac1:
            best = max((jaccard(tokenize(a1), tokenize(a2)) for a2 in ac2), default=0.0)
            ac_sims.append(best)
        score += 0.30 * (sum(ac_sims) / len(ac_sims))
    elif not ac1 and not ac2:
        score += 0.30

    # description keyword overlap (20%) — Jaccard on tokenized description
    score += 0.20 * jaccard(
        tokenize(r1.get("description", "")),
        tokenize(r2.get("description", ""))
    )

    # complexity match (10%)
    score += 0.10 * (1.0 if r1.get("complexity") == r2.get("complexity") else 0.0)

    return score


# ═══ Requirement Alignment ════════════════════════════════════════════════════

def align_requirements(v1_reqs, v2_reqs):
    """Align requirements using source.section as primary key.
    Fallback: greedy matching on description token similarity.

    Note: Multiple requirements may share the same source.section.
    Pass 1 performs best-match within each section group;
    excess requirements fall through to Pass 2.
    If ALL items have blank source.section, everything goes through Pass 2
    (greedy Jaccard). The stability report should emit a WARNING when >50%
    of alignments came from Pass 2 rather than Pass 1."""

    aligned = []  # [(v1_req, v2_req, similarity)]
    v2_used = set()
    pass1_count = 0

    # Pass 1: source-key grouping with best-match within each group
    v2_by_section = {}
    for j, r2 in enumerate(v2_reqs):
        sec = (r2.get("source") or {}).get("section", "")
        if sec:
            v2_by_section.setdefault(sec, []).append((j, r2))

    for r1 in v1_reqs:
        sec = (r1.get("source") or {}).get("section", "")
        if sec and sec in v2_by_section:
            best_sim, best_j, best_r2 = -1.0, -1, None
            for j, r2 in v2_by_section[sec]:
                if j not in v2_used:
                    sim = compute_pair_similarity(r1, r2)
                    if sim > best_sim:
                        best_sim, best_j, best_r2 = sim, j, r2
            if best_j >= 0:
                aligned.append((r1, best_r2, best_sim))
                v2_used.add(best_j)
                pass1_count += 1

    # Pass 2: greedy matching on remaining by description similarity
    v1_unmatched = [r for r in v1_reqs
                    if not any(a[0] is r for a in aligned)]
    v2_unmatched = [(j, r) for j, r in enumerate(v2_reqs)
                    if j not in v2_used]

    for r1 in v1_unmatched:
        best_sim, best_j, best_r2 = 0.0, -1, None
        t1 = tokenize(r1.get("description", ""))
        for j, r2 in v2_unmatched:
            t2 = tokenize(r2.get("description", ""))
            sim = jaccard(t1, t2)
            if sim > best_sim:
                best_sim, best_j, best_r2 = sim, j, r2
        if best_sim >= 0.4 and best_j >= 0:
            full_sim = compute_pair_similarity(r1, best_r2)
            aligned.append((r1, best_r2, full_sim))
            v2_unmatched = [(j, r) for j, r in v2_unmatched if j != best_j]

    # Rebuild v1_unmatched after Pass 2 consumed some items
    v1_still_unmatched = [r for r in v1_unmatched
                          if not any(a[0] is r for a in aligned)]

    pass2_count = len(aligned) - pass1_count
    return aligned, v1_still_unmatched, [r for _, r in v2_unmatched], pass1_count, pass2_count


# ═══ Gate Computation ═════════════════════════════════════════════════════════

def compute_gate(challenges, threshold=0.8):
    """Compute adversarial gate from challenge report.

    genuine = (HIGH + MEDIUM) - NOT_GENUINE
    resolved = RESOLVED + DOCUMENTED
    resolution_ratio = resolved / genuine (if genuine == 0: pass)
    gate_pass = (all HIGH resolved) AND (resolution_ratio >= threshold)
    """
    high_challenges = [c for c in challenges if c.get("severity") == "HIGH"]
    medium_challenges = [c for c in challenges if c.get("severity") == "MEDIUM"]

    actionable = high_challenges + medium_challenges
    not_genuine = [c for c in actionable if c.get("resolution") == "NOT_GENUINE"]
    genuine_list = [c for c in actionable if c.get("resolution") != "NOT_GENUINE"]
    genuine = len(genuine_list)

    resolved = len([c for c in genuine_list
                    if c.get("resolution") in ("RESOLVED", "DOCUMENTED")])

    all_high_resolved = all(
        c.get("resolution") in ("RESOLVED", "DOCUMENTED")
        for c in high_challenges
        if c.get("resolution") != "NOT_GENUINE"
    )

    if genuine == 0:
        resolution_ratio = 1.0
        gate_pass = True
    else:
        resolution_ratio = resolved / genuine
        gate_pass = all_high_resolved and (resolution_ratio >= threshold)

    return {
        "gate_pass": gate_pass,
        "resolution_ratio": resolution_ratio,
        "genuine": genuine,
        "resolved": resolved,
        "all_high_resolved": all_high_resolved,
        "total_challenges": len(challenges),
        "not_genuine_count": len(not_genuine),
    }


# ═══ Report Generation ════════════════════════════════════════════════════════

def generate_report(aligned, v1_only, v2_only, v1_path, v2_path,
                    pass1_count=0, pass2_count=0):
    """Generate stability-report.md content."""
    total_aligned = len(aligned)
    avg_sim = sum(s for _, _, s in aligned) / total_aligned if total_aligned else 0.0

    lines = [
        "# Interpretation Stability Report",
        "- Phase: phase-1-research",
        f"- Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
        f"- v1 path: {v1_path}",
        f"- v2 path: {v2_path}",
        "",
        "## Alignment Summary",
        f"- v1 requirements: {total_aligned + len(v1_only)}",
        f"- v2 requirements: {total_aligned + len(v2_only)}",
        f"- Aligned pairs: {total_aligned} (avg similarity: {avg_sim:.2f})",
        f"- v1-only (removed after clarification): {len(v1_only)}",
        f"- v2-only (added after clarification): {len(v2_only)}",
        f"- Pass 1 (section-based): {pass1_count}, Pass 2 (greedy): {pass2_count}",
        "",
    ]

    # WARNING if >50% alignments came from Pass 2
    if total_aligned > 0 and pass2_count > pass1_count:
        lines.append("> **WARNING**: >50% of alignments used greedy fallback (Pass 2).")
        lines.append("> source.section data may be missing or inconsistent.")
        lines.append("")

    if v1_only or v2_only:
        lines.append("## Changes From Clarification")
        lines.append("| Source Section | Direction | Description |")
        lines.append("|--------|-----------|-------------|")
        for r in v1_only:
            sec = (r.get("source") or {}).get("section", "?")
            lines.append(f"| {sec} | REMOVED | {r.get('description', '?')[:60]} |")
        for r in v2_only:
            sec = (r.get("source") or {}).get("section", "?")
            lines.append(f"| {sec} | ADDED | {r.get('description', '?')[:60]} |")
        lines.append("")

    return "\n".join(lines)


# ═══ CLI ══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Content-based requirement alignment and stability report")
    parser.add_argument("v1", help="Initial iron-requirements.json (v1)")
    parser.add_argument("v2", help="Post-clarification iron-requirements.json (v2)")
    parser.add_argument("-o", "--output", default=None, help="Output report path (.md)")
    args = parser.parse_args()

    with open(args.v1) as f:
        v1_data = json.load(f)
    with open(args.v2) as f:
        v2_data = json.load(f)

    v1_reqs = v1_data.get("requirements", [])
    v2_reqs = v2_data.get("requirements", [])

    aligned, v1_only, v2_only, p1_count, p2_count = align_requirements(v1_reqs, v2_reqs)
    report = generate_report(aligned, v1_only, v2_only, args.v1, args.v2, p1_count, p2_count)

    if args.output:
        with open(args.output, "w") as f:
            f.write(report)
        print(f"Stability report written to {args.output}")
    else:
        print(report)

    # Print summary
    avg_sim = sum(s for _, _, s in aligned) / len(aligned) if aligned else 0.0
    total = len(aligned) + len(v1_only) + len(v2_only)
    print(f"\nSummary: {total} entries — {len(aligned)} aligned, "
          f"{len(v1_only)} v1-only, {len(v2_only)} v2-only, avg_sim={avg_sim:.2f}")


if __name__ == "__main__":
    main()
