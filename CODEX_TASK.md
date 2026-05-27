# CODEX_TASK.md

## Task title

Continue Homelab Proxmox SDN Design

## Objective

Use this repository as the source of truth for a practical homelab network design using:

- Proxmox VE SDN
- FortiGate 100F as main firewall and VLAN gateway
- Cisco Catalyst C9300 as core L3 switch
- VLAN-based segmentation
- Context7 MCP for vendor documentation lookups
- Proxmox MCP for Proxmox execution when available
- Cisco IOS XE MCP for Catalyst execution when available

## Important existing decisions

1. FortiGate owns `.2` on every VLAN.
2. C9300 management IP is `10.10.10.1/24`.
3. FortiGate infrastructure management IP is `10.99.99.2/24`.
4. FortiGate is the L3 gateway/firewall for all VLANs.
5. C9300 is reached for management at `10.10.10.1` on VLAN 10.
6. Do not change C9300 inter-VLAN routing behavior without an explicit reviewed plan.
7. Do not create or remove C9300 SVIs without an explicit reviewed plan.
8. VLAN 99 is infrastructure management.
9. Do not trunk VLAN 99 to Proxmox nodes unless explicitly requested.
10. Proxmox SDN uses VLAN Zone `ztrunk` on `vmbr0`.

## Files to inspect first

Read these files before making changes:

- `AGENTS.md`
- `README.md`
- `data/network-plan.json`
- `configs/cisco-c9300-iosxe.cfg`
- `configs/fortigate-100f-vlan-cli.conf`
- `configs/proxmox-sdn-pvesh.sh`
- `docs/context7-prompts.md`
- `docs/validation-checklist.md`

## Current VLAN plan

| VLAN | Purpose | Subnet | Gateway |
|---:|---|---|---|
| 10 | Proxmox management | 10.10.10.0/24 | 10.10.10.2 |
| 20 | Storage / Ceph | 10.20.20.0/24 | 10.20.20.2 |
| 30 | VM services | 10.10.30.0/24 | 10.10.30.2 |
| 40 | Containers / apps | 10.10.40.0/24 | 10.10.40.2 |
| 50 | Lab / test | 10.10.50.0/24 | 10.10.50.2 |
| 60 | DMZ / public-facing | 10.10.60.0/24 | 10.10.60.2 |
| 99 | Infrastructure management | 10.99.99.0/24 | 10.99.99.2 |

## First Codex action

Create a safe implementation plan without applying changes.

The plan should include:

1. Existing-config discovery commands for:
   - Proxmox
   - FortiGate
   - Cisco C9300
2. Candidate diff approach.
3. Step-by-step apply order.
4. Validation commands.
5. Rollback plan.
6. Questions only where data is truly missing.

## Context7 usage

Use Context7 to verify:

- Proxmox VE SDN VLAN Zone, VNet, and Subnet API or CLI usage.
- Cisco IOS XE Catalyst 9300 VLAN trunk and SVI syntax.
- FortiGate VLAN subinterface syntax for FortiOS version in use, if known.

## MCP execution rules

If Proxmox MCP is available:

- Read existing SDN config before writing.
- Create only missing SDN objects.
- Do not delete existing objects unless explicitly asked.
- Apply SDN only after generating a plan.

If Cisco IOS XE MCP is available:

- Read running config first.
- Preserve existing allowed VLANs unless instructed to replace them.
- Use candidate/diff/check mode if supported.
- Save config only after validation passes.

If FortiGate MCP is available:

- Read current interface config first.
- Confirm parent interface before creating VLAN interfaces.
- Create firewall policies separately from interface creation.
- Avoid exposing management access broadly.

## Deliverable expected from Codex

Produce one of these:

- a pull request with improved, tested configuration files, or
- a written implementation plan with exact commands and validation steps, or
- a generated automation script that is idempotent and safe by default.

## Do not

- Do not assume the FortiGate parent interface is definitely `internal`.
- Do not apply destructive changes.
- Do not save network-device configs before validation.
- Do not remove VLANs from existing trunks without preserving current production VLANs.
