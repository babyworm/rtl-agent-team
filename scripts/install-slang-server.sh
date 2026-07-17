#!/usr/bin/env bash
# slang-server (hudson-trading) Build & Install Script
# Builds the SystemVerilog LSP from source
# https://github.com/hudson-trading/slang-server

set -euo pipefail

INSTALL_DIR="${HOME}/.local/bin"
BUILD_DIR="${HOME}/.local/src/slang-server"
REPO_URL="https://github.com/hudson-trading/slang-server.git"
MIN_CMAKE_VERSION="3.20"
MIN_GCC_VERSION="11"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warning() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error()   { echo -e "${RED}[ERROR]${NC} $1"; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

# Compare semver: returns 0 if $1 >= $2
version_gte() {
    awk -v current="$1" -v minimum="$2" 'BEGIN {
        current_count = split(current, current_parts, ".")
        minimum_count = split(minimum, minimum_parts, ".")
        part_count = current_count > minimum_count ? current_count : minimum_count
        for (part_index = 1; part_index <= part_count; part_index++) {
            current_part = part_index <= current_count ? current_parts[part_index] + 0 : 0
            minimum_part = part_index <= minimum_count ? minimum_parts[part_index] + 0 : 0
            if (current_part > minimum_part) exit 0
            if (current_part < minimum_part) exit 1
        }
        exit 0
    }'
}

check_prerequisites() {
    log_info "Checking build prerequisites..."
    local ok=true

    # git
    if command_exists git; then
        log_success "git: $(git --version)"
    else
        log_error "git not found"
        ok=false
    fi

    # cmake
    if command_exists cmake; then
        local cmake_ver
        cmake_ver="$(cmake --version | sed -n '1s/[^0-9]*\([0-9][0-9.]*\).*/\1/p')"
        if version_gte "$cmake_ver" "$MIN_CMAKE_VERSION"; then
            log_success "cmake: $cmake_ver (>= $MIN_CMAKE_VERSION)"
        else
            log_error "cmake $cmake_ver too old (need >= $MIN_CMAKE_VERSION)"
            ok=false
        fi
    else
        log_error "cmake not found"
        ok=false
    fi

    # C++20 compiler
    if command_exists g++; then
        local gcc_ver
        gcc_ver="$(g++ -dumpversion | cut -d. -f1)"
        if [[ "$gcc_ver" -ge "$MIN_GCC_VERSION" ]]; then
            log_success "g++: $(g++ --version | sed -n '1p') (>= GCC $MIN_GCC_VERSION)"
        else
            log_error "g++ $gcc_ver too old (need >= GCC $MIN_GCC_VERSION for C++20)"
            ok=false
        fi
    elif command_exists clang++; then
        log_success "clang++: $(clang++ --version | sed -n '1p')"
    else
        log_error "No C++20 compiler found (need g++ >= 11 or clang++ >= 17)"
        ok=false
    fi

    # ninja (optional but faster)
    if command_exists ninja; then
        log_success "ninja: $(ninja --version) (will use for faster builds)"
    else
        log_warning "ninja not found (will use make, install ninja-build for faster builds)"
    fi

    if [[ "$ok" != true ]]; then
        echo ""
        log_error "Missing prerequisites. Install them first:"
        echo "  Ubuntu/Debian: sudo apt install git cmake g++ ninja-build"
        echo "  Fedora:        sudo dnf install git cmake gcc-c++ ninja-build"
        echo "  Arch:          sudo pacman -S git cmake gcc ninja"
        echo "  macOS:         brew install cmake ninja"
        return 1
    fi

    return 0
}

clone_or_update() {
    if [[ -d "$BUILD_DIR/.git" ]]; then
        log_info "Updating existing source at $BUILD_DIR..."
        cd "$BUILD_DIR"
        git fetch origin
        git checkout main
        git pull origin main
        git submodule update --init --recursive
    else
        log_info "Cloning slang-server to $BUILD_DIR..."
        mkdir -p "$(dirname "$BUILD_DIR")"
        git clone "$REPO_URL" "$BUILD_DIR"
        cd "$BUILD_DIR"
        git submodule update --init --recursive
    fi
    log_success "Source ready at $BUILD_DIR"
}

