#!/bin/sh
# Phase-to-artifact path mapping for spawn context manifest.
# Used by spawn-context-util.sh to check upstream artifact presence.
#
# artmap_required <phase_num> → newline-delimited "path|role" pairs
# artmap_optional <phase_num> → newline-delimited "path|role" pairs

artmap_required() {
  case "$1" in
    1)
      cat <<'EOF'
specs|spec-documents
EOF
      ;;
    2)
      cat <<'EOF'
docs/phase-1-research/iron-requirements.json|p1-iron-requirements
docs/phase-1-research/io_definition.json|p1-io-definition
docs/phase-1-research/domain-analysis.md|p1-domain-analysis
docs/phase-1-research/timing_constraints.json|p1-timing-constraints
EOF
      ;;
    3)
      cat <<'EOF'
docs/phase-2-architecture/architecture.md|p2-architecture
docs/phase-2-architecture/iron-requirements.json|p2-iron-requirements
refc|p2-ref-model
EOF
      ;;
    4)
      cat <<'EOF'
docs/phase-3-uarch|p3-uarch-specs
docs/phase-3-uarch/iron-requirements.json|p3-iron-requirements
docs/phase-1-research/io_definition.json|p1-io-definition
EOF
      ;;
    5)
      cat <<'EOF'
docs/phase-1-research/iron-requirements.json|p1-iron-requirements
rtl|p4-rtl-sources
docs/phase-4-rtl|p4-rtl-docs
sim|p4-unit-test-results
docs/phase-4-rtl/stream-b-sva-skeletons.md|p4-stream-b-sva
docs/phase-4-rtl/stream-b-cdc-preliminary.md|p4-stream-b-cdc
docs/phase-4-rtl/stream-b-tb-skeletons.md|p4-stream-b-tb
EOF
      ;;
    6)
      cat <<'EOF'
reviews/phase-5-verify/final-compliance.md|p5-compliance
EOF
      ;;
    7)
      # Phase 7 exploration — no required upstream artifacts (exempt from pipeline gates)
      ;;
  esac
}

artmap_optional() {
  case "$1" in
    2)
      cat <<'EOF'
docs/phase-1-research/open-requirements.json|p1-open-requirements
EOF
      ;;
    3)
      cat <<'EOF'
docs/phase-1-research/iron-requirements.json|p1-iron-requirements
docs/phase-1-research/io_definition.json|p1-io-definition
docs/phase-2-architecture/bandwidth_report.json|p2-bandwidth
EOF
      ;;
    4)
      cat <<'EOF'
bfm|p3-bfm-model
docs/phase-3-uarch/clock-domain-map.md|p3-clock-domain-map
docs/phase-3-uarch/protocol-assignments.md|p3-protocol-assignments
docs/phase-2-architecture/architecture.md|p2-architecture
refc/**/*.c|p4-refc-reference
EOF
      ;;
    5)
      cat <<'EOF'
docs/phase-4-rtl/module-descriptions.md|p4-module-descriptions
EOF
      ;;
    6)
      cat <<'EOF'
docs/phase-4-rtl/module-descriptions.md|p4-module-descriptions
EOF
      ;;
    7)
      # Phase 7 exploration — optional context from prior phases
      cat <<'EOF'
reviews/phase-6-review/improvements.md|p6-improvements
docs/phase-2-architecture/architecture.md|p2-architecture
EOF
      ;;
  esac
}
