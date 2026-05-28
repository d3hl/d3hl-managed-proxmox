# Session Handoff - DeepSeek Proxmox Continuation

Date: 2026-05-28

## Current State

Cisco C9300 live configuration was updated and validated in running-config only.
Do not assume startup-config has the same changes until `write memory` is
explicitly run after final validation.

Validated Cisco state:

- Management SVI: `Vlan10`, `10.10.10.1/24`
- Default gateway: `10.10.10.2`
- FortiGate trunk: `TwentyFiveGigE2/1/2`, allowed VLANs `10,11,100`
- Node trunks:
  - `TenGigabitEthernet2/0/39`, allowed VLANs `3,10,11`
  - `TenGigabitEthernet2/0/41`, allowed VLANs `3,10,11`
  - `TenGigabitEthernet2/0/46`, allowed VLANs `3,10,11`
- VLAN names now match repo intent:
  - `10 PROXMOX_MGMT`
  - `20 STORAGE_CEPH`
  - `30 VM_SERVICES`
  - `40 CONTAINERS_APPS`
  - `50 LAB_TEST`
  - `60 DMZ`
  - `99 INFRA_MGMT`
- Interface descriptions now match `configs/cisco-c9300-iosxe.cfg`.
- Cisco validation ping succeeded: `ping 10.10.10.2 source vlan10` returned `5/5`.

## Source Of Truth

Use these files first:

- `AGENTS.md`
- `data/network-plan.json`
- `configs/proxmox-sdn-pvesh.sh`
- `docs/safe-implementation-runbook.md`
- `docs/validation-checklist.md`
- `docs/1password-secrets.md`

`data/network-plan.json` now includes VLAN names, gateway ownership, and Cisco trunk descriptions.

## DeepSeek Next Task: Proxmox

Continue with read-only Proxmox discovery before any mutation:

```bash
bash configs/proxmox-sdn-pvesh.sh discover
bash configs/proxmox-sdn-pvesh.sh plan
```

Manual validation equivalents:

```bash
pvesh get /cluster/sdn
pvesh get /cluster/sdn/zones
pvesh get /cluster/sdn/vnets
pvesh get /cluster/sdn/subnets || true
ip -br link | grep -E 'vmgmt|vstore|vsvc|vapps|vlab|vdmz'
bridge vlan show
```

Target Proxmox SDN:

- Zone: `ztrunk`
- Type: VLAN
- Bridge: `vmbr0`
- VNets:
  - `vmgmt`, VLAN 10, subnet `10.10.10.0/24`, gateway `10.10.10.2`
  - `vstore`, VLAN 20, subnet `10.20.20.0/24`, no FortiGate gateway
  - `vsvc`, VLAN 30, subnet `10.10.30.0/24`, gateway `10.10.30.2`
  - `vapps`, VLAN 40, subnet `10.10.40.0/24`, gateway `10.10.40.2`
  - `vlab`, VLAN 50, subnet `10.10.50.0/24`, gateway `10.10.50.2`
  - `vdmz`, VLAN 60, subnet `10.10.60.0/24`, gateway `10.10.60.2`

Do not create `vinfra` or any VLAN 99 Proxmox VNet unless explicitly requested.

## Credentials

Use 1Password vault `d3HLPRV`.

Do not write plaintext secrets into files, prompts, logs, or handoff notes.
Follow `docs/1password-secrets.md`.

## Risks / Blockers

- Cisco changes are validated in running-config but not saved with `write memory`.
- ✅ Node names confirmed: `nodeA, nodeB, nodeD, nodeF`. Repo updated.
- ✅ vmbr0 is OVS (not Linux bridge) — natively VLAN-aware. Trunks updated on A,B,D.
- ⚠️ **nodeF esfp1** still access port (tag=10, native-untagged). Needs trunk conversion to `trunks=3,10,11,30,40,50,60`.
- SDN was empty; all objects are new.

## Applied State (2026-05-28 — synced from live)

### SDN
- Zone: `ztrunk` (vlan, bridge=vmbr0) ✅
- VNets: `vmgmt`(10), `vstore`(20), `vsvc`(30), `vapps`(40), `vlab`(50), `vdmz`(60) ✅
- Subnets: VLAN 10 and VLANs 30,40,50,60 use FortiGate .2 gateways; VLAN 20 is storage-side only ✅
- SDN applied cluster-wide ✅

### OVS Trunks (synced from live)
| Node | Port | Trunk VLANs | Bridge |
|---|---|---|---|
| nodeA | en10basep2 | 3,10,11,30,40,50,60 | vmbr0 |
| nodeB | ennic1s1 | 3,10,11,30,40,50,60 | vmbr0 |
| nodeD | eno1 | 3,10,11,30,40,50,60 | vmbr0 |
| nodeF | sfp1 | 10,11,30,40,50,60 | vmbr0 |

### OVS Bridges
| Bridge | Purpose | Nodes |
|---|---|---|
| vmbr0 | Management / VM trunk | all 4 |
| vmbr20 | Ceph storage (MTU 9000) | all 4 |
| vmbr3 | Quorum / VLAN 3 | nodeF only |

### Node Management IPs
| Node | IP | Gateway |
|---|---|---|
| nodeA | 10.10.10.18 | 10.10.10.2 |
| nodeB | 10.10.10.15 | 10.10.10.2 |
| nodeD | 10.10.10.17 | 10.10.10.2 |
| nodeF | 10.10.10.10 | 10.10.10.2 |

### Next Actions
1. Full cross-platform validation: Cisco↔Proxmox↔FortiGate
2. Cisco `write memory` after validation
3. FortiGate VLAN interface creation for VLANs 30,40,50,60 after C9300 trunk review
4. Test VM attachment to VNets
