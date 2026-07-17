# =============================================================================
# RTL Agent Team — Open-Source EDA Toolchain Docker Image
# All tools needed for the 6-Phase RTL design pipeline
# =============================================================================
#
# Build:
#   docker build -t rtl-eda-tools docker/
#   docker build -t rtl-eda-tools --build-arg VERILATOR_VERSION=5.024 docker/
#   docker build -t rtl-eda-tools --build-arg OSS_CAD_SUITE_TAG=2025-02-01 docker/
#
# Run (mount project):
#   docker run -it --rm --user "$(id -u):$(id -g)" --env HOME=/tmp \
#     --mount "type=bind,src=$(pwd),dst=/workspace" --workdir /workspace rtl-eda-tools
#
# Run with GUI (gtkwave):
#   docker run -it --rm --user "$(id -u):$(id -g)" --env HOME=/tmp \
#     --env "DISPLAY=$DISPLAY" --mount type=bind,src=/tmp/.X11-unix,dst=/tmp/.X11-unix \
#     --mount "type=bind,src=$(pwd),dst=/workspace" --workdir /workspace rtl-eda-tools
# =============================================================================

FROM ubuntu:24.04 AS base

ARG DEBIAN_FRONTEND=noninteractive
ARG VERILATOR_VERSION=5.024
ARG SLANG_VERSION=v11.0
ARG SVLENS_VERSION=v0.3.6
ARG SYSTEMC_VERSION=3.0.2
ARG OSS_CAD_SUITE_TAG=2025-02-01

LABEL maintainer="rtl-agent-team"
LABEL description="Open-source EDA toolchain for RTL design and verification"

# -----------------------------------------------------------------------------
# System packages
# -----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    autoconf \
    automake \
    bison \
    build-essential \
    ca-certificates \
    cmake \
    curl \
    flex \
    git \
    gnupg \
    help2man \
    libfl-dev \
    libfl2 \
    libgoogle-perftools-dev \
    libreadline-dev \
    make \
    ninja-build \
    perl \
    pkg-config \
    python3 \
    python3-dev \
    python3-pip \
    python3-venv \
    tcl-dev \
    unzip \
    wget \
    zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Verilator (simulation + lint) — build from source for latest version
# -----------------------------------------------------------------------------
RUN cd /tmp && \
    git clone --depth 1 --branch v${VERILATOR_VERSION} https://github.com/verilator/verilator.git && \
    cd verilator && \
    autoconf && \
    ./configure --prefix=/usr/local && \
    make -j$(nproc) && \
    make install && \
    rm -rf /tmp/verilator

# -----------------------------------------------------------------------------
# Icarus Verilog (alternative simulator)
# -----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    iverilog \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# OSS CAD Suite (Yosys + SymbiYosys + SAT/SMT solvers)
# Pre-built bundle from YosysHQ: no sudo needed, consistent tool versions
# https://github.com/YosysHQ/oss-cad-suite-build
# Provides: yosys, sby, boolector, z3, yices2, bitwuzla, abc, nextpnr
# Replaces: apt yosys + source-built sby + apt boolector/z3
# -----------------------------------------------------------------------------
RUN OSS_DATE=$(echo "${OSS_CAD_SUITE_TAG}" | tr -d '-') && \
    ARCH=$(dpkg --print-architecture) && \
    case "$ARCH" in \
      amd64) OSS_ARCH="linux-x64" ;; \
      arm64) OSS_ARCH="linux-arm64" ;; \
      *) echo "Unsupported OSS CAD Suite architecture: $ARCH" >&2; exit 1 ;; \
    esac && \
    cd /tmp && \
    curl -fsSL "https://github.com/YosysHQ/oss-cad-suite-build/releases/download/${OSS_CAD_SUITE_TAG}/oss-cad-suite-${OSS_ARCH}-${OSS_DATE}.tgz" -o oss-cad-suite.tgz && \
    tar xzf oss-cad-suite.tgz -C /opt && \
    rm -f /tmp/oss-cad-suite.tgz

# OSS CAD Suite PATH (appended AFTER /usr/local/bin so custom-built verilator/slang take priority)
ENV PATH="${PATH}:/opt/oss-cad-suite/bin"

# -----------------------------------------------------------------------------
# Verible (style lint + formatting) — prebuilt binary from GitHub
# -----------------------------------------------------------------------------
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then VERIBLE_ARCH="x86_64"; else VERIBLE_ARCH="$ARCH"; fi && \
    VERIBLE_URL=$(curl -s https://api.github.com/repos/chipsalliance/verible/releases/latest \
      | python3 -c "import sys,json; r=json.load(sys.stdin); print([a['browser_download_url'] for a in r['assets'] if 'linux' in a['name'].lower() and '${VERIBLE_ARCH}' in a['name'].lower()][0] if [a for a in r['assets'] if 'linux' in a['name'].lower() and '${VERIBLE_ARCH}' in a['name'].lower()] else '')") && \
    if [ -n "$VERIBLE_URL" ]; then \
      cd /tmp && \
      curl -fsSL "$VERIBLE_URL" -o verible.tar.gz && \
      mkdir -p /opt/verible && \
      tar xzf verible.tar.gz -C /opt/verible --strip-components=1 && \
      ln -sf /opt/verible/bin/verible-verilog-lint /usr/local/bin/ && \
      ln -sf /opt/verible/bin/verible-verilog-format /usr/local/bin/ && \
      ln -sf /opt/verible/bin/verible-verilog-syntax /usr/local/bin/ && \
      rm -f /tmp/verible.tar.gz; \
    else \
      echo "WARNING: Verible not available for $ARCH, skipping"; \
    fi

