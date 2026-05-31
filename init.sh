#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

# Replace these commands with the correct commands for your repository.
PYTHON_BIN=""
for candidate in .venv/bin/python python python.exe python3; do
  if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -m pip --version >/dev/null 2>&1; then
    PYTHON_BIN="$candidate"
    break
  fi
done

if [ -z "$PYTHON_BIN" ] && command -v python3 >/dev/null 2>&1; then
  python3 -m venv .venv
  if .venv/bin/python -m pip --version >/dev/null 2>&1; then
    PYTHON_BIN=".venv/bin/python"
  fi
fi

if [ -z "$PYTHON_BIN" ]; then
  echo "Python with pip is required but was not found in PATH." >&2
  exit 1
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
