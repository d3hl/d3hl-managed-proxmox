# Multi-Agent Contract: Codex + DeepSeek + Composer

This contract defines how Codex, DeepSeek, and Composer collaborate on the Homelab Proxmox SDN Design project. It keeps implementation ownership clear and prevents multiple agents from changing the same network domain at the same time.

## Agent Roles

### Codex

Codex is the planning and architecture agent pipeline.

Codex owns:

- Overall architecture and source-of-truth alignment.
- Cisco C9300 implementation artifacts.
- Safety gates, rollback structure, and handoff review.
- Final cross-domain change approval before live execution.

Codex must not:

- Apply Proxmox SDN changes when DeepSeek is assigned that implementation.
- Apply FortiGate changes when Composer is assigned that implementation.
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

- Modify Cisco or FortiGate candidate configs.
- Create `vinfra` or any VLAN 99 Proxmox VNet unless explicitly requested.
- Apply Proxmox SDN before `vmbr0` is confirmed VLAN-aware on all nodes.
- Continue after validation failure without documenting the failed command, observed state, and proposed rollback or fix.

### Composer

Composer is the strict FortiGate 100F implementation agent.

Composer owns:

- FortiGate 100F discovery, candidate diffs, implementation, and FortiGate-only validation.
- FortiGate implementation artifacts under `ansible/`, `configs/fortigate-*`, and FortiGate-specific docs.
- FortiGate interface and policy work for `fortigate-001`, including routed VLANs `30`, `40`, `50`, and `60`.
- Evidence capture for FortiGate API/CLI checks, without recording secret values.

Composer must not:

- Modify Cisco C9300 configuration, Proxmox SDN configuration, VM/CT NICs, or non-FortiGate docs unless the handoff explicitly requests a documentation update.
- Create a FortiGate VLAN 20 interface; VLAN 20 remains storage-side only.
- Create or recreate VLAN 99 as a FortiGate VLAN interface; VLAN 99 remains on the existing `mgt` hard-switch.
- Rename or replace existing live FortiGate interfaces `hlvl`, `mgt`, `k8s`, or `Wifi` unless a reviewed migration plan explicitly authorizes it.
- Change the FortiGate parent trunk away from verified parent `x2` without fresh discovery and Codex review.
- Save or persist FortiGate configuration before validation passes and Codex approves the persistent save step.
- Continue after a FortiGate validation failure without documenting the failed command, observed state, and rollback or fix recommendation.

## Pipeline

### Phase 1: Shared Discovery

Both agents start from the same source files:

- `AGENTS.md`
- `CODEX_TASK.md`
- `README.md`
- `data/network-plan.json`
- `docs/1password-secrets.md`
- `docs/safe-implementation-runbook.md`
- `docs/validation-checklist.md`

Discovery is read-only. No agent applies changes in this phase.

Credentials come only from 1Password vault `d3HLPRV`. Agents must use secret references or short-lived `op run`/environment injection and must never record plaintext credential values in handoff notes.

Required outputs:

- Current Proxmox SDN state.
- Current Cisco VLAN, trunk, SVI, and routing state.
- Current FortiGate interface and parent trunk state.
- List of conflicts against `data/network-plan.json`.

### Phase 2: Codex Cisco Implementation

Codex prepares and reviews:

- `configs/cisco-c9300-iosxe.cfg`

Codex implementation rules:

- Cisco trunk changes use `switchport trunk allowed vlan add ...`.
- Cisco management is reached at `10.10.10.1` on VLAN 10.
- Do not change Cisco inter-VLAN routing behavior or SVI inventory without an explicit reviewed plan.
- Cisco credentials must be retrieved through 1Password vault `d3HLPRV`; do not embed them in configs.

Codex handoff to Composer and DeepSeek:

- Confirmed Cisco diff.
- Cisco validation outputs.
- Any known deviations or blocked items.

### Phase 3: Composer FortiGate Implementation

Composer uses:

