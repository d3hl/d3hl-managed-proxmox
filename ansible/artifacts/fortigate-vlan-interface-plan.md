# FortiGate VLAN Interface Plan

This plan is rendered from `ansible/group_vars/fortigates.yml`.

## Assumptions

- FortiGate keeps the existing live VLAN 10 gateway as `hlvl`.
- FortiGate keeps infrastructure management on the existing `mgt` hard-switch.
- VLAN 20 remains on the C9300/storage side and is not routed to the firewall.
- This plan only creates or updates missing FortiGate VLAN gateways for VLANs 30, 40, 50, and 60.
- VDOM: `root`
- Parent interface: `x2`
- Apply is blocked until `CONFIRM_FORTIGATE_APPLY=yes` and `CONFIRM_FORTIGATE_TRUNK_REVIEW=yes` are set.

## Existing Interfaces Tracked

| Interface | VLAN | IP | Access | Alias | Role |
|---|---:|---|---|---|---|
| hlvl | 10 | 10.10.10.2/24 | ping,https,ssh,snmp,fgfm,fabric | Proxmox management | lan |
| mgt | n/a | 10.99.99.2/24 | ping,https,ssh | Infrastructure management | lan |


## Candidate Interfaces To Add After Trunk Review

| Interface | VLAN | IP | Access | Alias | Role |
|---|---:|---|---|---|---|
| vsvc | 30 | 10.10.30.2/24 | ping | VM services | lan |
| vapps | 40 | 10.10.40.2/24 | ping | Containers / apps | lan |
| vlab | 50 | 10.10.50.2/24 | ping | Lab / test | lan |
| vdmz | 60 | 10.10.60.2/24 | ping | DMZ / public-facing | dmz |


## Validation Commands

```text
show system interface
get system interface
execute ping-options source 10.10.10.2
execute ping 10.10.10.1
```

## Rollback Hint

Remove only VLAN interfaces created by this plan: `vsvc`, `vapps`, `vlab`, and `vdmz`. Do not delete `hlvl`, `mgt`, or any VLAN 20 objects as part of this FortiGate plan.