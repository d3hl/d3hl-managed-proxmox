#!/usr/bin/env bash
# Create a 1Password service account for homelab agent automation.
#
# Prerequisites:
#   - 1Password CLI installed (dnf install 1password-cli)
#   - Signed-in CLI session: eval "$(op signin)" or op account add --signin
#
# Usage:
#   eval "$(op signin)"
#   CONFIRM_OP_SERVICE_ACCOUNT_CREATE=yes bash configs/setup-1password-service-account.sh
#
# The service account token is printed once. Save it in 1Password immediately.
# Do not commit the token or store it in this repository.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SERVICE_ACCOUNT_NAME="${OP_SERVICE_ACCOUNT_NAME:-d3hl-managed-proxmox-wsl}"
VAULT_SPECS=(
  "d3HL:read_items"
  "d3HLPRV:read_items"
  "AI:read_items"
)

if ! command -v op >/dev/null 2>&1; then
  echo "ERROR: 1Password CLI (op) is not installed." >&2
  echo "Install: sudo dnf install 1password-cli" >&2
  exit 1
fi

echo "==> 1Password CLI: $(op --version)"

if ! op vault list >/dev/null 2>&1; then
  echo "ERROR: Not signed in to 1Password CLI." >&2
  echo "Run: eval \"\$(op signin)\"" >&2
  echo "Or: eval \"\$(op account add --signin)\"" >&2
  exit 1
fi

echo "==> Available vaults:"
op vault list

missing_vaults=()
for spec in "${VAULT_SPECS[@]}"; do
  vault_name="${spec%%:*}"
  if ! op vault get "$vault_name" >/dev/null 2>&1; then
    missing_vaults+=("$vault_name")
  fi
done

if ((${#missing_vaults[@]} > 0)); then
  echo "ERROR: These vaults were not found in the signed-in account:" >&2
  printf '  - %s\n' "${missing_vaults[@]}" >&2
  echo "Fix vault names in configs/setup-1password-service-account.sh if needed." >&2
  exit 1
fi

if [[ "${CONFIRM_OP_SERVICE_ACCOUNT_CREATE:-}" != "yes" ]]; then
  echo "Refusing to create service account without CONFIRM_OP_SERVICE_ACCOUNT_CREATE=yes" >&2
  echo "Planned service account: ${SERVICE_ACCOUNT_NAME}" >&2
  echo "Planned vault access:" >&2
  printf '  - %s\n' "${VAULT_SPECS[@]}" >&2
  exit 1
fi

vault_args=()
for spec in "${VAULT_SPECS[@]}"; do
  vault_args+=(--vault "$spec")
done

echo "==> Creating service account: ${SERVICE_ACCOUNT_NAME}"
token="$(op service-account create "$SERVICE_ACCOUNT_NAME" "${vault_args[@]}" --raw)"

if [[ -z "$token" ]]; then
  echo "ERROR: Service account creation returned an empty token." >&2
  exit 1
fi

OUT_DIR="${ROOT}/ansible/artifacts"
mkdir -p "$OUT_DIR"
meta_file="${OUT_DIR}/op-service-account-created.json"
python3 - <<PY
import json
import time
from pathlib import Path

Path("${meta_file}").write_text(
    json.dumps(
        {
            "created_at_epoch": int(time.time()),
            "service_account_name": "${SERVICE_ACCOUNT_NAME}",
            "vaults": [spec.split(":")[0] for spec in """${VAULT_SPECS[*]}""".split()],
            "token_saved_in_repo": False,
        },
        indent=2,
    ),
    encoding="utf-8",
)
PY

echo "==> Service account created."
echo "Evidence metadata: ansible/artifacts/op-service-account-created.json"
echo
echo "IMPORTANT:"
echo "  1. Save the token below in 1Password (for example item: ${SERVICE_ACCOUNT_NAME})."
echo "  2. Export for automation: export OP_SERVICE_ACCOUNT_TOKEN='<token>'"
echo "  3. Test: op vault list"
echo "  4. Do not commit the token or paste it into repo files."
echo
echo "Service account token (shown once):"
echo "$token"
