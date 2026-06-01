# AGENTS.md — d3hl-managed-proxmox

Shared startup, DoD, and session rules: **`agent-contract-master/AGENTS.md`** (multi-root workspace).

Work only in this repo (`proxmox` root) for files, git, `feature_list.json`, and `claude-progress.md`.

## Project

Homelab Proxmox SDN design: VLAN-based network with Proxmox VE SDN, FortiGate 100F, Cisco C9300, trunks to Proxmox nodes.

## Devices

| Device | Role | IP |
|--------|------|-----|
| FortiGate 100F | Firewall / VLAN gateway | 10.99.99.2/24 on VLAN 99 |
| Cisco C9300 | Core L3 switch | 10.10.10.1/24 on VLAN 10 |
| Proxmox nodes | Virtualization | nodeA, nodeB, nodeD, nodeF |

## Routing model

FortiGate owns gateway IPs for VLANs 10, 30, 40, 50, and 60. VLAN 20 stays on C9300/storage (not on FortiGate). VLAN 99 stays on FortiGate `mgt` hard-switch — do not recreate as a VLAN interface.

| VLAN | Purpose | Subnet | Gateway |
|-----:|---------|--------|---------|
| 10 | Proxmox management | 10.10.10.0/24 | 10.10.10.2 |
| 20 | Storage / Ceph | 10.20.20.0/24 | none on FortiGate |
| 30 | VM services | 10.10.30.0/24 | 10.10.30.2 |
| 40 | Containers / apps | 10.10.40.0/24 | 10.10.40.2 |
| 50 | Lab / test | 10.10.50.0/24 | 10.10.50.2 |
| 60 | DMZ | 10.10.60.0/24 | 10.10.60.2 |
| 99 | Infra management | 10.99.99.0/24 | 10.99.99.2 (`mgt`) |

C9300 management: `10.10.10.1` on VLAN 10. Do not change or remove SVIs without a reviewed migration plan.

## Proxmox SDN target

- Zone: `ztrunk`, type VLAN, bridge `vmbr0`, nodes `nodeA,nodeB,nodeD,nodeF`

| VNet | VLAN | Subnet | Gateway |
|------|-----:|--------|---------|
| vmgmt | 10 | 10.10.10.0/24 | 10.10.10.2 |
| vstore | 20 | 10.20.20.0/24 | none on FortiGate |
| vsvc | 30 | 10.10.30.0/24 | 10.10.30.2 |
| vapps | 40 | 10.10.40.0/24 | 10.10.40.2 |
| vlab | 50 | 10.10.50.0/24 | 10.10.50.2 |
| vdmz | 60 | 10.10.60.0/24 | 10.10.60.2 |

Do not create `vinfra` / VLAN 99 in Proxmox unless explicitly requested.

## Cisco C9300 target

FortiGate trunk `TwentyFiveGigE2/1/2`: VLANs `10,11,30,40,50,60,100`.

Proxmox trunks `TenGigabitEthernet2/0/39`, `TenGigabitEthernet2/0/41`, `TenGigabitEthernet2/0/46`: VLANs `3,10,11,30,40,50,60`.

Do not allow VLAN 99 on Proxmox trunks unless explicitly requested.

## FortiGate target

Parent: `x2`. Use live names: VLAN 10 → `hlvl` on `x2`; VLAN 99 → `mgt`; VLAN 20 not routed on FortiGate. Add missing `30`, `40`, `50`, `60` under `x2` only after trunk review.

## Automation (MCP / live devices)

1. Read running config first
2. Detect existing VLANs, trunks, SDN zones/VNets
3. Diff/plan before mutation
4. Do not remove existing allowed VLANs unless instructed
5. Safe order: VLANs → SVI → trunks → FortiGate VLAN IFs → Proxmox SDN → apply SDN
6. Validate before persistent save
7. Save only after validation

## Secrets

Follow `agent-contract-master/docs/secrets-baseline.md`. Item names and `op://` paths: **`docs/1password-secrets.md`** in this repo.

## Validation

**Cisco:**

```cisco
show vlan brief
show interfaces trunk
show ip interface brief
show running-config interface vlan10
ping 10.10.10.2 source vlan10
```

**FortiGate:**

```text
show system interface
get system interface
execute ping-options source 10.10.10.2
execute ping 10.10.10.1
```

**Proxmox:**

```bash
pvesh get /cluster/sdn
pvesh get /cluster/sdn/zones
pvesh get /cluster/sdn/vnets
ip -br link | grep -E 'vmgmt|vstore|vsvc|vapps|vlab|vdmz'
bridge vlan show
```

## Do not

- Change C9300 inter-VLAN routing without a design change
- Create or remove C9300 SVIs without a reviewed plan
- Trunk VLAN 99 to Proxmox by default
- Shrink production trunk allowed VLANs
- Save config before reachability checks pass

## Docs index

- `docs/validation-checklist.md`, `docs/safe-implementation-runbook.md`
- FortiGate runbooks under `docs/fortigate-*.md`

## Response style

For generated config include: assumptions, candidate config, validation commands, rollback hints.
