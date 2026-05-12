# RTL Documentation Conventions

A quick reference for filling `<!-- LLM_FILL: ... -->` markers and choosing
visual elements in `docs/rtl/{module}.md`. Stays under 200 lines so it can be
consulted in one read.

## 1. Naming

| Element | Convention | Example |
|---------|-----------|---------|
| Port direction prefix | `i_`, `o_`, `io_` (NOT suffix) | `i_data`, `o_valid` |
| Clock port | `clk` (single) or `{domain}_clk` | `sys_clk`, `pixel_clk` |
| Reset port | `rst_n` (single) or `{domain}_rst_n` (active-low async) | `sys_rst_n` |
| Instance | `u_*` prefix | `u_range_coder` |
| Parameter | `UPPER_SNAKE_CASE` | `DATA_WIDTH` |
| Localparam | `L_*` prefix, `UPPER_SNAKE_CASE` | `L_FIFO_DEPTH` |
| FSM state | `ST_*` prefix, `UPPER_SNAKE_CASE` | `ST_IDLE`, `ST_ENCODE` |

If a violation is recorded in the generated doc's banner, do not rewrite the
RTL — surface it for the human RTL engineer.

## 2. Table formats

### Port table column order

`Port Name | Direction | Width | Clock Domain | Kind | Description`

`Kind` is one of `clock`, `reset`, `data`, `protocol`. The renderer fills
`clock` and `reset` automatically based on naming; `data` is the default;
`protocol` should be applied by the LLM when filling marker descriptions for
AXI/AHB/APB signals.

### Parameter table

`Parameter | Type | Default | Description`

### Instance table

`Instance | Module | Purpose`

## 3. Diagram tool choice

- **Block diagrams** (sub-instance hierarchy, data flow between blocks) →
  **D2**. Match the project's `<markdown_diagram_rule>`.
- **FSM** → **Mermaid `stateDiagram-v2`**.
- **Flow / sequence** → **Mermaid `flowchart`** or `sequenceDiagram`.
- Do not mix D2 and Mermaid for the same diagram type within a single doc.

## 4. Length guidance

- Overview: 100-200 characters. One or two sentences. State the module's
  responsibility, not its implementation.
- Per-state description: 1-2 lines. What the state does and what triggers
  the transition out of it.
- Per-port description: 1 line. Skip if the port name already conveys the
  meaning (e.g., `i_valid`).
- Design Notes: optional. Use only when the module has a non-obvious
  property a reader of the code would not see immediately (e.g., "the
  internal counter wraps at DATA_WIDTH-2 to avoid the W-1 edge case").

## 5. Anti-patterns

- Leaving `<!-- LLM_FILL: ... -->` markers in the committed doc — fail.
- Leaving `{{PLACEHOLDER}}` strings — fail (the renderer should have
  replaced them; if any remain, fix the renderer or the JSON instead).
- Restating the port name in its description ("i_valid — input valid signal").
- Inventing port descriptions when no comment or naming clue exists. Leave
  the cell blank rather than fabricating.
- Writing "TODO" inside the doc body. If something cannot be documented yet,
  remove the corresponding section and note absence in the document footer.
