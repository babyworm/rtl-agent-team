# Interpretation Stability Report
- Phase: phase-1-research
- Date: {{DATE}}
- v1 path: {{V1_PATH}}
- v2 path: {{V2_PATH}}

## Alignment Summary
- v1 requirements: {{V1_COUNT}}
- v2 requirements: {{V2_COUNT}}
- Aligned pairs: {{ALIGNED_COUNT}} (avg similarity: {{AVG_SIM}})
- v1-only (removed after clarification): {{V1_ONLY_COUNT}}
- v2-only (added after clarification): {{V2_ONLY_COUNT}}

## Changes From Clarification
| Source Section | Direction | Description |
|----------------|-----------|-------------|
| {{SECTION}} | REMOVED/ADDED | {{DESCRIPTION}} |

<!-- Sections below are appended by the orchestrator (Step 7.9), not by stability_check.py -->

## Adversarial Challenge Resolution
| Challenge | Source Section | Severity | Resolution | Status |
|-----------|--------------|----------|------------|--------|
| {{CHALLENGE_DESC}} | {{SECTION}} | HIGH/MEDIUM/LOW | {{USER_DECISION}} | RESOLVED/DOCUMENTED/NOT_GENUINE |

## Gate Result
- Genuine challenges: {{GENUINE}}
- Resolved: {{RESOLVED}}
- Resolution ratio: {{RATIO}} (threshold: 0.8)
- All HIGH resolved: {{YES/NO}}
- **Gate: {{PASS/FAIL}}**
