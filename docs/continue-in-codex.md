# Continue in Codex

This folder is prepared for OpenAI Codex or Codex CLI.

## Recommended flow

1. Extract this bundle.
2. Put the folder under Git.
3. Open the folder in Codex.
4. Ask Codex to read:
   - `AGENTS.md`
   - `CODEX_TASK.md`
   - `README.md`
   - `data/network-plan.json`
   - `docs/multi-agent-deepseek-contract.md`

## Suggested first prompt for Codex

```text
Read AGENTS.md and CODEX_TASK.md first.

Continue the Homelab Proxmox SDN Design project.

Do not apply changes yet.

Create a safe implementation plan for:
- Proxmox VE SDN VLAN Zone and VNets
- Cisco C9300 L2 core switch config
- FortiGate 100F VLAN interfaces using .2 gateway addresses

Use Context7 MCP for latest Proxmox, Cisco IOS XE, and FortiGate/FortiOS documentation if available.

If Proxmox MCP or Cisco IOS XE MCP is available, only perform read-only discovery first.
Return:
1. discovered current state,
2. diff from target design,
3. apply plan,
4. validation commands,
5. rollback plan.
```

## Optional local Git setup

```bash
cd homelab-proxmox-sdn-design
git init
git add .
git commit -m "Initial homelab Proxmox SDN design handoff"
```

## Files of interest

- `AGENTS.md` — persistent project instructions for Codex/agents.
- `CODEX_TASK.md` — first task prompt and execution constraints.
- `configs/` — candidate device configs and Proxmox scripts.
- `docs/context7-prompts.md` — prompts for Context7-backed MCP execution.
- `docs/multi-agent-deepseek-contract.md` — Codex and DeepSeek ownership, handoff, and validation contract.
- `docs/safe-implementation-runbook.md` — safe implementation sequence.
- `docs/validation-checklist.md` — validation and safety checklist.
- `data/network-plan.json` — machine-readable source of truth.
