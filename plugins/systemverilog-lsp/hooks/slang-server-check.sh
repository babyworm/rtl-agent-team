#!/bin/sh
# SessionStart hook for the systemverilog-lsp plugin.
# Advises the session to install slang-server when the LSP backend is missing.

INPUT=$(cat)
CWD=$(printf '%s' "$INPUT" | sed -n 's/.*"cwd"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
[ -z "$CWD" ] && CWD="$(pwd)"

if command -v slang-server >/dev/null 2>&1; then
  exit 0
fi

LOCAL_BIN="${HOME}/.local/bin/slang-server"
if [ -x "$LOCAL_BIN" ]; then
  printf '{"hookSpecificOutput":{"additionalContext":"systemverilog-lsp: slang-server is installed at %s but is not on PATH. Add `export PATH=\\"$HOME/.local/bin:$PATH\\"` to your shell profile, restart the session, or ask me to verify the local LSP install."}}' "$LOCAL_BIN"
  exit 0
fi

printf '{"hookSpecificOutput":{"additionalContext":"systemverilog-lsp: slang-server is not installed, so SystemVerilog LSP features (diagnostics, hover, go-to-definition) are unavailable. If you want, I can install it now. Choose one: `local` (recommended, installs to ~/.local/bin), `global` (installs system-wide and may require sudo), or `skip`. For local install I will use the plugin helper at `scripts/install-slang-server.sh`."}}'
