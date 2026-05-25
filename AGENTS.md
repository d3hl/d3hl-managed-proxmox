# AGENTS.md

## Project

Homelab Proxmox SDN Design.

The goal is to maintain a practical VLAN-based homelab network using:

- Proxmox VE SDN
- FortiGate 100F as the main firewall and VLAN gateway
- Cisco Catalyst C9300 as the L2 core switch
- VLAN trunking to Proxmox nodes
- Isolated networks for management, storage, VM services, apps, lab, DMZ, and infrastructure management

## Current design assumptions

### Devices

| Device | Role | IP |
|---|---|---|
| FortiGate 100F | Main firewall and VLAN gateway | 10.99.99.2/24 on VLAN 99 |
| Cisco C9300 | Core L2 switch | 10.99.99.1/24 on VLAN 99 |
| Proxmox nodes | Virtualization hosts | pve01, pve02, pve03 |

### Routing model

FortiGate owns the gateway IP for all VLANs.

Use `.2` for FortiGate interfaces:

| VLAN | Purpose | Subnet | Gateway |
|---:|---|---|---|
| 10 | Proxmox management | 10.10.10.0/24 | 10.10.10.2 |
| 20 | Storage / Ceph | 10.20.20.0/24 | 10.20.20.2 |
| 30 | VM services | 10.10.30.0/24 | 10.10.30.2 |
| 40 | Containers / apps | 10.10.40.0/24 | 10.10.40.2 |
| 50 | Lab / test | 10.10.50.0/24 | 10.10.50.2 |
| 60 | DMZ / public-facing | 10.10.60.0/24 | 10.10.60.2 |
| 99 | Infrastructure management | 10.99.99.0/24 | 10.99.99.2 |

Cisco C9300 should not route between VLANs in this design. Only `interface Vlan99` exists for switch management.

## Proxmox SDN target

Use a VLAN Zone.

- Zone ID: `ztrunk`
- Type: VLAN
- Bridge: `vmbr0`
- Nodes: `pve01,pve02,pve03`

VNets:

| VNet | VLAN | Subnet | Gateway |
|---|---:|---|---|
| vmgmt | 10 | 10.10.10.0/24 | 10.10.10.2 |
| vstore | 20 | 10.20.20.0/24 | 10.20.20.2 |
| vsvc | 30 | 10.10.30.0/24 | 10.10.30.2 |
| vapps | 40 | 10.10.40.0/24 | 10.10.40.2 |
| vlab | 50 | 10.10.50.0/24 | 10.10.50.2 |
| vdmz | 60 | 10.10.60.0/24 | 10.10.60.2 |

Do not create `vinfra` / VLAN 99 in Proxmox unless explicitly requested.

## Cisco C9300 target

FortiGate trunk:

- Interface: `TenGigabitEthernet1/1/1`
- Allowed VLANs: `10,20,30,40,50,60,99`

Proxmox trunks:

- Interfaces: `TenGigabitEthernet1/1/2-4`
- Allowed VLANs: `10,20,30,40,50,60`

Do not allow VLAN 99 to Proxmox trunks unless explicitly requested.

## FortiGate target

Parent interface is currently a placeholder: `internal`.

Before applying, confirm whether the actual FortiGate uplink is:

- a physical port, such as `port1`
- an aggregate, such as `agg-core`
- a hardware/software switch interface, such as `internal`

All VLAN interfaces should be created under that parent interface.

## Automation guidance

When using MCP/automation tools:

1. Always read current running configuration first.
2. Detect existing VLANs, interfaces, trunks, SDN zones, VNets, and subnets.
3. Produce a diff/plan before mutation.
4. Avoid removing existing allowed VLANs unless explicitly instructed.
5. Apply changes in a safe order:
   - Create VLANs
   - Create switch SVI
   - Configure trunks
   - Create FortiGate VLAN interfaces
   - Create Proxmox SDN zone/VNets/subnets
   - Apply Proxmox SDN
6. Validate before saving persistent config.
7. Save/write memory only after validation succeeds.

## Validation commands

### Cisco IOS XE

```cisco
show vlan brief
show interfaces trunk
show ip interface brief
show running-config interface vlan99
ping 10.99.99.2 source vlan99
```

### FortiGate

```text
show system interface
get system interface
execute ping-options source 10.99.99.2
execute ping 10.99.99.1
```

### Proxmox

```bash
pvesh get /cluster/sdn
pvesh get /cluster/sdn/zones
pvesh get /cluster/sdn/vnets
ip -br link | grep -E 'vmgmt|vstore|vsvc|vapps|vlab|vdmz'
bridge vlan show
```

## Do not do

- Do not enable C9300 inter-VLAN routing unless the design changes.
- Do not create C9300 SVIs for VLANs 10,20,30,40,50,60.
- Do not trunk VLAN 99 to Proxmox by default.
- Do not change production trunks without preserving existing allowed VLANs.
- Do not save configuration until reachability is validated.

## Preferred response style for future agents

Keep outputs practical and execution-focused.

For any generated config, include:

- Assumptions
- Candidate config
- Validation commands
- Rollback hints
