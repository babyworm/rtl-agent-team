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
docs/phase-1-research/requirements.json|p1-requirements
docs/phase-1-research/io_definition.json|p1-io-definition
docs/phase-1-research/domain-analysis.md|p1-domain-analysis
EOF
      ;;
    3)
      cat <<'EOF'
docs/phase-2-architecture/architecture.md|p2-architecture
refc|p2-ref-model
docs/phase-2-architecture/bandwidth_report.json|p2-bandwidth
EOF
      ;;
    4)
      cat <<'EOF'
docs/phase-3-uarch|p3-uarch-specs
docs/phase-1-research/io_definition.json|p1-io-definition
EOF
      ;;
    5)
      cat <<'EOF'
docs/phase-1-research/requirements.json|p1-requirements
EOF
      ;;
    6)
      cat <<'EOF'
reviews/phase-5-verify/final-compliance.md|p5-compliance
EOF
      ;;
  esac
}

artmap_optional() {
  case "$1" in
    3)
      cat <<'EOF'
docs/phase-1-research/requirements.json|p1-requirements
docs/phase-1-research/io_definition.json|p1-io-definition
EOF
      ;;
    4)
      cat <<'EOF'
docs/phase-3-uarch/clock-domain-map.md|p3-clock-domain-map
docs/phase-3-uarch/protocol-assignments.md|p3-protocol-assignments
docs/phase-2-architecture/architecture.md|p2-architecture
EOF
      ;;
    5)
      cat <<'EOF'
docs/phase-4-rtl/module-descriptions.md|p4-module-descriptions
docs/phase-4-rtl/stream-b-sva-skeletons.md|p4-stream-b-sva
docs/phase-4-rtl/stream-b-cdc-preliminary.md|p4-stream-b-cdc
docs/phase-4-rtl/stream-b-tb-skeletons.md|p4-stream-b-tb
EOF
      ;;
    6)
      cat <<'EOF'
docs/phase-4-rtl/module-descriptions.md|p4-module-descriptions
EOF
      ;;
  esac
}
