#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
TOKEN_REF="${FORTIOS_ACCESS_TOKEN:-op://d3HLPRV/FORTIOS_ACCESS_TOKEN/credential}"

export FORTIGATE_HOST="${FORTIGATE_HOST:-https://10.99.99.2:7443}"

if [[ "${FORTIOS_ACCESS_TOKEN:-}" == op://* ]] || [[ -z "${FORTIOS_ACCESS_TOKEN:-}" ]]; then
  export FORTIOS_ACCESS_TOKEN="$(op read "$TOKEN_REF")"
fi

exec "$ROOT/.venv/bin/python" "$ROOT/configs/fortigate-api-persist-save.py"
