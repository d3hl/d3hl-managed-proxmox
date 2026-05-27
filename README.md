# Homelab Proxmox SDN Network Design

This bundle contains execution-ready configuration artifacts for a practical homelab network using:

- Proxmox VE SDN
- FortiGate 100F as main firewall and VLAN gateway
- Cisco Catalyst C9300 as core L2 switch
- VLAN-based segmentation
- Proxmox SDN VLAN Zone using `vmbr0`

## Topology

```text
Internet / ISP
     |
FortiGate 100F
Mgmt / VLAN 99 IP: 10.99.99.2/24
     |
802.1Q trunk
     |
Cisco C9300 Core Switch
Mgmt / VLAN 10 IP: 10.10.10.1/24
     |
802.1Q trunks
     |
Proxmox Nodes: nodeA, nodeB, nodeD, nodeF
```

## Gateway model

FortiGate owns `.2` on every VLAN and is the default gateway for routed VLANs.

Cisco C9300 is reached for management on VLAN 10 at `10.10.10.1/24`.

## VLAN table

| Purpose | VLAN | Subnet | FortiGate Gateway |
|---|---:|---|---|
| Proxmox management | 10 | 10.10.10.0/24 | 10.10.10.2 |
| Storage / Ceph | 20 | 10.20.20.0/24 | 10.20.20.2 |
| VM services | 30 | 10.10.30.0/24 | 10.10.30.2 |
| Containers / apps | 40 | 10.10.40.0/24 | 10.10.40.2 |
| Lab / test | 50 | 10.10.50.0/24 | 10.10.50.2 |
| DMZ / public-facing | 60 | 10.10.60.0/24 | 10.10.60.2 |
| Infrastructure management | 99 | 10.99.99.0/24 | 10.99.99.2 |

## Files

- `AGENTS.md` — instructions for future AI/automation agents.
- `configs/cisco-c9300-iosxe.cfg` — Cisco IOS XE candidate configuration.
- `configs/fortigate-100f-vlan-cli.conf` — FortiGate VLAN interface candidate configuration.
- `configs/proxmox-sdn-pvesh.sh` — safe Proxmox SDN `pvesh` discovery, plan, apply, and validation helper.
- `configs/proxmox-vmbr0-example.interfaces` — example Proxmox host bridge config.
- `mcp/proxmox_mcp_server.py` — read-only Proxmox MCP discovery server.
- `docs/1password-secrets.md` — 1Password vault `d3HLPRV` credential handling standard.
- `docs/context7-prompts.md` — MCP/Context7 execution prompts.
- `docs/multi-agent-deepseek-contract.md` — Codex and DeepSeek role split, handoff format, and validation contract.
- `docs/safe-implementation-runbook.md` — discovery, diff, apply, validation, and rollback runbook.
- `docs/validation-checklist.md` — post-change validation steps.
- `data/network-plan.json` — machine-readable design data.

## Safety notes

Review interface names before applying.

Do not paste directly into production devices without checking:
- FortiGate parent interface or aggregate name
- C9300 port names
- Proxmox node names
- Existing VLANs and trunks
- Existing management access path
- 1Password vault `d3HLPRV` access for required credentials

Do not store plaintext secrets in this repository. Use `docs/1password-secrets.md`.


## Continue in Codex

This bundle includes:

- `AGENTS.md`
- `CODEX_TASK.md`
- `docs/continue-in-codex.md`

Use `CODEX_TASK.md` as the first prompt/task in Codex.
