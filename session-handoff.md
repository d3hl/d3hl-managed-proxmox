# Session Handoff - d3hl-managed-proxmox

Last Updated: 2026-06-13

## Current Objective

Active feature: `proxmox-tf-vm-001` (in_progress) — first Terraform module in the repo, a bpg/proxmox clone-based VM on VM_SERVICES (VLAN 30, vsvc). Offline-validated; live apply is gated.

Recommended Next Step: to finish the feature, run a gated live plan/apply on the cluster (requires 1Password-injected API token and an operator-approved apply gate under `live_apply_gated`):
`export TF_VAR_proxmox_api_token="$(op read 'op://d3HLPRV/Proxmox API for AI/username')=$(op read 'op://d3HLPRV/Proxmox API for AI/credential')"` then `op run -- terraform -chdir=terraform/proxmox-vm plan -var="template_vm_id=<id>"`. Record the VM-created evidence, then flip the feature to `passing`.

## Current State

- Cisco C9300 live configuration has been validated and saved.
- Proxmox SDN/API validation is complete.
- FortiGate VLAN gateways, policies, repo-live verification, and persistent save are complete.
- QEMU guest agent on VM `444` / `sg-hl-vm01` remains unavailable, so in-guest gateway ping is not automatable; L3/L2 E2E is proven externally.
- 2026-06-13 first Terraform added under `terraform/proxmox-vm/` (bpg/proxmox ~> 0.107, resolved 0.109.0). `fmt -check`, `init -backend=false`, and `validate` pass; `./init.sh` runs the guarded Terraform step. No secrets in repo; op:// token references injected at runtime. Live plan/apply gated under `live_apply_gated`; no `terraform destroy` in scope.

## Files

- `AGENTS.md`
- `feature_list.json`
- `claude-progress.md`
- `session-handoff.md`
- `init.sh`
- `data/network-plan.json`
- `docs/fortigate-e2e-validation.md`
- `terraform/proxmox-vm/` (providers.tf, variables.tf, main.tf, outputs.tf, terraform.tfvars.example, .terraformignore)

## Historical Network Evidence

Earlier Cisco validation state:

Validated Cisco state:

- Management SVI: `Vlan10`, `10.10.10.1/24`
- Default gateway: `10.10.10.2`
- FortiGate trunk: `TwentyFiveGigE2/1/2`, allowed VLANs `10,11,30,40,50,60,100` in running-config
- Node trunks:
  - `TenGigabitEthernet2/0/39`, allowed VLANs `3,10,11`
  - `TenGigabitEthernet2/0/41`, allowed VLANs `3,10,11`
  - `TenGigabitEthernet2/0/46`, allowed VLANs `3,10,11`
- VLAN names now match repo intent:
  - `10 PROXMOX_MGMT`
  - `20 STORAGE_CEPH`
  - `30 VM_SERVICES`
  - `40 CONTAINERS_APPS`
  - `50 LAB_TEST`
  - `60 DMZ`
  - `99 INFRA_MGMT`
- Interface descriptions now match `configs/cisco-c9300-iosxe.cfg`.
- Cisco validation ping succeeded: `ping 10.10.10.2 source vlan10` returned `5/5`.

## Source Of Truth

Use these files first:

- `AGENTS.md`
- `data/network-plan.json`
- `configs/proxmox-sdn-pvesh.sh`
- `docs/safe-implementation-runbook.md`
- `docs/validation-checklist.md`
- `docs/1password-secrets.md`

`data/network-plan.json` now includes VLAN names, gateway ownership, and Cisco trunk descriptions.

## DeepSeek Next Task: Proxmox

Continue with read-only Proxmox discovery before any mutation:

```bash
bash configs/proxmox-sdn-pvesh.sh discover
bash configs/proxmox-sdn-pvesh.sh plan
```

Manual validation equivalents:

```bash
pvesh get /cluster/sdn
pvesh get /cluster/sdn/zones
pvesh get /cluster/sdn/vnets
pvesh get /cluster/sdn/subnets || true
ip -br link | grep -E 'vmgmt|vstore|vsvc|vapps|vlab|vdmz'
bridge vlan show
```

Target Proxmox SDN:

- Zone: `ztrunk`
- Type: VLAN
- Bridge: `vmbr0`
- VNets:
  - `vmgmt`, VLAN 10, subnet `10.10.10.0/24`, gateway `10.10.10.2`
  - `vstore`, VLAN 20, subnet `10.20.20.0/24`, no FortiGate gateway
  - `vsvc`, VLAN 30, subnet `10.10.30.0/24`, gateway `10.10.30.2`
  - `vapps`, VLAN 40, subnet `10.10.40.0/24`, gateway `10.10.40.2`
  - `vlab`, VLAN 50, subnet `10.10.50.0/24`, gateway `10.10.50.2`
  - `vdmz`, VLAN 60, subnet `10.10.60.0/24`, gateway `10.10.60.2`

Do not create `vinfra` or any VLAN 99 Proxmox VNet unless explicitly requested.

## Credentials

Use 1Password vault `d3HLPRV`.

Do not write plaintext secrets into files, prompts, logs, or handoff notes.
Follow `docs/1password-secrets.md`.

## Blockers

- None for the tracked network close-out features.
- VM `444` guest-agent access is still unavailable; do not rely on in-guest command execution for validation until that is fixed.

## Risks

- Node names confirmed: `nodeA, nodeB, nodeD, nodeF`.
- `vmbr0` is OVS, not a Linux bridge, and is natively VLAN-aware.
- `nodeF` uses `sfp1` for the `vmbr0` trunk; VLAN 3 uses dedicated `vmbr3` / `nic4`.
- Do not run live apply or persistent-save commands without explicit user approval and fresh verification.

## Applied State (2026-05-28 — synced from live)

### SDN
- Zone: `ztrunk` (vlan, bridge=vmbr0) ✅
- VNets: `vmgmt`(10), `vstore`(20), `vsvc`(30), `vapps`(40), `vlab`(50), `vdmz`(60) ✅
- Subnets: VLAN 10 and VLANs 30,40,50,60 use FortiGate .2 gateways; VLAN 20 is storage-side only ✅
- SDN applied cluster-wide ✅

### OVS Trunks (synced from live)
| Node | Port | Trunk VLANs | Bridge |
|---|---|---|---|
| nodeA | en10basep2 | 3,10,11,30,40,50,60 | vmbr0 |
| nodeB | ennic1s1 | 3,10,11,30,40,50,60 | vmbr0 |
| nodeD | eno1 | 3,10,11,30,40,50,60 | vmbr0 |
| nodeF | sfp1 | 10,11,30,40,50,60 | vmbr0 |

### OVS Bridges
| Bridge | Purpose | Nodes |
|---|---|---|
| vmbr0 | Management / VM trunk | all 4 |
| vmbr20 | Ceph storage (MTU 9000) | all 4 |
| vmbr3 | Quorum / VLAN 3 | nodeF only |

### Node Management IPs
| Node | IP | Gateway |
|---|---|---|
| nodeA | 10.10.10.18 | 10.10.10.2 |
| nodeB | 10.10.10.15 | 10.10.10.2 |
| nodeD | 10.10.10.17 | 10.10.10.2 |
| nodeF | 10.10.10.10 | 10.10.10.2 |

## Next Session

Start command:

```bash
cd /home/d3/Github/d3hl-managed-proxmox
./init.sh
```

Recommended Next Step: after baseline passes, choose any newly added feature from `feature_list.json` and keep work to that feature.