- `ansible/group_vars/fortigates.yml`
- `ansible/playbooks/fortigate/discover.yml`
- `ansible/playbooks/fortigate/render-vlan-plan.yml`
- `ansible/playbooks/fortigate/apply-vlan-interfaces.yml`
- `configs/fortigate-api-verify.py`
- `configs/fortigate-api-apply-vlans.py`
- `docs/fortigate-ansible-runbook.md`

Composer implementation order:

0. Confirm 1Password access before credentialed FortiGate work:
   ```bash
   op --version
   op account list
   ```
1. Read live FortiGate state before mutation:
   ```bash
   op run -- python configs/fortigate-api-verify.py
   ```
2. Confirm the FortiGate API endpoint is `https://10.99.99.2:7443`.
3. Confirm parent interface `x2`, existing VLAN 10 interface `hlvl`, existing VLAN 99 hard-switch `mgt`, and existing VLANs `k8s` and `Wifi`.
4. Confirm the C9300-to-FortiGate trunk already carries `10,11,30,40,50,60,100` before FortiGate mutation.
5. Render or produce a candidate FortiGate diff before applying.
6. Apply only FortiGate-scoped changes with both gates present:
   ```bash
   CONFIRM_FORTIGATE_APPLY=yes CONFIRM_FORTIGATE_TRUNK_REVIEW=yes op run -- python configs/fortigate-api-apply-vlans.py
   ```
7. Validate FortiGate state after apply:
   ```bash
   op run -- python configs/fortigate-api-verify.py
   ```

Composer may implement FortiGate firewall policies only after a separate policy plan is recorded. VLAN interface creation and firewall policy creation are separate tasks.

### Phase 4: DeepSeek Proxmox Implementation

DeepSeek uses:

- `configs/proxmox-sdn-pvesh.sh`
- `docs/safe-implementation-runbook.md`

DeepSeek implementation order:

0. Confirm 1Password access if credentialed Proxmox access is needed:
   ```bash
   op --version
   op account list
   ```
1. Run Proxmox discovery:
   ```bash
   bash configs/proxmox-sdn-pvesh.sh discover
   ```
2. Generate the planned Proxmox commands:
   ```bash
   bash configs/proxmox-sdn-pvesh.sh plan
   ```
3. Confirm `vmbr0` is VLAN-aware on `nodeA`, `nodeB`, `nodeD`, and `nodeF`.
4. Create only missing SDN objects:
   ```bash
   CONFIRM_PROXMOX_SDN_APPLY=yes bash configs/proxmox-sdn-pvesh.sh apply
   ```
5. Review the created objects.
6. Apply SDN cluster-wide only after review:
   ```bash
   APPLY_PROXMOX_SDN=yes CONFIRM_PROXMOX_SDN_APPLY=yes bash configs/proxmox-sdn-pvesh.sh apply
   ```

### Phase 5: DeepSeek End-to-End Validation

DeepSeek validates all domains and reports results back to Codex and Composer.

Cisco:

```cisco
show vlan brief
show interfaces trunk
show ip interface brief
show running-config interface vlan10
ping 10.10.10.2 source vlan10
```

FortiGate:

```text
show system interface
get system interface
execute ping-options source 10.10.10.2
execute ping 10.10.10.1
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

### Phase 6: Codex Final Review

Codex reviews Composer and DeepSeek validation evidence before persistent saves.

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
Credential source:
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
- If two agents propose changes to the same domain, Codex resolves ownership before execution.
- Composer is the only agent assigned to FortiGate implementation while this contract is active.
- If management reachability is at risk, stop before applying and require manual confirmation.

## Completion Criteria

The multi-agent task is complete only when:

- Cisco carries the required VLANs without pruning unrelated trunk VLANs.
- FortiGate owns VLAN 10 as live interface `hlvl` and candidate gateway interfaces for VLANs 30,40,50,60 on confirmed parent trunk `x2`.
- VLAN 20 remains on the C9300/storage side and is not routed to the FortiGate.
- Proxmox SDN zone `ztrunk` and VNets `vmgmt`, `vstore`, `vsvc`, `vapps`, `vlab`, and `vdmz` exist.
- VLAN 99 is not created as a Proxmox VNet.
- Validation succeeds across all three platforms.
- Rollback notes and final discovered state are recorded.
