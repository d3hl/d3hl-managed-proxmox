# Codex Security Scan Report

Repository: `/home/d3/Github/d3hl-managed-proxmox`

Scan ID: `c5bf0c6_20260606T201348Z`

## Summary

The repo-wide scan found one reportable security issue.

| ID | Severity | Title |
|---|---|---|
| CS-001 | High | Tracked FortiGate config backup exposes encrypted private keys and credential material |

## Finding CS-001: Tracked FortiGate Backup Contains Sensitive Credential Material

Severity: High

Affected file:

- `ansible/artifacts/fortigate-config-backup.conf`

Evidence:

- Line 461 contains an encrypted FortiGate API key.
- Lines 9094, 9155, 9216, 9276, and 9367 contain encrypted password material.
- Lines 9096, 9157, 9218, 9278, and 9369 begin encrypted private-key blocks.
- Lines 10226-10227 show saved-password behavior and encrypted PSK material.
- `git check-ignore -v` shows `ansible/artifacts/` is ignored, but `git ls-files` still lists `ansible/artifacts/fortigate-config-backup.conf`, so the ignored live backup remains tracked.

Impact:

Anyone with repository access can obtain a full FortiGate backup containing encrypted credential, private-key, certificate, VPN, and firewall configuration material. Encryption reduces immediate exploitability, but this is still sensitive device backup data and should be treated as exposed.

Recommended remediation:

1. Remove `ansible/artifacts/fortigate-config-backup.conf` from the tracked tree.
2. Purge it from git history if the repository has been shared beyond this workstation.
3. Rotate or reissue affected FortiGate API keys, VPN PSKs, local certificate/private-key material, and any backup-contained secrets as operationally appropriate.
4. Keep generated backups outside the repository or store only redacted backups.

## Closed Coverage Rows

- Device automation: closed as suppressed. Mutating scripts expose explicit `CONFIRM_*` gates, and no shell-eval sink survived the parent sweep.
- MCP boundary: no reportable arbitrary command execution was promoted; commands are fixed command names passed via argv. This row remains covered by the scan notes and suppressed except for the artifact leak in the same broader slice.
- Docs/static intent: closed as suppressed. Secret references are `op://` pointers and the docs explicitly forbid plaintext secret commits.
- Generated caches/binary assets and virtualenv/vendor trees: not applicable.

## Verification Notes

Baseline `./init.sh` completed its dependency sync and JSON validation output before the surrounding Windows PowerShell process emitted an unrelated WinGet command-not-found predictor exception. The scan used WSL-side grep and line-numbered reads for current-worktree evidence.

Subagents were authorized and dispatched, but did not return before timeout. Parent-owned discovery, validation, and attack-path receipts are recorded in the scan artifacts.
