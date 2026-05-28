# FortiGate Repo vs Live Comparison - 2026-05-29

Scope: read-only comparison of checked-in FortiGate intent against live FortiGate interface state.

No FortiGate configuration changes were attempted.

## Sources Compared

Repo intent:

- `ansible/group_vars/fortigates.yml`
- `configs/fortigate-100f-vlan-cli.conf`
- `data/network-plan.json`

Live source:

- FortiGate REST API at `https://10.99.99.2:7443`
- VDOM: `root`
- Token source: `op://d3HLPRV/FORTIOS_ACCESS_TOKEN/credential`
- Secret values printed: no

## Summary

| Area | Repo intent | Live FortiGate | Status |
|---|---|---|---|
| API endpoint | `ansible_httpapi_port: 7443` | API reachable at `10.99.99.2:7443` | match |
| VLAN parent | `x2` in Ansible vars; placeholder in CLI candidate | `x2` is live VLAN parent | partial drift |
| VLAN 10 gateway | `VLAN10_PROXMOX_MGMT`, VLAN 10, `10.10.10.2/24` | `hlvl`, VLAN 10, parent `x2`, `10.10.10.2/24` | name drift |
| VLAN 20 gateway | `VLAN20_STORAGE_CEPH`, `10.20.20.2/24` | not present | missing |
| VLAN 30 gateway | `VLAN30_VM_SERVICES`, `10.10.30.2/24` | not present | missing |
| VLAN 40 gateway | `VLAN40_CONTAINERS_APPS`, `10.10.40.2/24` | not present | missing |
| VLAN 50 gateway | `VLAN50_LAB_TEST`, `10.10.50.2/24` | not present | missing |
| VLAN 60 gateway | `VLAN60_DMZ`, `10.10.60.2/24` | not present | missing |
| VLAN 99 gateway | `VLAN99_INFRA_MGMT`, VLAN 99, `10.99.99.2/24` | `mgt` hard-switch already owns `10.99.99.2/24` | IP/design conflict |
| Existing VLAN 11 | not a target gateway in repo VLAN list | `k8s`, VLAN 11, parent `x2`, `10.11.11.2/24` | live extra |
| Existing VLAN 100 | trunked to FortiGate in Cisco intent | `Wifi`, VLAN 100, parent `x2`, `10.100.100.2/24` | live extra |

## Live VLAN Interfaces

| Interface | VLAN | Parent | IP | Access | Status |
|---|---:|---|---|---|---|
| `hlvl` | 10 | `x2` | `10.10.10.2/24` | `ping https ssh snmp fgfm fabric` | up |
| `k8s` | 11 | `x2` | `10.11.11.2/24` | `ping` | up |
| `Wifi` | 100 | `x2` | `10.100.100.2/24` | `ping` | up |

## Target Interface Comparison

| Repo target | Expected VLAN/IP | Live equivalent | Result |
|---|---|---|---|
| `VLAN10_PROXMOX_MGMT` | VLAN 10, `10.10.10.2/24` | `hlvl` | present with different name |
| `VLAN20_STORAGE_CEPH` | VLAN 20, `10.20.20.2/24` | none | missing |
| `VLAN30_VM_SERVICES` | VLAN 30, `10.10.30.2/24` | none | missing |
| `VLAN40_CONTAINERS_APPS` | VLAN 40, `10.10.40.2/24` | none | missing |
| `VLAN50_LAB_TEST` | VLAN 50, `10.10.50.2/24` | none | missing |
| `VLAN60_DMZ` | VLAN 60, `10.10.60.2/24` | none | missing |
| `VLAN99_INFRA_MGMT` | VLAN 99, `10.99.99.2/24` | `mgt` hard-switch | IP/design conflict |

## Important Drift

- The Ansible intent has the correct live parent interface (`x2`) and API port (`7443`).
- The CLI candidate file still uses `__CONFIRM_PARENT_INTERFACE__`; it is stale compared with Ansible intent and live discovery.
- Creating `VLAN10_PROXMOX_MGMT` as a new interface would duplicate the existing VLAN 10 gateway currently named `hlvl`.
- Creating `VLAN99_INFRA_MGMT` would conflict with the existing `mgt` hard-switch IP `10.99.99.2/24`.
- Cisco-to-FortiGate trunk intent still allows only VLANs `10,11,100`; this aligns with live FortiGate VLANs but not with repo target VLANs `20,30,40,50,60`.

## Safe Next Decision

Choose one FortiGate intent model before applying changes:

1. Adopt live names:
   - Track VLAN 10 as `hlvl`.
   - Keep VLAN 99 on `mgt` hard-switch.
   - Add only missing VLANs 20, 30, 40, 50, and 60 after trunk review.

2. Migrate to repo target names:
   - Plan a controlled rename/migration for VLAN 10 from `hlvl` to `VLAN10_PROXMOX_MGMT`.
   - Explicitly decide whether VLAN 99 remains `mgt` or becomes a VLAN interface.
   - Update firewall policies, DHCP, routes, and references before changing names.

Recommended: adopt live names for existing production interfaces, and only add missing VLAN gateways after Cisco trunk allowance is reviewed.

## Decision Recorded

Adopt live names and adjust repo intent:

- Track VLAN 10 as existing FortiGate interface `hlvl`.
- Keep VLAN 99 on existing FortiGate `mgt` hard-switch.
- Do not create a FortiGate VLAN 20 interface; VLAN 20 remains on the C9300/storage side.
- Add only missing FortiGate VLAN gateways 30, 40, 50, and 60 after C9300-to-FortiGate trunk review.
