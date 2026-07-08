---
name: test-design-policy
description: "Internal reference: test design policy (agent-loaded; do not invoke)."
user-invocable: false
---

# RTL Test Case Design Policy

## Purpose

Codifies systematic test case design techniques for deriving test vectors from specifications.
Referenced by testbench-dev and verification orchestrators.

## Equivalence Class Partitioning (ECP)

For each input signal:
- Identify valid equivalence classes from uarch spec (e.g., opcode ranges, mode encodings)
- Identify invalid equivalence classes (undefined encodings, reserved ranges)
- Select at least one representative value from each class
- Document: `{input_name: [{class: "valid_normal", range: "0x00-0x0F", representative: "0x05"}, ...]}`

## Boundary Value Analysis (BVA)

For each integer input of width W:
- Unsigned: test 0, 1, 2^(W-1)-1, 2^(W-1), 2^W-2, 2^W-1
- Signed: test -(2^(W-1)), -(2^(W-1))+1, -1, 0, +1, 2^(W-1)-1
- For address inputs: test base, base+1, top-1, top (alignment boundaries)
- For counter/depth inputs: test 0, 1, depth-1, depth (full/empty conditions)

## State Transition Testing

For each FSM defined in uarch spec:
- Extract state list and valid transitions from spec
- Build state transition matrix (source_state x event -> target_state)
- Mandatory tests: all valid transitions (0-switch coverage)
- Recommended: all 1-switch transition pairs (N-1 switch coverage)
- At least one illegal transition attempt per state (verify no state corruption)
- Reset recovery: verify return to spec-defined reset state from every reachable state

## Decision Table Testing

For modules with >=3 boolean control inputs:
- Enumerate condition combinations (2^N for N conditions, or reduced set for don't-cares)
- Map each combination to expected action/output
- Generate one test per row (or per distinct action group if rows collapse)

## Corner Case Categories (by module type)

### Datapath modules
- All-zeros, all-ones input
- Sign extension boundary (MSB toggle)
- Overflow/underflow at arithmetic boundaries
- Back-to-back operations (no idle between)

### FSM/Control modules
- Immediate re-trigger after completion
- Simultaneous conflicting requests
- Stall/backpressure at every state boundary
- Timeout/watchdog expiry

### Interface modules (valid/ready)
- valid without ready (backpressure, hold >N cycles)
- ready without valid (idle consumption)
- Simultaneous assert/deassert
- Back-to-back transfers (zero-gap throughput)
- Single-beat and max-burst-length transfers

## Test Vector Derivation Workflow

1. Read uarch spec + io_definition.json
2. For each input: apply ECP -> list equivalence classes
3. For each integer input: apply BVA -> list boundary values
4. For each FSM: extract state transition matrix
5. For modules with >=3 boolean controls: build decision table
6. Merge results into unified test plan with coverage mapping
7. Prioritize: boundary values + state transitions first, then ECP representatives

## Anti-Patterns

- "100 random vectors" without coverage goal
- Testing only happy path (no error injection)
- Testing only reset -> single operation -> check (no sustained/stress scenarios)
- Copy-paste test vectors without traceability to spec requirement
