#!/usr/bin/env bash
set -euo pipefail

# Proxmox VE SDN - VLAN Zone + VNets Safe Candidate Script
#
# Default mode is read-only planning:
#   ./proxmox-sdn-pvesh.sh
#   ./proxmox-sdn-pvesh.sh discover
#   ./proxmox-sdn-pvesh.sh plan
#
# Apply mode requires an explicit confirmation environment variable:
#   CONFIRM_PROXMOX_SDN_APPLY=yes ./proxmox-sdn-pvesh.sh apply
#
# Applying the cluster SDN config is a separate gate:
#   APPLY_PROXMOX_SDN=yes CONFIRM_PROXMOX_SDN_APPLY=yes ./proxmox-sdn-pvesh.sh apply

MODE="${1:-plan}"
ZONE="ztrunk"
BRIDGE="vmbr0"
NODES="pve01,pve02,pve03"

VNETS=(
  "vmgmt:10:10.10.10.0/24:10.10.10.2"
  "vstore:20:10.20.20.0/24:10.20.20.2"
  "vsvc:30:10.10.30.0/24:10.10.30.2"
  "vapps:40:10.10.40.0/24:10.10.40.2"
  "vlab:50:10.10.50.0/24:10.10.50.2"
  "vdmz:60:10.10.60.0/24:10.10.60.2"
)

usage() {
  cat <<'EOF'
Usage: ./proxmox-sdn-pvesh.sh [discover|plan|apply|validate]

discover  Run read-only discovery commands on a Proxmox node.
plan      Print the target pvesh changes without mutating anything.
apply     Create only missing SDN objects. Requires CONFIRM_PROXMOX_SDN_APPLY=yes.
validate  Run post-change validation commands.

This script intentionally does not create vinfra/VLAN 99.
EOF
}

print_cmd() {
  printf '  '
  printf '%q ' "$@"
  printf '\n'
}

require_apply_confirmation() {
  if [[ "${CONFIRM_PROXMOX_SDN_APPLY:-}" != "yes" ]]; then
    echo "Refusing to apply: set CONFIRM_PROXMOX_SDN_APPLY=yes after reviewing discovery and diff output." >&2
    exit 1
  fi
  if [[ "$(id -u)" -ne 0 ]]; then
    echo "Refusing to apply: run as root on a Proxmox cluster node." >&2
    exit 1
  fi
  command -v pvesh >/dev/null 2>&1 || {
    echo "Refusing to apply: pvesh was not found." >&2
    exit 1
  }
}

discover() {
  echo "# Proxmox read-only discovery"
  hostname || true
  command -v pveversion >/dev/null 2>&1 && pveversion || true
  command -v pvesh >/dev/null 2>&1 && pvesh get /nodes || true
  command -v pvesh >/dev/null 2>&1 && pvesh get /cluster/sdn || true
  command -v pvesh >/dev/null 2>&1 && pvesh get /cluster/sdn/zones || true
  command -v pvesh >/dev/null 2>&1 && pvesh get /cluster/sdn/vnets || true
  command -v pvesh >/dev/null 2>&1 && pvesh get /cluster/sdn/subnets || true
  grep -n "vmbr0\|bridge-vlan-aware\|bridge-vids" /etc/network/interfaces || true
  command -v bridge >/dev/null 2>&1 && bridge vlan show || true
}

plan() {
  echo "# Candidate Proxmox SDN changes"
  echo "# Review current SDN state first. These commands are not executed in plan mode."
  print_cmd pvesh create /cluster/sdn/zones --zone "$ZONE" --type vlan --bridge "$BRIDGE" --nodes "$NODES"

  for item in "${VNETS[@]}"; do
    IFS=":" read -r vnet tag subnet gateway <<<"$item"
    print_cmd pvesh create /cluster/sdn/vnets --vnet "$vnet" --zone "$ZONE" --tag "$tag"
    print_cmd pvesh create "/cluster/sdn/vnets/${vnet}/subnets" --subnet "$subnet" --gateway "$gateway"
  done

  echo
  echo "# SDN apply gate, run only after diff review:"
  print_cmd pvesh set /cluster/sdn
}

path_exists() {
  pvesh get "$1" >/dev/null 2>&1
}

subnet_exists() {
  local vnet="$1"
  local subnet="$2"
  pvesh get "/cluster/sdn/vnets/${vnet}/subnets" --output-format json 2>/dev/null | grep -F "$subnet" >/dev/null 2>&1
}

apply() {
  require_apply_confirmation

  if ! grep -q "iface ${BRIDGE} " /etc/network/interfaces; then
    echo "Refusing to apply: ${BRIDGE} was not found in /etc/network/interfaces." >&2
    exit 1
  fi
  if ! grep -q "bridge-vlan-aware yes" /etc/network/interfaces; then
    echo "Refusing to apply: ${BRIDGE} must be VLAN-aware before SDN VNets are applied." >&2
    exit 1
  fi

  echo "# Creating missing Proxmox SDN objects"
  if path_exists "/cluster/sdn/zones/${ZONE}"; then
    echo "Zone ${ZONE} already exists; leaving it unchanged."
  else
    pvesh create /cluster/sdn/zones --zone "$ZONE" --type vlan --bridge "$BRIDGE" --nodes "$NODES"
  fi

  for item in "${VNETS[@]}"; do
    IFS=":" read -r vnet tag subnet gateway <<<"$item"

    if path_exists "/cluster/sdn/vnets/${vnet}"; then
      echo "VNet ${vnet} already exists; leaving it unchanged."
    else
      pvesh create /cluster/sdn/vnets --vnet "$vnet" --zone "$ZONE" --tag "$tag"
    fi

    if subnet_exists "$vnet" "$subnet"; then
      echo "Subnet ${subnet} for ${vnet} already exists; leaving it unchanged."
    else
      pvesh create "/cluster/sdn/vnets/${vnet}/subnets" --subnet "$subnet" --gateway "$gateway"
    fi
  done

  if [[ "${APPLY_PROXMOX_SDN:-}" == "yes" ]]; then
    echo "# Applying SDN configuration cluster-wide"
    pvesh set /cluster/sdn
  else
    echo "# Created missing objects only. Review them, then apply with:"
    echo "APPLY_PROXMOX_SDN=yes CONFIRM_PROXMOX_SDN_APPLY=yes ./proxmox-sdn-pvesh.sh apply"
  fi
}

validate() {
  echo "# Proxmox validation"
  pvesh get /cluster/sdn
  pvesh get /cluster/sdn/zones
  pvesh get /cluster/sdn/vnets
  ip -br link | grep -E 'vmgmt|vstore|vsvc|vapps|vlab|vdmz' || true
  bridge vlan show
}

case "$MODE" in
  discover) discover ;;
  plan) plan ;;
  apply) apply ;;
  validate) validate ;;
  -h|--help|help) usage ;;
  *)
    usage >&2
    exit 2
    ;;
esac
