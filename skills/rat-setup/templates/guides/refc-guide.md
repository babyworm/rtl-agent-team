# C Reference Model

## Standards

- **Language**: C11 (`-std=c11`). C++ is NOT used for reference models
- **Model type**: Functional model — no clock, no reset, pure algorithm
- **External memory**: Access functions must be abstracted (callback/function pointer)
- **DPI-C**: Primary integration method with SystemVerilog

## Directory Structure

```
refc/
├── src/              # Flat source (single-module ref model)
├── {module}/         # Per-module ref model (multi-module projects)
├── include/          # Common headers
├── build/            # Build output (.so for DPI-C)
├── test/             # Ref model unit tests
└── vectors/          # Test vectors
    ├── perf/         # Performance test vectors
    └── conformance/  # Conformance test vectors
```

## Build

```bash
gcc -std=c11 -shared -fPIC -o build/lib{module}_ref.so src/*.c -Iinclude
```

<!-- rat-version: 0.7.7 -->
