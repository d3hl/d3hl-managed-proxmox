# Repository Coverage Ledger

| Row | Surface | Family | Disposition | Evidence |
|---:|---|---|---|---|
| 1 | `configs/` automation | command injection, unsafe mutation, secrets | suppressed | parent sink/gate sweep found explicit `CONFIRM_*` gates on mutating scripts; no shell-eval sink survived review; token-prefix test helpers are local diagnostics |
| 2 | `mcp/`, Ansible, tracked artifacts | MCP input/authz, unsafe intent, secret leakage | reportable | `CS-001` covers tracked FortiGate backup secret material; Ansible apply paths have confirmation gates |
| 3 | `data/`, docs, static configs | committed secrets, unsafe runbook, sensitive disclosure | suppressed | docs use `op://` references and warn against plaintext secrets; no unsafe VLAN 99/VLAN20 runbook violation promoted |
| 4 | `__pycache__`, `*.pyc`, binary assets | generated/non-source | not_applicable | generated cache or binary asset excluded from source review |
| 5 | local virtualenv trees | vendored third-party dependencies | not_applicable | not tracked in git-owned scan scope |