build() {
    cd "$BUILD_DIR"
    log_info "Configuring with CMake..."

    local cmake_args=("-B" "build" "-DCMAKE_BUILD_TYPE=Release")

    # Use ninja if available
    if command_exists ninja; then
        cmake_args+=("-G" "Ninja")
    fi

    # Arch Linux workaround: use vendored fmt
    if [[ -f /etc/arch-release ]]; then
        cmake_args+=("-DCMAKE_DISABLE_FIND_PACKAGE_fmt=TRUE")
        log_info "Arch Linux detected: using vendored fmt"
    fi

    cmake "${cmake_args[@]}"

    log_info "Building slang-server (this may take a few minutes)..."
    local nproc
    nproc="$(nproc 2>/dev/null || sysctl -n hw.ncpu 2>/dev/null || echo 4)"
    cmake --build build -j"$nproc" --target slang_server

    log_success "Build complete"
}

install_binary() {
    cd "$BUILD_DIR"
    mkdir -p "$INSTALL_DIR"

    # Find the built binary
    local binary
    binary="$(find build -name 'slang-server' -type f -executable 2>/dev/null | sed -n '1p')"
    if [[ -z "$binary" ]]; then
        # Try alternate name
        binary="$(find build -name 'slang_server' -type f -executable 2>/dev/null | sed -n '1p')"
    fi

    if [[ -z "$binary" ]]; then
        log_error "Built binary not found in build/"
        return 1
    fi

    cp "$binary" "$INSTALL_DIR/slang-server"
    chmod +x "$INSTALL_DIR/slang-server"
    log_success "Installed to $INSTALL_DIR/slang-server"
}

verify_install() {
    echo ""
    if command_exists slang-server; then
        log_success "slang-server is available: $(which slang-server)"
        slang-server --version 2>&1 || true
    elif [[ -x "$INSTALL_DIR/slang-server" ]]; then
        log_success "slang-server installed at $INSTALL_DIR/slang-server"
        "$INSTALL_DIR/slang-server" --version 2>&1 || true
        if [[ ":$PATH:" != *":$INSTALL_DIR:"* ]]; then
            echo ""
            log_warning "$INSTALL_DIR is not in PATH. Add to your shell profile:"
            echo ""
            echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
            echo ""
        fi
    else
        log_error "Installation verification failed"
        return 1
    fi
}

check_status() {
    echo ""
    echo "======================================"
    echo "  SystemVerilog LSP Status"
    echo "======================================"
    echo ""

    for cmd in slang-server svls verible-verilog-ls slang; do
        if command_exists "$cmd"; then
            log_success "$cmd: $(which "$cmd")"
            "$cmd" --version 2>&1 | sed -n '1p' || true
        else
            log_warning "$cmd: not found"
        fi
        echo ""
    done
}

uninstall() {
    if [[ -f "$INSTALL_DIR/slang-server" ]]; then
        rm -f "$INSTALL_DIR/slang-server"
        log_success "Removed $INSTALL_DIR/slang-server"
    else
        log_warning "slang-server not found in $INSTALL_DIR"
    fi

    if [[ -d "$BUILD_DIR" ]]; then
        read -r -p "Remove source directory $BUILD_DIR? [y/N]: " confirm
        if [[ "$confirm" =~ ^[Yy] ]]; then
            rm -rf "$BUILD_DIR"
            log_success "Removed $BUILD_DIR"
        fi
    fi
}

usage() {
    echo "Usage: $0 [command]"
    echo ""
    echo "Commands:"
    echo "  install     Build and install slang-server (default)"
    echo "  check       Check installed SV language servers"
    echo "  update      Pull latest source and rebuild"
    echo "  uninstall   Remove slang-server binary and source"
    echo "  help        Show this help"
    echo ""
    echo "Options:"
    echo "  INSTALL_DIR=<path>  Override install directory (default: ~/.local/bin)"
    echo "  BUILD_DIR=<path>    Override build directory (default: ~/.local/src/slang-server)"
}

main() {
    local cmd="${1:-install}"

    case "$cmd" in
        install|build)
            echo "======================================"
            echo "  slang-server Build & Install"
            echo "  https://github.com/hudson-trading/slang-server"
            echo "======================================"
            echo ""
            check_prerequisites
            clone_or_update
            build
            install_binary
            verify_install
            echo ""
            log_success "slang-server installation complete!"
            ;;
        update)
            log_info "Updating slang-server..."
            clone_or_update
            build
            install_binary
            verify_install
            log_success "Update complete!"
            ;;
        check|status)
            check_status
            ;;
        uninstall|remove)
            uninstall
            ;;
        help|-h|--help)
            usage
            ;;
        *)
            log_error "Unknown command: $cmd"
            usage
            exit 1
            ;;
    esac
}

main "$@"
