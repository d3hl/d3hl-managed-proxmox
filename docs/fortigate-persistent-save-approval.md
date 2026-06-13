# Persistent Save Approval Path

This document records when Cisco and FortiGate running-config changes are approved
for persistent save, and the exact commands to run after approval.

## Preconditions (all must pass)

- [x] FortiGate interfaces: 6/6 repo targets match on parent `x2`
- [x] FortiGate address objects, zones, and Phase B policies applied (15/15 operations OK)
- [x] Codex approved Composer FortiGate running-config policy implementation (Session 019)
- [x] E2E VLAN 50 validation: VM 444 DHCP lease `10.10.50.10` via FortiGate vlab (Session 021)
- [x] Workstation → VM `10.10.50.10` ping 3/3
- [x] Workstation → FortiGate gateway `10.10.50.2` ping 3/3
- [x] Fresh repo-vs-live FortiGate verification passes (`configs/fortigate-repo-live-verify.py`) — 23/23 match after HOMELAB-TO-MGMT-LIMITED service align (2026-06-01)
- [x] User approved persistent save (2026-05-31)
- [x] Persistent save workflow executed with config backup artifact (2026-06-01, Session 023)

## Repo sources of truth

| Domain | File |
|---|---|
| VLAN interfaces | `ansible/group_vars/fortigates.yml` |
| Address objects, zones, policies | `ansible/group_vars/fortigate_policies.yml` |
| Trunk VLAN allowance (C9300 side) | `data/network-plan.json` |
| FortiGate VLAN CLI reference | `configs/fortigate-100f-vlan-cli.conf` |

## Verification before save

```bash
source ~/.zshrc   # OP_SERVICE_ACCOUNT_TOKEN
bash configs/fortigate-discover-op-run.sh
bash configs/fortigate-repo-live-verify-op-run.sh
CONFIRM_FORTIGATE_PERSISTENT_SAVE=yes bash configs/fortigate-persist-save-op-run.sh
```

Expected:
- Interfaces: 6/6 match, parent `x2`
- Trunk VLANs on `x2`: 10, 11, 30, 40, 50, 60, 100 (VLAN 20 absent on FortiGate)
- Address objects: 4/4 match
- Zones: VSVC, VAPPS, VLAB, VDMZ match
- Policies: 7/7 Phase B policies match
- No forbidden VLAN 20 or VLAN 99 interfaces on FortiGate

## FortiGate persistent save (after Codex approval)

FortiGate auto-saves configuration changes in most operating modes. Confirm with:

```text
show system status
get system status
```

If manual backup is required before reboot:

```text
execute backup config tftp <filename> <tftp-server-ip>
```

Or export via API (read-only backup before save):

```bash
# From workstation with API token — backup only, no mutation
FORTIGATE_HOST='https://10.99.99.2:7443' \
FORTIOS_ACCESS_TOKEN="$(op read 'op://d3HLPRV/FORTIOS_ACCESS_TOKEN/credential')" \
  .venv/bin/python configs/fortigate-discover-op-run.sh
```

FortiGate running-config is typically persisted automatically. Verify post-change:

```text
show system interface
show firewall policy
show system zone
```

## Cisco persistent save

Cisco running-config was saved on **2026-05-31** (Session 022) after verification:

- C9300-to-FortiGate trunk `TwentyFiveGigE2/1/2`: VLANs `10,11,30,40,50,60,100`
- C9300 Proxmox trunks `Te2/0/39,41,46`: VLANs `3,10,11,30,40,50,60`
- `ping 10.10.10.2 source vlan10` OK before and after `write memory`

Evidence: `ansible/artifacts/cisco-c9300-verification.json` (Session 022).

Re-verify after future trunk changes:

```cisco
show interfaces trunk
show running-config interface TwentyFiveGigE2/1/2
show running-config interface TenGigabitEthernet2/0/39
show running-config interface TenGigabitEthernet2/0/41
show running-config interface TenGigabitEthernet2/0/46
ping 10.10.10.2 source vlan10
write memory
```

## Rollback (if post-save validation fails)

### FortiGate policies (delete only repo-created objects)

```text
config firewall policy
    delete <policyid-for-DENY-LAB-TO-DMZ>
    delete <policyid-for-DENY-INTERNAL-TO-DMZ>
    delete <policyid-for-MGMT-TO-HOMELAB>
    delete <policyid-for-HOMELAB-TO-MGMT-LIMITED>
    delete <policyid-for-VMSVC-VAPPS-EASTWEST>
    delete <policyid-for-VLAB-TO-VMSVC>
    delete <policyid-for-DMZ-TO-WAN-NAT>
end
config system zone
    delete VSVC
    delete VAPPS
    delete VLAB
    delete VDMZ
end
config firewall address
    delete "vsvc address"
    delete "vapps address"
    delete "vlab address"
    delete "vdmz address"
end
```

Do not delete `hlvl`, `mgt`, `k8s`, `Wifi`, or VLAN interfaces.

### Cisco

Reload unsaved running-config or restore pre-change trunk VLAN lists captured in
`ansible/artifacts/cisco-fortigate-trunk-review.json`.

## Approval record

| Date | Approver | Scope | Persistent save executed? |
|---|---|---|---|
| 2026-05-30 | Codex | FortiGate running-config policy implementation | No — deferred pending E2E |
| 2026-05-30 | — | E2E VLAN 50 validated (Session 021) | No — pending repo-live verify + final Codex sign-off |
| 2026-05-31 | User | FortiGate persistent save approval granted | Approved — execution deferred |
| 2026-05-31 | Session 022 | Cisco `write memory` | Yes |
| 2026-06-01 | Session 023 | FortiGate discover + repo-live 23/23 + persist-save + config backup | Yes |

Session 023 artifacts:

- `ansible/artifacts/fortigate-repo-live-verify.json` — 23/23 match
- `ansible/artifacts/fortigate-persistent-save.json` — policy align + backup metadata
- `ansible/artifacts/fortigate-config-backup.conf` — 384,835 bytes

Policy alignment during save: `HOMELAB-TO-MGMT-LIMITED` (ID 13) service corrected from `ALL` to `DNS`, `NTP`, `PING` to match repo intent.

## Status

FortiGate and Cisco persistent saves are complete for the current homelab SDN design.
`fortigate-001` is marked `passing` in `feature_list.json`.

Optional follow-ups (not blockers):

1. Guest-level E2E on `vsvc`/`vapps`/`vdmz` — see `docs/fortigate-e2e-validation.md`.
2. Manual FortiGate CLI ping `10.10.10.1` from `10.10.10.2` (REST monitor ping unavailable on FortiOS 7.6.6).
3. Re-run the verification trio above after any FortiGate policy or interface change.
