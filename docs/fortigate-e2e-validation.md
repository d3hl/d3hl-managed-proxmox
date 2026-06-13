# FortiGate E2E Validation Matrix

This document records end-to-end connectivity evidence for FortiGate routed VLANs
(30, 40, 50, 60) and VLAN 10 management reachability.

## Scope

| VLAN | VNet | Subnet | FortiGate gateway | Interface |
|---:|---|---|---|---|
| 10 | vmgmt | 10.10.10.0/24 | 10.10.10.2 | hlvl |
| 30 | vsvc | 10.10.30.0/24 | 10.10.30.2 | vsvc |
| 40 | vapps | 10.10.40.0/24 | 10.10.40.2 | vapps |
| 50 | vlab | 10.10.50.0/24 | 10.10.50.2 | vlab |
| 60 | vdmz | 10.10.60.0/24 | 10.10.60.2 | vdmz |

VLAN 20 (vstore) is storage-side only and is not routed on the FortiGate.

## Validation matrix

| Tier | Test | vsvc (30) | vapps (40) | vlab (50) | vdmz (60) | VLAN 10 mgmt |
|---|---|---|---|---|---|---|
| L3 gateway | Workstation → FortiGate `.2` | OK 2026-06-01 | OK 2026-06-01 | OK 2026-05-30 / 2026-06-01 | OK 2026-06-01 | OK 2026-06-01 (`10.10.10.2`) |
| L3 reverse | C9300 SVI → FortiGate gateway | — | — | OK 2026-05-30 (`10.10.50.2`) | — | OK 2026-05-31 (`ping 10.10.10.2 source vlan10`) |
| L3 C9300 SVI | Workstation → `10.10.10.1` | — | — | — | — | OK 2026-06-01 |
| FortiGate → C9300 | `execute ping 10.10.10.1` from `10.10.10.2` | — | — | — | — | N/A via API (404); substitute evidence accepted |
| Proxmox SDN | VNet + gateway in repo | OK | OK | OK | OK | OK (vmgmt) |
| Proxmox OVS trunks | VLAN on node trunks | OK | OK | OK | OK | OK |
| VM / DHCP | Guest lease from FortiGate DHCP | Not tested | Not tested | OK — VM 444 `10.10.50.10` | Not tested | N/A |
| VM reachability | External ping to guest IP | Not tested | Not tested | OK — workstation → `10.10.50.10` 3/3 | Not tested | N/A |
| In-guest gateway ping | QEMU guest agent → `.2` | Not tested | Not tested | Blocked — agent HTTP 501 | Not tested | N/A |

## Evidence references

| Artifact / session | Content |
|---|---|
| Session 021 | VM 444 on `vlab`: DHCP `10.10.50.10`, workstation pings to VM and `10.10.50.2` |
| Session 022 | C9300 `ping 10.10.10.2 source vlan10` OK; C9300 `write memory` |
| Session 023 | FortiGate discover 6/6; repo-live 23/23; persistent save + backup |
| `ansible/artifacts/fortigate-repo-live-verify.json` | 23/23 repo-live match |
| `ansible/artifacts/fortigate-persistent-save.json` | Policy align + backup metadata |
| `ansible/artifacts/proxmox-fortigate-gateway-validation.json` | SDN gateways and OVS trunks |

## VLAN 10 ping substitute (FortiGate → C9300)

FortiGate REST monitor endpoint `/api/v2/monitor/system/ping` returns HTTP 404 on
FortiOS 7.6.6 build 3652 with API token auth. Automation cannot source the ping
from `hlvl` today.

Accepted substitute evidence for `fortigate-001`:

- `hlvl` is up with `10.10.10.2/24` on parent `x2` (live API)
- C9300 `Vlan10` (`10.10.10.1/24`) can ping FortiGate `10.10.10.2` (Session 022)
- Workstation can ping both `10.10.10.1` and `10.10.10.2` on the same `/24` segment

Optional gold standard (manual CLI or SSH):

```text
execute ping-options source 10.10.10.2
execute ping 10.10.10.1
```

## Remaining optional tests

1. Attach a running VM to `vsvc`, `vapps`, or `vdmz` and repeat DHCP + external ping.
2. Enable QEMU guest agent on VM 444 for in-guest `ping 10.10.50.2`.
3. Manual FortiGate CLI ping from `10.10.10.2` to `10.10.10.1` if API limitation is lifted or console access is used.

## Re-run commands

```bash
source ~/.zshrc   # OP_SERVICE_ACCOUNT_TOKEN or op signin
bash configs/fortigate-discover-op-run.sh
bash configs/fortigate-repo-live-verify-op-run.sh
CONFIRM_FORTIGATE_PERSISTENT_SAVE=yes bash configs/fortigate-persist-save-op-run.sh
```

Workstation gateway ping spot-check:

```bash
for ip in 10.10.10.1 10.10.10.2 10.10.30.2 10.10.40.2 10.10.50.2 10.10.60.2; do
  ping -c 2 -W 2 "$ip"
done
```
