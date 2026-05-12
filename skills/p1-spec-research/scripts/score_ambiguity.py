#!/usr/bin/env python3
"""Compute ambiguity score across 4 RTL goal dimensions.

Used by goal-clarifier agent during interview loop to:
  1. Display human-readable scoreboard each round.
  2. Decide exit condition (ambiguity ≤ 20%) in JSON mode.

Exit codes:
  0  success
  2  invalid score (outside 0-100)
"""
from __future__ import annotations

import argparse
import json
import sys

DIMENSIONS = ["functionality", "ppa", "scope", "verification"]
DISPLAY = {
    "functionality": "Functionality",
    "ppa":           "PPA Target",
    "scope":         "Scope",
    "verification":  "Verification",
}
_COL_WIDTH = 18  # label_len + colon + spaces + digits = 18 before "/100"
EXIT_THRESHOLD = 20


def _validate(name: str, value: int) -> None:
    if not 0 <= value <= 100:
        print(f"error: {name} score must be 0-100 (got {value})", file=sys.stderr)
        sys.exit(2)


def compute(scores: dict[str, int]) -> dict:
    avg = sum(scores.values()) / len(scores)
    ambiguity = round(100 - avg)
    lowest = min(scores, key=scores.get)
    return {
        "ambiguity": ambiguity,
        "lowest": lowest,
        "lowest_score": scores[lowest],
        "exit": ambiguity <= EXIT_THRESHOLD,
        "scores": scores,
    }


def main() -> int:
    p = argparse.ArgumentParser(description="Score RTL goal ambiguity across 4 dimensions.")
    for d in DIMENSIONS:
        p.add_argument(f"--{d}", type=int, required=True, help=f"Score 0-100 for {d}")
    p.add_argument("--json", action="store_true", help="Emit JSON instead of human-readable scoreboard")
    p.add_argument("--round", type=int, default=None, help="Round number for the human-mode header")
    args = p.parse_args()

    scores = {d: getattr(args, d) for d in DIMENSIONS}
    for d, v in scores.items():
        _validate(d, v)

    result = compute(scores)

    if args.json:
        print(json.dumps(result))
        return 0

    if args.round is not None:
        print(f"=== Round {args.round} ===")
    else:
        print("=== Scoreboard ===")
    for d in DIMENSIONS:
        label = DISPLAY[d]
        fw = _COL_WIDTH - len(label) - 1  # colon takes 1 char
        print(f"{label}:{scores[d]:>{fw}}/100")
    print(f"Ambiguity:     {result['ambiguity']}%")
    print(f"Lowest:        {DISPLAY[result['lowest']]} ({result['lowest_score']})")
    print(f"Exit decision: {'EXIT' if result['exit'] else 'CONTINUE'}  (target ≤ {EXIT_THRESHOLD}%)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
