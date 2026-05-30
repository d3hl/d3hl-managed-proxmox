#!/usr/bin/env bash
# Run C9300 verification/save with 1Password-injected SSH credentials.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${ROOT}/.venv/bin/python"
VERIFY="${ROOT}/configs/cisco-c9300-verify.py"

if ! command -v op >/dev/null 2>&1; then
  echo "ERROR: 1Password CLI (op) is not installed." >&2
  exit 1
fi

export CISCO_HOST="${CISCO_HOST:-op://d3HLPRV/C9300/IP}"
export CISCO_USERNAME="${CISCO_USERNAME:-op://d3HLPRV/C9300/username}"
export CISCO_PASSWORD="${CISCO_PASSWORD:-op://d3HLPRV/C9300/password}"

exec op run -- "$PYTHON" "$VERIFY" "$@"
