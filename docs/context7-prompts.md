# Context7 / MCP Execution Prompts

## Proxmox MCP prompt

```text
Use Context7 to load the latest Proxmox VE SDN documentation.

Configure Proxmox SDN for a VLAN-based homelab network.

Cluster nodes:
- nodeA : 10.10.10.18/24, 10.20.20.18/24, 192.168.3.18/24
- nodeB : 10.10.10.15/24, 10.20.20.15/24, 192.168.3.15/24
- nodeD : 10.10.10.17/24, 10.20.20.17/24, 192.168.3.17/24
- nodeF : 10.10.10.10/24, 10.20.20.10/24, 192.168.3.10/24

Base bridge:
- vmbr0
- VLAN-aware trunk bridge

Create SDN VLAN zone:
- Zone ID: ztrunk
- Type: VLAN
- Bridge: vmbr0
- Nodes: nodeA,nodeB,nodeD,nodeF

Create VNets:
- vmgmt, VLAN 10, subnet 10.99.99.0/24, gateway 10.99.99.2
- vceph, VLAN 20, subnet 10.20.20.0/24, gateway 10.20.20.1
- vvm, VLAN 30, subnet 10.10.30.0/24, gateway 10.10.30.2
- vapps, VLAN 40, subnet 10.10.40.0/24, gateway 10.10.40.2
- vlab, VLAN 50, subnet 10.10.50.0/24, gateway 10.10.50.2
- vdmz, VLAN 60, subnet 10.10.60.0/24, gateway 10.10.60.2
- vquorum, VLAN3, subnet 192.168.3.0/24, gateway 192.168.3.1 

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
- Management IP: 10.10.10.1/24
- Default gateway: FortiGate 100F at 10.10.10.2

Design:
- FortiGate 100F is the L3 gateway/firewall for all VLANs.
- C9300 is the L3 core switch.
- Do not change inter-VLAN routing behavior without an explicit reviewed plan.
- VLAN 99 is infrastructure management.
- VLAN 99 should be allowed only on the FortiGate uplink unless explicitly needed elsewhere.
- Node trunks should carry VLANs 3,10,11.
- FortiGate trunk should carry VLANs 10,11,100.

Create VLANs:
- VLAN 10: PROXMOX_MGMT
- VLAN 20: STORAGE_CEPH
- VLAN 30: VM_SERVICES
- VLAN 40: CONTAINERS_APPS
- VLAN 50: LAB_TEST
- VLAN 60: DMZ
- VLAN 99: INFRA_MGMT

Configure SVI:
- interface Vlan10
- description Core switch management
- ip address 10.10.10.1 255.255.255.0
- no shutdown

Configure default gateway:
- ip default-gateway 10.10.10.2

Configure trunk to FortiGate:
- interface TwentyFiveGigE2/1/2
- description Trunk_to_FortiGate_100F
- mode trunk
- allowed VLANs: 10,11,100

Configure trunks to Proxmox:
- interfaces TenGigabitEthernet2/0/39, TenGigabitEthernet2/0/41, TenGigabitEthernet2/0/46
- description Trunk_to_Proxmox_Nodes
- mode trunk
- allowed VLANs: 3,10,11

Validate:
- show vlan brief
- show interfaces trunk
- show ip interface brief
- show running-config interface vlan10
- ping 10.10.10.2 source vlan10
- write memory only after successful validation
```
