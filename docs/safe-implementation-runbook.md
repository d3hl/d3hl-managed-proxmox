# Safe Implementation Runbook

This runbook implements the Homelab Proxmox SDN design without assuming live device state. Run discovery first, compare output against the target design, then apply only reviewed changes.

## Target Summary

FortiGate owns the `.2` gateway on every VLAN. The Cisco C9300 remains L2-only with only `Vlan99` for switch management. Proxmox uses VLAN SDN zone `ztrunk` on `vmbr0` and does not create `vinfra` / VLAN 99.

| VLAN | Purpose | Subnet | Gateway | Proxmox VNet |
|---:|---|---|---|---|
| 10 | Proxmox management | 10.10.10.0/24 | 10.10.10.2 | vmgmt |
| 20 | Storage / Ceph | 10.20.20.0/24 | 10.20.20.2 | vstore |
| 30 | VM services | 10.10.30.0/24 | 10.10.30.2 | vsvc |
| 40 | Containers / apps | 10.10.40.0/24 | 10.10.40.2 | vapps |
| 50 | Lab / test | 10.10.50.0/24 | 10.10.50.2 | vlab |
| 60 | DMZ / public-facing | 10.10.60.0/24 | 10.10.60.2 | vdmz |
| 99 | Infrastructure management | 10.99.99.0/24 | 10.99.99.2 | none |

## Read-Only Discovery

### Proxmox

Run on a Proxmox cluster node:

```bash
bash configs/proxmox-sdn-pvesh.sh discover
bash configs/proxmox-sdn-pvesh.sh plan
```

Manual equivalent:

```bash
hostname
pveversion
pvesh get /nodes
pvesh get /cluster/sdn
pvesh get /cluster/sdn/zones
pvesh get /cluster/sdn/vnets
pvesh get /cluster/sdn/subnets || true
grep -n "vmbr0\|bridge-vlan-aware\|bridge-vids" /etc/network/interfaces
bridge vlan show
```

### Cisco C9300

```cisco
show version
show running-config | include ^ip routing|^no ip routing|^ip default-gateway
show vlan brief
show interfaces trunk
show running-config interface TenGigabitEthernet1/1/1
show running-config interface TenGigabitEthernet1/1/2
show running-config interface TenGigabitEthernet1/1/3
show running-config interface TenGigabitEthernet1/1/4
show running-config interface Vlan99
show ip interface brief
```

### FortiGate

```text
get system status
show system interface
get system interface
show system zone
get router info routing-table all
```

Confirm the FortiGate parent trunk interface before using `configs/fortigate-100f-vlan-cli.conf`. The file intentionally contains `__CONFIRM_PARENT_INTERFACE__` and must not be pasted unchanged.

## Diff Rules

- Create missing VLANs, VNets, subnets, and VLAN interfaces only.
- Treat duplicate VLAN IDs, conflicting IPs, unexpected Cisco SVIs, and Proxmox VLAN 99 VNet/interface presence as review-required.
- Preserve existing Cisco trunk VLANs. The candidate config uses `switchport trunk allowed vlan add ...`.
- Do not prune VLANs from trunks unless a separate approved maintenance step says to do so.
- Do not save Cisco or FortiGate persistent config until validation succeeds.

## Apply Order

1. Save backups:
   - Cisco: `show running-config`
   - FortiGate: `show full-configuration system interface`
   - Proxmox: `pvesh get /cluster/sdn`, zones, VNets, and subnets
2. Cisco:
   - Apply `configs/cisco-c9300-iosxe.cfg`.
   - Confirm `ip routing` is not enabled for this L2 design.
   - Do not save yet.
3. FortiGate:
   - Replace `__CONFIRM_PARENT_INTERFACE__` with the confirmed parent interface.
   - Apply `configs/fortigate-100f-vlan-cli.conf`.
   - Create firewall policies separately.
4. Proxmox:
   - Confirm `vmbr0` exists and is VLAN-aware on all nodes.
   - Create missing objects:
     ```bash
     CONFIRM_PROXMOX_SDN_APPLY=yes bash configs/proxmox-sdn-pvesh.sh apply
     ```
   - After reviewing created objects, apply SDN:
     ```bash
     APPLY_PROXMOX_SDN=yes CONFIRM_PROXMOX_SDN_APPLY=yes bash configs/proxmox-sdn-pvesh.sh apply
     ```
5. Validate all three platforms.
6. Save Cisco and FortiGate configs only after validation passes.

## Validation

### Cisco

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
bash configs/proxmox-sdn-pvesh.sh validate
```

Manual equivalent:

```bash
pvesh get /cluster/sdn
pvesh get /cluster/sdn/zones
pvesh get /cluster/sdn/vnets
ip -br link | grep -E 'vmgmt|vstore|vsvc|vapps|vlab|vdmz'
bridge vlan show
```

## Rollback

### Cisco

If validation fails before saving, remove only newly added changes or reload the unsaved running config during the maintenance window. If trunk reachability changes unexpectedly, restore the pre-change allowed VLAN lists captured during discovery.

### FortiGate

Remove only interfaces that were newly created during this change:

```text
config system interface
    delete VLAN10_PROXMOX_MGMT
    delete VLAN20_STORAGE_CEPH
    delete VLAN30_VM_SERVICES
    delete VLAN40_CONTAINERS_APPS
    delete VLAN50_LAB_TEST
    delete VLAN60_DMZ
    delete VLAN99_INFRA_MGMT
end
```

If an interface existed before the change, restore its prior settings from backup instead of deleting it.

### Proxmox

Use the pre-change SDN snapshots to identify objects created by this run. Remove only those new subnets, VNets, and the `ztrunk` zone if it was newly created. Do not edit `/etc/network/interfaces` unless host bridge changes were explicitly approved.
