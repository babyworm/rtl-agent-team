#!/usr/bin/env bash
# systemverilog-lsp helper: install slang-server from upstream source.

set -euo pipefail

MODE="local"
CMD="install"
INSTALL_PREFIX_LOCAL="${HOME}/.local"
INSTALL_PREFIX_GLOBAL="/usr/local"
SRC_DIR="${HOME}/.local/src/slang-server"
REPO_URL="https://github.com/hudson-trading/slang-server.git"
MIN_CMAKE_VERSION="3.20"
MIN_GCC_MAJOR="11"

usage() {
  cat <<'EOF'
Usage:
  install-slang-server.sh install [--mode local|global|skip]
  install-slang-server.sh check
  install-slang-server.sh help

Modes:
  local   Build from source and install under ~/.local/bin (recommended)
  global  Build from source and install under /usr/local/bin (may require sudo)
  skip    Do nothing and exit successfully
EOF
}

version_gte() {
  printf '%s\n%s' "$2" "$1" | sort -V -C
}

have() {
  command -v "$1" >/dev/null 2>&1
}

parse_args() {
  if [ $# -gt 0 ]; then
    CMD="$1"
    shift
  fi

  while [ $# -gt 0 ]; do
    case "$1" in
      --mode)
        MODE="${2:-}"
        shift 2
        ;;
      -h|--help|help)
        CMD="help"
        shift
        ;;
      *)
        echo "Unknown argument: $1" >&2
        usage
        exit 1
        ;;
    esac
  done
}

check_prereqs() {
  local ok=1

  for bin in git cmake; do
    if ! have "$bin"; then
      echo "Missing prerequisite: $bin" >&2
      ok=0
    fi
  done

  if have cmake; then
    local cmake_ver
    cmake_ver="$(cmake --version | awk 'NR==1{print $3}')"
    if ! version_gte "$cmake_ver" "$MIN_CMAKE_VERSION"; then
      echo "cmake $cmake_ver is too old (need >= $MIN_CMAKE_VERSION)" >&2
      ok=0
    fi
  fi

  if have g++; then
    local gcc_major
    gcc_major="$(g++ -dumpversion | cut -d. -f1)"
    if [ "${gcc_major:-0}" -lt "$MIN_GCC_MAJOR" ]; then
      echo "g++ $gcc_major is too old (need >= $MIN_GCC_MAJOR for C++20)" >&2
      ok=0
    fi
  elif ! have clang++; then
    echo "Missing prerequisite: g++ >= $MIN_GCC_MAJOR or clang++" >&2
    ok=0
  fi

  if [ "$ok" -ne 1 ]; then
    cat <<'EOF' >&2
Install prerequisites first:
  Ubuntu/Debian: sudo apt install git cmake g++ ninja-build
  Fedora:        sudo dnf install git cmake gcc-c++ ninja-build
  macOS:         brew install cmake ninja
EOF
    exit 1
  fi
}

clone_or_update() {
  mkdir -p "$(dirname "$SRC_DIR")"
  if [ -d "$SRC_DIR/.git" ]; then
    git -C "$SRC_DIR" fetch --tags origin
    git -C "$SRC_DIR" checkout main
    git -C "$SRC_DIR" pull --ff-only origin main
    git -C "$SRC_DIR" submodule update --init --recursive
  else
    git clone "$REPO_URL" "$SRC_DIR"
    git -C "$SRC_DIR" submodule update --init --recursive
  fi
}

build_and_install() {
  local prefix="$1"
  local build_dir="$SRC_DIR/build"
  local generator_args=()

  if have ninja; then
    generator_args=(-G Ninja)
  fi

  cmake -S "$SRC_DIR" -B "$build_dir" "${generator_args[@]}" \
    -DCMAKE_BUILD_TYPE=Release \
    -DCMAKE_INSTALL_PREFIX="$prefix"
  cmake --build "$build_dir" -j"$(nproc 2>/dev/null || echo 4)" --target slang_server

  if [ "$MODE" = "global" ]; then
    echo "Global install selected. You may be prompted for sudo."
    sudo cmake --install "$build_dir"
  else
    cmake --install "$build_dir"
  fi
}

verify_install() {
  if have slang-server; then
    echo "slang-server ready: $(command -v slang-server)"
    slang-server --version 2>&1 | head -1 || true
    return 0
  fi

  if [ -x "${HOME}/.local/bin/slang-server" ]; then
    echo "slang-server installed at ${HOME}/.local/bin/slang-server"
    "${HOME}/.local/bin/slang-server" --version 2>&1 | head -1 || true
    echo 'Add `export PATH="$HOME/.local/bin:$PATH"` to your shell profile if needed.'
    return 0
  fi

  echo "slang-server installation verification failed" >&2
  return 1
}

check_status() {
  if have slang-server; then
    echo "slang-server: $(command -v slang-server)"
    slang-server --version 2>&1 | head -1 || true
  elif [ -x "${HOME}/.local/bin/slang-server" ]; then
    echo "slang-server exists at ${HOME}/.local/bin/slang-server but PATH is missing ~/.local/bin"
  else
    echo "slang-server: not installed"
  fi
}

main() {
  parse_args "$@"

  case "$CMD" in
    install)
      case "$MODE" in
        skip)
          echo "Skipping slang-server installation."
          exit 0
          ;;
        local|global)
          ;;
        *)
          echo "Invalid mode: $MODE" >&2
          usage
          exit 1
          ;;
      esac
      check_prereqs
      clone_or_update
      if [ "$MODE" = "global" ]; then
        build_and_install "$INSTALL_PREFIX_GLOBAL"
      else
        mkdir -p "${INSTALL_PREFIX_LOCAL}/bin"
        build_and_install "$INSTALL_PREFIX_LOCAL"
      fi
      verify_install
      ;;
    check)
      check_status
      ;;
    help|-h|--help)
      usage
      ;;
    *)
      echo "Unknown command: $CMD" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
