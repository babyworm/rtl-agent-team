# Docker EDA Image Details (rat-setup reference)

Read this file only when the user chooses the `docker` install mode (Q1) or asks about the
Docker EDA image build args, run commands, or included tool versions.

## Build (versions are configurable)
```bash
docker build -t rtl-eda-tools \
  --build-arg VERILATOR_VERSION=5.024 \
  --build-arg SLANG_VERSION=v11.0 \
  --build-arg SVLENS_VERSION=v0.3.6 \
  --build-arg SYSTEMC_VERSION=3.0.2 \
  "${CLAUDE_PLUGIN_ROOT}/docker/"
```

## Run
```bash
docker run -it --rm \
  --user "$(id -u):$(id -g)" --env HOME=/tmp \
  --mount "type=bind,src=$(pwd),dst=/workspace" \
  --workdir /workspace rtl-eda-tools

# GUI (gtkwave) support
docker run -it --rm \
  --user "$(id -u):$(id -g)" --env HOME=/tmp --env "DISPLAY=$DISPLAY" \
  --mount "type=bind,src=/tmp/.X11-unix,dst=/tmp/.X11-unix" \
  --mount "type=bind,src=$(pwd),dst=/workspace" \
  --workdir /workspace rtl-eda-tools
```

## Included Tools
| Tool | Version | Purpose |
|------|---------|---------|
| verilator | 5.024 (configurable) | Simulation + Lint |
| verible | latest release | Style Lint + Formatting |
| yosys | OSS CAD Suite | Synthesis |
| iverilog | apt latest | Alternative simulator |
| slang | v11.0 (configurable) | IEEE 1800 Semantic Lint |
| svlens | v0.3.6 (configurable) | Structural analysis + CDC |
| sby (SymbiYosys) | OSS CAD Suite + boolector, z3, yices2 | Formal verification |
| gtkwave | apt latest | Waveform viewer |
| SystemC/TLM-2.0 | 3.0.2 (configurable) | Reference model + BFM |
| cocotb + extensions | pip latest | Functional verification |
| gcc/g++ | apt latest | Reference model build |
