#!/usr/bin/env bash
# Apply FortiGate address objects, zones, and firewall policies with 1Password creds.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${ROOT}/.venv/bin/python"
APPLY="${ROOT}/configs/fortigate-api-apply-policies.py"
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

if ! op whoami >/dev/null 2>&1 && ! op vault list >/dev/null 2>&1 && [[ -z "${OP_SERVICE_ACCOUNT_TOKEN:-}" ]]; then
  echo "ERROR: 1Password is not authenticated in this shell." >&2
  exit 1
fi

if [[ "${FORTIOS_ACCESS_TOKEN:-}" == op://* ]] || [[ -z "${FORTIOS_ACCESS_TOKEN:-}" ]]; then
  export FORTIOS_ACCESS_TOKEN="$(resolve_token "$TOKEN_REF")"
fi

exec "$PYTHON" "$APPLY"
