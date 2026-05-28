# Safe Implementation Runbook

This runbook implements the Homelab Proxmox SDN design without assuming live device state. Run discovery first, compare output against the target design, then apply only reviewed changes.

Use 1Password vault `d3HLPRV` for credentials. Follow `docs/1password-secrets.md`; do not put plaintext usernames, passwords, tokens, SSH keys, or exported `.env` files in this repository.

## Target Summary

FortiGate owns the `.2` gateway on VLAN 10 and the approved routed VLANs 30, 40, 50, and 60. VLAN 20 remains on the C9300/storage side and is not routed to the FortiGate. The Cisco C9300 is reached for management at `10.10.10.1` on VLAN 10. Proxmox uses VLAN SDN zone `ztrunk` on `vmbr0` and does not create `vinfra` / VLAN 99.

| VLAN | Purpose | Subnet | Gateway | Proxmox VNet |
|---:|---|---|---|---|
| 10 | Proxmox management | 10.10.10.0/24 | 10.10.10.2 | vmgmt |
| 20 | Storage / Ceph | 10.20.20.0/24 | none on FortiGate | vstore |
| 30 | VM services | 10.10.30.0/24 | 10.10.30.2 | vsvc |
| 40 | Containers / apps | 10.10.40.0/24 | 10.10.40.2 | vapps |
| 50 | Lab / test | 10.10.50.0/24 | 10.10.50.2 | vlab |
| 60 | DMZ / public-facing | 10.10.60.0/24 | 10.10.60.2 | vdmz |
| 99 | Infrastructure management | 10.99.99.0/24 | 10.99.99.2 | none |

## Read-Only Discovery

If a device login requires credentials, verify 1Password CLI access first without printing secrets:

```bash
op --version
op account list
```

Use secret references such as `op://d3HLPRV/C9300/username` and short-lived `op run` environment injection for tools that need credentials.

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
show running-config interface TwentyFiveGigE2/1/2
show running-config interface TenGigabitEthernet2/0/39
show running-config interface TenGigabitEthernet2/0/41
show running-config interface TenGigabitEthernet2/0/46
show running-config interface Vlan10
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

Confirm the C9300-to-FortiGate trunk carries `10,11,30,40,50,60,100` before using `configs/fortigate-100f-vlan-cli.conf`. The file uses the verified parent interface `x2` and intentionally excludes VLAN 20 and VLAN 99.

## Diff Rules

- Create missing VLANs, VNets, subnets, and VLAN interfaces only.
- Treat duplicate VLAN IDs, conflicting IPs, unexpected Cisco SVIs, and Proxmox VLAN 99 VNet/interface presence as review-required
- Do not prune VLANs from trunks unless a separate approved maintenance step says to do so.
- Do not save Cisco or FortiGate persistent config until validation succeeds.

## Apply Order

1. Save backups:
   - Cisco: `show running-config`
   - FortiGate: `show full-configuration system interface`
   - Proxmox: `pvesh get /cluster/sdn`, zones, VNets, and subnets
2. Cisco:
   - Apply `configs/cisco-c9300-iosxe.cfg`.
   - Confirm `ip routing` is not enabled for this L3 design.
   - Do not save yet.
3. FortiGate:
   - Confirm VLAN 10 is already tracked as `hlvl`.
   - Confirm VLAN 99 remains on `mgt` hard-switch.
   - Confirm VLAN 20 is not routed to the FortiGate.
   - Apply `configs/fortigate-100f-vlan-cli.conf` only for VLANs 30, 40, 50, and 60 after trunk review.
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
show running-config interface vlan10
ping 10.10.10.2 source vlan10
```

### FortiGate

```text
show system interface
get system interface
execute ping-options source 10.10.10.2
execute ping 10.10.10.1
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
    delete vsvc
    delete vapps
    delete vlab
    delete vdmz
end
```

Do not delete `hlvl`, `mgt`, VLAN 20 objects, `k8s`, or `Wifi` as part of this FortiGate rollback. If an interface existed before the change, restore its prior settings from backup instead of deleting it.

### Proxmox

Use the pre-change SDN snapshots to identify objects created by this run. Remove only those new subnets, VNets, and the `ztrunk` zone if it was newly created. Do not edit `/etc/network/interfaces` unless host bridge changes were explicitly approved.
