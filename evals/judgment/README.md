# Judgment prompt evaluation

These fixed fixtures check settled requirements, material ambiguity despite a low
average score, measured failure despite confidence, and an undefined verification
oracle. Each model gives one structured response. No review loops or grading retries
are run. A repair's affected verification can be required without adding a review.

```bash
python3 scripts/eval_prompts.py --variant both --output /tmp/rat-prompt-results
```

The baseline is `0db2ba5`. Agent prompts include their preloaded skill bodies so a
policy's instructions are measured as well. Current compiled prompts are read from
the working tree. Claude calls disable tools/hooks and have a per-case budget;
Codex calls use a read-only ephemeral session and retain configured reasoning effort.
The default comparison has 24 calls, at most $8 of Claude case budgets plus Codex
usage. Use `--models` and `--case` for a smaller check. Never retry a failed grade
without a change or a diagnosed execution problem.

Prompt byte/word counts are exact inventory measurements. Fixture scores concern
judgment behavior in the supplied context; they do not prove end-to-end routing,
RTL correctness, or quality on all designs. Keep provider/model identity, usage,
errors, and the baseline/current result files when reporting a comparison.
