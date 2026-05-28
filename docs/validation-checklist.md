# Validation Checklist

## Before applying

- [ ] Run the read-only discovery commands in `docs/safe-implementation-runbook.md`.
- [ ] Review candidate diff and mark conflicts before mutation.
- [ ] Confirm 1Password CLI access and vault `d3HLPRV` availability for any required credentials.
- [ ] Confirm FortiGate parent trunk interface `x2`.
- [ ] Confirm C9300 FortiGate uplink port.
- [ ] Confirm C9300 FortiGate trunk carries VLANs 10,11,30,40,50,60,100 before FortiGate apply.
- [ ] Confirm C9300 Proxmox node ports.
- [ ] Confirm Proxmox node names.
- [ ] Confirm `vmbr0` exists and is VLAN-aware on all Proxmox nodes.
- [ ] Confirm current management access will not be cut off.
- [ ] Back up existing configs.
- [ ] Verify Cisco trunk changes preserve existing allowed VLANs.

## Cisco C9300 validation

```cisco
show vlan brief
show interfaces trunk
show ip interface brief
show running-config interface vlan10
ping 10.10.10.2 source vlan10
```

Expected:
- VLANs 10,20,30,40,50,60,99 exist.
- FortiGate trunk allows VLANs 10,11,30,40,50,60,100 before FortiGate gateway apply.
- Node trunks allow VLANs 3,10,11.
- VLAN10 SVI is up/up.
- C9300 can ping FortiGate 10.10.10.2 from VLAN10.

## FortiGate validation

```text
show system interface
get system interface
execute ping-options source 10.10.10.2
execute ping 10.10.10.1
```

Expected:
- Existing `hlvl` VLAN 10 interface remains present with `10.10.10.2/24`.
- Existing `mgt` hard-switch remains present with `10.99.99.2/24`.
- VLAN 20 is not created as a FortiGate routed interface.
- Candidate VLAN interfaces 30,40,50,60 exist with `.2` addresses after apply.
- FortiGate can ping C9300 management IP 10.10.10.1.
- Firewall policies are created separately according to security requirements.

## Proxmox validation

```bash
pvesh get /cluster/sdn
pvesh get /cluster/sdn/zones
pvesh get /cluster/sdn/vnets
ip -br link | grep -E 'vmgmt|vstore|vsvc|vapps|vlab|vdmz'
bridge vlan show
```

Expected:
- Zone `ztrunk` exists.
- VNets exist: `vmgmt`, `vstore`, `vsvc`, `vapps`, `vlab`, `vdmz`.
- VNet interfaces appear on the Proxmox nodes after SDN apply.
- VMs can attach to the correct VNet.
