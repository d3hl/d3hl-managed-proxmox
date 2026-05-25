# Context7 / MCP Execution Prompts

## Proxmox MCP prompt

```text
Use Context7 to load the latest Proxmox VE SDN documentation.

Configure Proxmox SDN for a VLAN-based homelab network.

Cluster nodes:
- pve01
- pve02
- pve03

Base bridge:
- vmbr0
- VLAN-aware trunk bridge

Create SDN VLAN zone:
- Zone ID: ztrunk
- Type: VLAN
- Bridge: vmbr0
- Nodes: pve01,pve02,pve03

Create VNets:
- vmgmt, VLAN 10, subnet 10.10.10.0/24, gateway 10.10.10.2
- vstore, VLAN 20, subnet 10.20.20.0/24, gateway 10.20.20.2
- vsvc, VLAN 30, subnet 10.10.30.0/24, gateway 10.10.30.2
- vapps, VLAN 40, subnet 10.10.40.0/24, gateway 10.10.40.2
- vlab, VLAN 50, subnet 10.10.50.0/24, gateway 10.10.50.2
- vdmz, VLAN 60, subnet 10.10.60.0/24, gateway 10.10.60.2

Do not create vinfra/VLAN 99 on Proxmox unless explicitly requested.

After creating the SDN objects, apply/reload SDN configuration cluster-wide.
Validate that VNet interfaces exist on all nodes.
```

## Cisco IOS XE MCP prompt

```text
Use Context7 to load the latest Cisco IOS XE documentation for Catalyst 9300 VLANs, trunk ports, SVIs, and management default gateway behavior.

Target device:
- Cisco Catalyst C9300
- Core switch
- Management IP: 10.99.99.1/24
- Default gateway: FortiGate 100F at 10.99.99.2

Design:
- FortiGate 100F is the L3 gateway/firewall for all VLANs.
- C9300 is the L2 core switch.
- Do not enable inter-VLAN routing on the C9300 for this design.
- VLAN 99 is infrastructure management.
- VLAN 99 should be allowed only on the FortiGate uplink unless explicitly needed elsewhere.
- Proxmox trunks should carry VLANs 10,20,30,40,50,60.
- FortiGate trunk should carry VLANs 10,20,30,40,50,60,99.

Create VLANs:
- VLAN 10: PROXMOX_MGMT
- VLAN 20: STORAGE_CEPH
- VLAN 30: VM_SERVICES
- VLAN 40: CONTAINERS_APPS
- VLAN 50: LAB_TEST
- VLAN 60: DMZ
- VLAN 99: INFRA_MGMT

Configure SVI:
- interface Vlan99
- description Core switch management
- ip address 10.99.99.1 255.255.255.0
- no shutdown

Configure default gateway:
- ip default-gateway 10.99.99.2

Configure trunk to FortiGate:
- interface TenGigabitEthernet1/1/1
- description Trunk_to_FortiGate_100F
- mode trunk
- allowed VLANs: 10,20,30,40,50,60,99

Configure trunks to Proxmox:
- interfaces TenGigabitEthernet1/1/2-4
- description Trunk_to_Proxmox_Nodes
- mode trunk
- allowed VLANs: 10,20,30,40,50,60

Validate:
- show vlan brief
- show interfaces trunk
- show ip interface brief
- show running-config interface vlan99
- ping 10.99.99.2 source vlan99
- write memory only after successful validation
```
