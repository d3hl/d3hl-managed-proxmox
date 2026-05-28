# Current Network Diagram

Generated from the repo state on 2026-05-28.

Primary sources:

- `data/network-plan.json`
- `configs/cisco-c9300-iosxe.cfg`
- `configs/fortigate-100f-vlan-cli.conf`
- `configs/proxmox-sdn-pvesh.sh`
- `session-handoff.md`

## Topology

```mermaid
flowchart LR
  fg["FortiGate 100F<br/>Gateway and firewall<br/>Mgmt: 10.99.99.2/24 on mgt hard-switch<br/>API: https://10.99.99.2:7443<br/>Verified trunk parent: x2"]

  c9300["Cisco Catalyst C9300<br/>Core switch<br/>Vlan10: 10.10.10.1/24<br/>Default gateway: 10.10.10.2"]

  fg ==>|Trunk to C9300<br/>C9300 port: TwentyFiveGigE2/1/2<br/>Allowed VLANs: 10,11,100| c9300

  subgraph pve["Proxmox VE cluster"]
    direction TB

    sdn["SDN zone: ztrunk<br/>Type: VLAN<br/>Bridge: vmbr0<br/>Nodes: nodeA,nodeB,nodeD,nodeF"]

    nodeA["nodeA<br/>Mgmt: 10.10.10.18<br/>vmbr0 OVS<br/>Port en10basep2<br/>Trunks: 3,10,11,30,40,50,60"]
    nodeB["nodeB<br/>Mgmt: 10.10.10.15<br/>vmbr0 OVS<br/>Port ennic1s1<br/>Trunks: 3,10,11,30,40,50,60"]
    nodeD["nodeD<br/>Mgmt: 10.10.10.17<br/>vmbr0 OVS<br/>Port eno1<br/>Trunks: 3,10,11,30,40,50,60"]
    nodeF["nodeF<br/>Mgmt: 10.10.10.10<br/>vmbr0 OVS<br/>Port sfp1<br/>Trunks: 10,11,30,40,50,60<br/>VLAN 3 via vmbr3/nic4"]

    vmgmt["vmgmt<br/>VLAN 10<br/>10.10.10.0/24<br/>GW 10.10.10.2"]
    vstore["vstore<br/>VLAN 20<br/>10.20.20.0/24<br/>GW 10.20.20.2"]
    vsvc["vsvc<br/>VLAN 30<br/>10.10.30.0/24<br/>GW 10.10.30.2"]
    vapps["vapps<br/>VLAN 40<br/>10.10.40.0/24<br/>GW 10.10.40.2"]
    vlab["vlab<br/>VLAN 50<br/>10.10.50.0/24<br/>GW 10.10.50.2"]
    vdmz["vdmz<br/>VLAN 60<br/>10.10.60.0/24<br/>GW 10.10.60.2"]

    nodeA --- sdn
    nodeB --- sdn
    nodeD --- sdn
    nodeF --- sdn

    sdn --> vmgmt
    sdn --> vstore
    sdn --> vsvc
    sdn --> vapps
    sdn --> vlab
    sdn --> vdmz
  end

  c9300 ==>|Te2/0/39<br/>Repo/live validated allowed VLANs: 3,10,11<br/>network-plan target adds: 30,40,50,60| nodeA
  c9300 ==>|Te2/0/41<br/>Repo/live validated allowed VLANs: 3,10,11<br/>network-plan target adds: 30,40,50,60| nodeB
  c9300 ==>|Te2/0/46<br/>Repo/live validated allowed VLANs: 3,10,11<br/>network-plan target adds: 30,40,50,60| nodeD
  c9300 -.->|No C9300 port mapping captured<br/>nodeF uses Proxmox port sfp1| nodeF

  fg -.->|Live: hlvl VLAN 10 on x2<br/>Candidate names still need reconciliation| vmgmt
  fg -.->|Gateway .2| vstore
  fg -.->|Gateway .2| vsvc
  fg -.->|Gateway .2| vapps
  fg -.->|Gateway .2| vlab
  fg -.->|Gateway .2| vdmz
```

## VLAN And VNet Map

| VLAN | Name | Purpose | Subnet | Gateway | Proxmox VNet |
|---:|---|---|---|---|---|
| 10 | PROXMOX_MGMT | Proxmox management | 10.10.10.0/24 | 10.10.10.2 | vmgmt |
| 20 | STORAGE_CEPH | Storage / Ceph | 10.20.20.0/24 | 10.20.20.2 | vstore |
| 30 | VM_SERVICES | VM services | 10.10.30.0/24 | 10.10.30.2 | vsvc |
| 40 | CONTAINERS_APPS | Containers / apps | 10.10.40.0/24 | 10.10.40.2 | vapps |
| 50 | LAB_TEST | Lab / test | 10.10.50.0/24 | 10.10.50.2 | vlab |
| 60 | DMZ | DMZ / public-facing | 10.10.60.0/24 | 10.10.60.2 | vdmz |
| 99 | INFRA_MGMT | Infrastructure management | 10.99.99.0/24 | 10.99.99.2 | none |

## Current Review Notes

- FortiGate VLAN interfaces are still candidate config. The parent trunk interface is `__CONFIRM_PARENT_INTERFACE__` and must be discovered before apply.
- FortiGate API was verified at `https://10.99.99.2:7443`.
- FortiGate parent trunk interface was verified as `x2`.
- Live FortiGate VLAN interfaces on `x2`: `hlvl` VLAN 10 (`10.10.10.2/24`), `k8s` VLAN 11 (`10.11.11.2/24`), and `Wifi` VLAN 100 (`10.100.100.2/24`).
- Repo target VLAN interface names are not present yet: `VLAN20_STORAGE_CEPH`, `VLAN30_VM_SERVICES`, `VLAN40_CONTAINERS_APPS`, `VLAN50_LAB_TEST`, and `VLAN60_DMZ` are missing.
- VLAN 99 target conflicts with existing `mgt` hard-switch using `10.99.99.2/24`; do not create a VLAN 99 interface without a reviewed migration plan.
- FortiGate VLAN interfaces are still candidate config. The parent trunk interface is now known, but live naming/IP conflicts must be reconciled before apply.
- The validated C9300 FortiGate trunk currently allows VLANs `10,11,100`, while the FortiGate candidate gateway config includes VLANs `10,20,30,40,50,60,99`. Review trunk allowance before expecting those gateways to pass on that link.
- `configs/cisco-c9300-iosxe.cfg` and `session-handoff.md` show Proxmox-facing C9300 trunks allowing `3,10,11`; `data/network-plan.json` now records the expanded target `3,10,11,30,40,50,60`.
- Proxmox SDN is represented as applied cluster-wide in `session-handoff.md`: zone `ztrunk` plus VNets `vmgmt`, `vstore`, `vsvc`, `vapps`, `vlab`, and `vdmz`.
- `vinfra` / VLAN 99 is intentionally not created in Proxmox.
