# Repository Coverage Ledger

| Row | Surface | Family | Disposition | Evidence |
|---:|---|---|---|---|
| 1 | `configs/` automation | command injection, unsafe mutation, secrets | open | assigned to discovery subagent A |
| 2 | `mcp/`, Ansible, tracked artifacts | MCP input/authz, unsafe intent, secret leakage | open | assigned to discovery subagent B |
| 3 | `data/`, docs, static configs | committed secrets, unsafe runbook, sensitive disclosure | open | assigned to discovery subagent C |
| 4 | `__pycache__`, `*.pyc`, binary assets | generated/non-source | not_applicable | generated cache or binary asset excluded from source review |
| 5 | local virtualenv trees | vendored third-party dependencies | not_applicable | not tracked in git-owned scan scope |
