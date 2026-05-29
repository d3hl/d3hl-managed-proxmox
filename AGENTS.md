# AGENTS.md

This repository is designed for long-running coding-agent work. The goal is not to maximize raw code output. 
The goal is to leave the repo in a state where the next session can continue without guessing.

## Startup Workflow

Before writing code:

1. Confirm the working directory with `pwd`.
2. Read `claude-progress.md` for the latest verified state and next step.
3. Read `feature_list.json` and choose the highest-priority unfinished feature.
4. Review recent commits with `git log --oneline -5`.
5. Run `./init.sh`.
6. Run the required smoke or end-to-end verification before starting new work.

If baseline verification is already failing, fix that first. Do not stack new
feature work on top of a broken starting state.

## Working Rules

- Work on one feature at a time.
- Do not mark a feature complete just because code was added.
- Keep changes within the selected feature scope unless a blocker forces a
  narrow supporting fix.
- Do not silently change verification rules during implementation.
- Prefer durable repo artifacts over chat summaries.

## Required Artifacts

- `feature_list.json`: source of truth for feature state
- `claude-progress.md`: session log and current verified status
- `init.sh`: standard startup and verification path
- `session-handoff.md`: optional compact handoff for larger sessions

## Definition Of Done

A feature is done only when all of the following are true:

- the target behavior is implemented
- the required verification actually ran
- evidence is recorded in `feature_list.json` or `claude-progress.md`
- the repository remains restartable from the standard startup path

## End Of Session

Before ending a session:

1. Update `claude-progress.md`.
2. Update `feature_list.json`.
3. Record any unresolved risk or blocker.
4. Commit with a descriptive message once the work is in a safe state.
5. Leave the repo clean enough for the next session to run `./init.sh`
   immediately.

## Project

Homelab Proxmox SDN Design.

The goal is to maintain a practical VLAN-based homelab network using:

- Proxmox VE SDN
- FortiGate 100F as the main firewall and VLAN gateway
- Cisco Catalyst C9300 as the L3 core switch
- VLAN trunking to Proxmox nodes
- Isolated networks for management, storage, VM services, apps, lab, DMZ, and infrastructure management

## Current design assumptions

### Devices

| Device | Role | IP |
|---|---|---|
| FortiGate 100F | Main firewall and VLAN gateway | 10.99.99.2/24 on VLAN 99 |
| Cisco C9300 | Core L3 switch | 10.10.10.1/24 on VLAN 10 |
| Proxmox nodes | Virtualization hosts | nodeA, nodeB, nodeD, nodeF |

### Routing model

FortiGate owns the gateway IP for VLAN 10 and the approved routed VLANs 30, 40, 50, and 60.
VLAN 20 remains on the C9300/storage side and is not routed to the FortiGate.
VLAN 99 remains on the FortiGate `mgt` hard-switch and must not be recreated as a VLAN interface.

Use `.2` for FortiGate routed interfaces:

| VLAN | Purpose | Subnet | Gateway |
|---:|---|---|---|
| 10 | Proxmox management | 10.10.10.0/24 | 10.10.10.2 |
| 20 | Storage / Ceph | 10.20.20.0/24 | none on FortiGate |
| 30 | VM services | 10.10.30.0/24 | 10.10.30.2 |
| 40 | Containers / apps | 10.10.40.0/24 | 10.10.40.2 |
| 50 | Lab / test | 10.10.50.0/24 | 10.10.50.2 |
| 60 | DMZ / public-facing | 10.10.60.0/24 | 10.10.60.2 |
| 99 | Infrastructure management | 10.99.99.0/24 | 10.99.99.2 on `mgt` hard-switch |

Cisco C9300 is reached for management at `10.10.10.1` on VLAN 10. Do not remove or change existing SVIs without a reviewed migration plan.

## Proxmox SDN target

Use a VLAN Zone.

- Zone ID: `ztrunk`
- Type: VLAN
- Bridge: `vmbr0`
- Nodes: `nodeA,nodeB,nodeD,nodeF`

VNets:

| VNet | VLAN | Subnet | Gateway |
|---|---:|---|---|
| vmgmt | 10 | 10.10.10.0/24 | 10.10.10.2 |
| vstore | 20 | 10.20.20.0/24 | none on FortiGate |
| vsvc | 30 | 10.10.30.0/24 | 10.10.30.2 |
| vapps | 40 | 10.10.40.0/24 | 10.10.40.2 |
| vlab | 50 | 10.10.50.0/24 | 10.10.50.2 |
| vdmz | 60 | 10.10.60.0/24 | 10.10.60.2 |

Do not create `vinfra` / VLAN 99 in Proxmox unless explicitly requested.

## Cisco C9300 target

FortiGate trunk:

- Interface: `TwentyFiveGigE2/1/2`
- Allowed VLANs: `10,11,30,40,50,60,100`

Proxmox trunks:

- Interfaces: `TenGigabitEthernet2/0/39`, `TenGigabitEthernet2/0/41`, `TenGigabitEthernet2/0/46`
- Allowed VLANs: `3,10,11`

Do not allow VLAN 99 to Proxmox trunks unless explicitly requested.

## FortiGate target

Parent interface is verified as `x2`.

Adopt the live FortiGate interface names:

- VLAN 10 gateway is existing interface `hlvl` on `x2`.
- VLAN 99 management is existing hard-switch `mgt`.
- VLAN 20 is not a FortiGate routed interface.
- Add only missing VLAN interfaces `30`, `40`, `50`, and `60` after reviewing the C9300-to-FortiGate trunk.

New VLAN interfaces should be created under parent interface `x2`.

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

## Secrets and credentials

Use 1Password for all live credentials and secrets.

- Vault: `d3HLPRV`
- Follow `docs/1password-secrets.md`.
- Prefer 1Password secret references and `op run` scoped environment injection.
- Never store plaintext credentials, tokens, SSH keys, service account secrets, or exported `.env` files in this repository.
- Never paste secret values into agent prompts, markdown, handoff notes, or validation output.
- Do not use `op run --no-masking`.
- If a required 1Password item or field is missing, report the missing reference path only.

## Validation commands

### Cisco IOS XE

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
pvesh get /cluster/sdn
pvesh get /cluster/sdn/zones
pvesh get /cluster/sdn/vnets
ip -br link | grep -E 'vmgmt|vstore|vsvc|vapps|vlab|vdmz'
bridge vlan show
```

## Do not do

- Do not change C9300 inter-VLAN routing behavior unless the design changes.
- Do not create or remove C9300 SVIs without an explicit reviewed plan.
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
