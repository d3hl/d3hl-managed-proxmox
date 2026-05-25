# Multi-Agent Contract: Codex + DeepSeek

This contract defines how Codex and DeepSeek collaborate on the Homelab Proxmox SDN Design project. It keeps implementation ownership clear and prevents both agents from changing the same network domain at the same time.

## Agent Roles

### Codex

Codex is the planning and architecture agent pipeline.

Codex owns:

- Overall architecture and source-of-truth alignment.
- Cisco C9300 implementation artifacts.
- FortiGate 100F implementation artifacts.
- Safety gates, rollback structure, and handoff review.
- Final cross-domain change approval before live execution.

Codex must not:

- Apply Proxmox SDN changes when DeepSeek is assigned that implementation.
- Remove existing Cisco trunk VLANs unless explicitly approved.
- Assume the FortiGate parent interface is `internal`.
- Save Cisco or FortiGate persistent config before validation passes.

### DeepSeek

DeepSeek is the implementation and validation agent for the full pipeline, with direct implementation ownership for Proxmox.

DeepSeek owns:

- Proxmox VE SDN implementation.
- Proxmox discovery, diff, apply, and validation output.
- End-to-end validation evidence across Proxmox, Cisco, and FortiGate after Codex-owned network changes are staged.
- Reporting mismatches back to Codex before any corrective mutation.

DeepSeek must not:

- Modify Cisco or FortiGate candidate configs without Codex review.
- Create `vinfra` or any VLAN 99 Proxmox VNet unless explicitly requested.
- Apply Proxmox SDN before `vmbr0` is confirmed VLAN-aware on all nodes.
- Continue after validation failure without documenting the failed command, observed state, and proposed rollback or fix.

## Pipeline

### Phase 1: Shared Discovery

Both agents start from the same source files:

- `AGENTS.md`
- `CODEX_TASK.md`
- `README.md`
- `data/network-plan.json`
- `docs/safe-implementation-runbook.md`
- `docs/validation-checklist.md`

Discovery is read-only. No agent applies changes in this phase.

Required outputs:

- Current Proxmox SDN state.
- Current Cisco VLAN, trunk, SVI, and routing state.
- Current FortiGate interface and parent trunk state.
- List of conflicts against `data/network-plan.json`.

### Phase 2: Codex Cisco and FortiGate Implementation

Codex prepares and reviews:

- `configs/cisco-c9300-iosxe.cfg`
- `configs/fortigate-100f-vlan-cli.conf`

Codex implementation rules:

- Cisco trunk changes use `switchport trunk allowed vlan add ...`.
- Cisco remains L2-only; do not enable inter-VLAN routing.
- Only `interface Vlan99` is configured as an SVI.
- FortiGate parent interface must be discovered and substituted for `__CONFIRM_PARENT_INTERFACE__`.
- FortiGate firewall policies are separate from VLAN interface creation.

Codex handoff to DeepSeek:

- Confirmed Cisco diff.
- Confirmed FortiGate parent interface.
- Cisco and FortiGate validation outputs.
- Any known deviations or blocked items.

### Phase 3: DeepSeek Proxmox Implementation

DeepSeek uses:

- `configs/proxmox-sdn-pvesh.sh`
- `docs/safe-implementation-runbook.md`

DeepSeek implementation order:

1. Run Proxmox discovery:
   ```bash
   bash configs/proxmox-sdn-pvesh.sh discover
   ```
2. Generate the planned Proxmox commands:
   ```bash
   bash configs/proxmox-sdn-pvesh.sh plan
   ```
3. Confirm `vmbr0` is VLAN-aware on `pve01`, `pve02`, and `pve03`.
4. Create only missing SDN objects:
   ```bash
   CONFIRM_PROXMOX_SDN_APPLY=yes bash configs/proxmox-sdn-pvesh.sh apply
   ```
5. Review the created objects.
6. Apply SDN cluster-wide only after review:
   ```bash
   APPLY_PROXMOX_SDN=yes CONFIRM_PROXMOX_SDN_APPLY=yes bash configs/proxmox-sdn-pvesh.sh apply
   ```

### Phase 4: DeepSeek End-to-End Validation

DeepSeek validates all domains and reports results back to Codex.

Cisco:

```cisco
show vlan brief
show interfaces trunk
show ip interface brief
show running-config interface vlan99
ping 10.99.99.2 source vlan99
```

FortiGate:

```text
show system interface
get system interface
execute ping-options source 10.99.99.2
execute ping 10.99.99.1
```

Proxmox:

```bash
bash configs/proxmox-sdn-pvesh.sh validate
```

Validation report must include:

- Commands run.
- Pass/fail result.
- Relevant output snippets.
- Any difference from `data/network-plan.json`.
- Whether persistent save is recommended.

### Phase 5: Codex Final Review

Codex reviews DeepSeek validation evidence before persistent saves.

Codex approves:

- Cisco `write memory`.
- FortiGate persistent commit/save behavior, if required by the operating mode.
- Documentation updates for any real-world deviations.

## Handoff Format

Each handoff should include:

```text
Agent:
Phase:
Device/domain:
Files used:
Discovery summary:
Candidate diff:
Commands executed:
Validation result:
Blocked items:
Rollback notes:
Next owner:
```

## Conflict Rules

- If source files disagree, `data/network-plan.json` and `AGENTS.md` are authoritative.
- If live device state conflicts with repo intent, stop and report the conflict.
- If Codex and DeepSeek propose changes to the same domain, Codex resolves ownership before execution.
- If management reachability is at risk, stop before applying and require manual confirmation.

## Completion Criteria

The multi-agent task is complete only when:

- Cisco carries the required VLANs without pruning unrelated trunk VLANs.
- FortiGate owns all `.2` VLAN gateway interfaces on the confirmed parent trunk.
- Proxmox SDN zone `ztrunk` and VNets `vmgmt`, `vstore`, `vsvc`, `vapps`, `vlab`, and `vdmz` exist.
- VLAN 99 is not created as a Proxmox VNet.
- Validation succeeds across all three platforms.
- Rollback notes and final discovered state are recorded.
