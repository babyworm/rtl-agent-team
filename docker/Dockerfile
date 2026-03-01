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
#   docker run -it --rm -v $(pwd):/workspace -w /workspace rtl-eda-tools
#
# Run with GUI (gtkwave):
#   docker run -it --rm -e DISPLAY=$DISPLAY -v /tmp/.X11-unix:/tmp/.X11-unix \
#     -v $(pwd):/workspace -w /workspace rtl-eda-tools
# =============================================================================

FROM ubuntu:24.04 AS base

ARG DEBIAN_FRONTEND=noninteractive
ARG VERILATOR_VERSION=5.024
ARG SLANG_VERSION=v6.0
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
RUN OSS_DATE=$(echo ${OSS_CAD_SUITE_TAG} | tr -d '-') && \
    ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "amd64" ]; then OSS_ARCH="linux-x64"; else OSS_ARCH="linux-arm64"; fi && \
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
# Verification: print all tool versions
# -----------------------------------------------------------------------------
RUN echo "=== RTL EDA Toolchain ===" && \
    verilator --version && \
    verible-verilog-lint --version 2>/dev/null || echo "verible: not available on this arch" && \
    iverilog -V 2>&1 | head -1 && \
    yosys --version && \
    sby --help 2>&1 | head -1 || echo "sby: installed" && \
    echo "OSS CAD Suite: $(ls /opt/oss-cad-suite/ 2>/dev/null && echo 'installed' || echo 'NOT FOUND')" && \
    slang --version 2>&1 | head -1 && \
    slang-server --version 2>&1 | head -1 && \
    python3 -c "import cocotb; print(f'cocotb {cocotb.__version__}')" && \
    python3 -c "import SystemC; print('SystemC: available')" 2>/dev/null || \
      (test -f /usr/local/include/systemc.h && echo "SystemC ${SYSTEMC_VERSION} (SYSTEMC_HOME=$SYSTEMC_HOME)" || echo "SystemC: NOT FOUND") && \
    g++ --version | head -1 && \
    echo "=== All tools ready ==="

# -----------------------------------------------------------------------------
# Workspace
# -----------------------------------------------------------------------------
WORKDIR /workspace

CMD ["/bin/bash"]
