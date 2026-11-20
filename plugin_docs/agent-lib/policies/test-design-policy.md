# RTL Test Case Design Policy

Build stimulus around the source-backed behavior and expected result of each
selected point. Use equivalence class partitioning (ECP) for distinct behaviors,
boundary value analysis (BVA) at specified transitions, state transition testing
(STT) for stateful behavior, or a decision table (DT) when interacting controls
change the result. Use a cross only when the combination has a distinct obligation.

Keep DUT observations independent of the oracle. For a behavioral refC, compare
accepted transactions against model output using the specified numeric tolerance.
Cycle latency, reset and backpressure checks need a hardware contract. If a
material assumption changes the expected result, record it for resolution.
