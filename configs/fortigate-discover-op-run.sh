#!/usr/bin/env bash
# Run read-only FortiGate discovery with 1Password-injected API credentials.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${ROOT}/.venv/bin/python"
DISCOVER="${ROOT}/configs/fortigate-api-discover.py"
TOKEN_REF="${FORTIOS_ACCESS_TOKEN:-op://d3HLPRV/FORTIOS_ACCESS_TOKEN/credential}"

if ! command -v op >/dev/null 2>&1; then
  echo "ERROR: 1Password CLI (op) is not installed." >&2
  exit 1
fi

export FORTIGATE_HOST="${FORTIGATE_HOST:-https://10.99.99.2:7443}"

resolve_token() {
  local ref="$1"
  if [[ "$ref" != op://* ]]; then
    printf '%s' "$ref"
    return 0
  fi
  op read "$ref"
}

authenticated=0
if op whoami >/dev/null 2>&1; then
  authenticated=1
elif op vault list >/dev/null 2>&1; then
  authenticated=1
elif [[ -n "${OP_SERVICE_ACCOUNT_TOKEN:-}" ]]; then
  authenticated=1
fi

if [[ "$authenticated" -eq 0 ]]; then
  echo "ERROR: 1Password is not authenticated in this shell." >&2
  echo "Run: eval \"\$(op signin --account my)\"" >&2
  echo "Or: export OP_SERVICE_ACCOUNT_TOKEN='<service-account-token>'" >&2
  exit 1
fi

if [[ "${FORTIOS_ACCESS_TOKEN:-}" == op://* ]] || [[ -z "${FORTIOS_ACCESS_TOKEN:-}" ]]; then
  export FORTIOS_ACCESS_TOKEN="$(resolve_token "$TOKEN_REF")"
fi

exec "$PYTHON" "$DISCOVER"
