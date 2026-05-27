#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Replace these commands with the correct commands for your repository.
PYTHON_BIN="python"
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  if command -v python.exe >/dev/null 2>&1; then
    PYTHON_BIN="python.exe"
  else
    echo "Python is required but was not found in PATH." >&2
    exit 1
  fi
fi

INSTALL_CMD=("$PYTHON_BIN" -m pip install -r mcp/requirements.txt)
VERIFY_CMD=("$PYTHON_BIN" -m json.tool data/network-plan.json)
START_CMD=("$PYTHON_BIN" app.py)

echo "==> Working directory: $PWD"
echo "==> Syncing dependencies"
"${INSTALL_CMD[@]}"

echo "==> Running baseline verification"
"${VERIFY_CMD[@]}"

echo "==> Startup command"
printf '    %q' "${START_CMD[@]}"
printf '\n'

if [ "${RUN_START_COMMAND:-0}" = "1" ]; then
  echo "==> Starting the app"
  exec "${START_CMD[@]}"
fi

echo "Set RUN_START_COMMAND=1 if you want init.sh to launch the app directly."
