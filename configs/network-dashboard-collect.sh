#!/usr/bin/env bash
# Collect homelab network dashboard snapshot from discovery artifacts.
# Use --live to re-run FortiGate/Cisco/Proxmox discovery before merging.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
PYTHON="${ROOT}/.venv/bin/python"
COLLECT="${ROOT}/configs/network-dashboard-collect.py"

if [[ ! -x "$PYTHON" ]]; then
  PYTHON="python3"
fi

LIVE=0
WRITESIDECAR=0
for arg in "$@"; do
  case "$arg" in
    --live) LIVE=1 ;;
    --write-sidecar) WRITESIDECAR=1 ;;
  esac
done

if [[ "$LIVE" -eq 1 ]]; then
  echo "# Live discovery mode"
  if command -v op >/dev/null 2>&1; then
    op run -- "$PYTHON" "$COLLECT" --live ${WRITESIDECAR:+--write-sidecar}
  else
    echo "WARNING: op not found; running discovery without op run wrapper" >&2
    "$PYTHON" "$COLLECT" --live ${WRITESIDECAR:+--write-sidecar}
  fi
else
  ARGS=()
  [[ "$WRITESIDECAR" -eq 1 ]] && ARGS+=(--write-sidecar)
  "$PYTHON" "$COLLECT" "${ARGS[@]}"
fi