# -----------------------------------------------------------------------------
# slang (IEEE 1800 semantic lint) — build from source
# -----------------------------------------------------------------------------
RUN cd /tmp && \
    git clone --depth 1 --branch ${SLANG_VERSION} https://github.com/MikePopoloski/slang.git && \
    cd slang && \
    cmake -B build -DCMAKE_INSTALL_PREFIX=/usr/local -DCMAKE_BUILD_TYPE=Release -G Ninja && \
    cmake --build build -j$(nproc) && \
    cmake --install build && \
    rm -rf /tmp/slang

# -----------------------------------------------------------------------------
# svlens (structural analysis: CDC + connectivity + metrics) — build from source
# https://github.com/babyworm/svlens
# Depends on slang (installed above)
# -----------------------------------------------------------------------------
RUN cd /tmp && \
    git clone --depth 1 --branch ${SVLENS_VERSION} https://github.com/babyworm/svlens.git && \
    cd svlens && \
    cmake -B build -DCMAKE_INSTALL_PREFIX=/usr/local -DCMAKE_BUILD_TYPE=Release -G Ninja && \
    cmake --build build -j$(nproc) && \
    cmake --install build && \
    rm -rf /tmp/svlens

# -----------------------------------------------------------------------------
# slang-server (SystemVerilog LSP) — build from source
# https://github.com/hudson-trading/slang-server
# -----------------------------------------------------------------------------
RUN cd /tmp && \
    git clone --depth 1 https://github.com/hudson-trading/slang-server.git && \
    cd slang-server && \
    git submodule update --init --recursive && \
    cmake -B build -DCMAKE_BUILD_TYPE=Release -G Ninja && \
    cmake --build build -j$(nproc) --target slang_server && \
    cp build/bin/slang-server /usr/local/bin/ && \
    rm -rf /tmp/slang-server

# -----------------------------------------------------------------------------
# SystemC / TLM-2.0 (reference model + BFM) — build from Accellera source
# -----------------------------------------------------------------------------
RUN cd /tmp && \
    git clone --depth 1 --branch ${SYSTEMC_VERSION} https://github.com/accellera-official/systemc.git && \
    cd systemc && \
    cmake -B build \
      -DCMAKE_INSTALL_PREFIX=/usr/local \
      -DCMAKE_BUILD_TYPE=Release \
      -DCMAKE_CXX_STANDARD=17 \
      -G Ninja && \
    cmake --build build -j$(nproc) && \
    cmake --install build && \
    rm -rf /tmp/systemc

ENV SYSTEMC_HOME=/usr/local

# -----------------------------------------------------------------------------
# (Yosys + SymbiYosys + solvers are provided by OSS CAD Suite above)
# -----------------------------------------------------------------------------

# -----------------------------------------------------------------------------
# GTKWave (waveform viewer)
# -----------------------------------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    gtkwave \
    && rm -rf /var/lib/apt/lists/*

# -----------------------------------------------------------------------------
# Python EDA packages (cocotb + extensions)
# -----------------------------------------------------------------------------
RUN pip3 install --break-system-packages --no-cache-dir \
    cocotb \
    cocotb-bus \
    cocotbext-axi \
    cocotb-coverage \
    pytest \
    pytest-xdist \
    numpy

# -----------------------------------------------------------------------------
# Verification: required failures stop the build; optional failures are reported
# -----------------------------------------------------------------------------
RUN set -eu; \
    check_required() { \
      check_name="$1"; shift; \
      if check_output="$("$@" 2>&1)"; then \
        printf '[required] %s: ' "$check_name"; \
        printf '%s\n' "$check_output" | sed -n '1p'; \
      else \
        check_rc=$?; \
        printf '[required] %s failed (rc=%s): ' "$check_name" "$check_rc" >&2; \
        printf '%s\n' "$check_output" | sed -n '1p' >&2; \
        return "$check_rc"; \
      fi; \
    }; \
    check_optional() { \
      check_name="$1"; shift; \
      if check_output="$("$@" 2>&1)"; then \
        printf '[optional] %s: ' "$check_name"; \
        printf '%s\n' "$check_output" | sed -n '1p'; \
      else \
        check_rc=$?; \
        printf '[optional] %s unavailable (rc=%s)\n' "$check_name" "$check_rc"; \
      fi; \
    }; \
    echo "=== RTL EDA Toolchain ==="; \
    check_required verilator verilator --version; \
    check_required iverilog iverilog -V; \
    check_required yosys yosys --version; \
    check_required sby sby --help; \
    check_required slang slang --version; \
    check_required svlens svlens --version; \
    check_required slang-server slang-server --version; \
    check_required cocotb python3 -c "import cocotb; print(f'cocotb {cocotb.__version__}')"; \
    check_required SystemC test -f /usr/local/include/systemc.h; \
    check_required g++ g++ --version; \
    check_optional verible-verilog-lint verible-verilog-lint --version; \
    check_optional gtkwave gtkwave --version; \
    echo "=== All required tools ready ==="

# -----------------------------------------------------------------------------
# Workspace
# -----------------------------------------------------------------------------
WORKDIR /workspace

CMD ["/bin/bash"]
