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

## Network dashboard canvas refresh

The homelab network dashboard is a Cursor canvas at
`~/.cursor/projects/home-d3-Github-d3hl-managed-proxmox/canvases/homelab-network-dashboard.canvas.tsx`.
It shows FortiGate → C9300 → Proxmox topology, VLAN relationships, interface status, and IP inventory.

### Prerequisites

- [ ] 1Password CLI authenticated (`op whoami`) or `OP_SERVICE_ACCOUNT_TOKEN` exported.
- [ ] Vault `d3HLPRV` credentials available for FortiGate API, Cisco SSH, and Proxmox API.

### Refresh from the canvas

1. Open the canvas beside chat and click **Refresh live data**.
2. The button opens an agent chat with a prompt to re-run discovery and update the canvas sidecar.
3. Confirm `homelab-network-dashboard.canvas.data.json` timestamp updates after the agent completes.

### Refresh from the shell

```bash
# Offline merge from existing artifacts only
bash configs/network-dashboard-collect.sh --write-sidecar

# Live discovery + merge + sidecar update
bash configs/network-dashboard-collect.sh --live --write-sidecar
```

Expected outputs:

- `data/network-dashboard-snapshot.json` — committed snapshot artifact
- `~/.cursor/projects/home-d3-Github-d3hl-managed-proxmox/canvases/homelab-network-dashboard.canvas.data.json` — runtime canvas state

### Rollback

Delete `homelab-network-dashboard.canvas.data.json` to fall back to the embedded seed snapshot in the `.canvas.tsx` file.
