---
paths:
  - "docs/**/*.md"
  - "reviews/**/*.md"
---

# Diagram Policy

| Diagram Type | Tool | Use For |
|-------------|------|---------|
| **Block diagram** | **D2** | Architecture, module hierarchy, HW block decomposition |
| **Flow / Interaction** | **Mermaid** | Pipeline stages, FSM, data/control flow, sequence diagrams |
| **ASCII flow diagram** | **Prohibited** | Do NOT use ASCII art — use D2 or Mermaid |

D2: architecture diagrams (`.d2` code blocks), per-module internal structure.
Mermaid: FSM (`stateDiagram-v2`), data flow (`flowchart`), sequences (`sequenceDiagram`).

<!-- rat-version: 0.7.7 -->
