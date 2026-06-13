# Finding Discovery Report

## Coverage

Reviewed repository-owned source, config, docs, Ansible intent, MCP code, wrappers, and tracked artifacts. Local virtualenv/vendor trees, generated caches, and binary sprite assets were excluded as not applicable to repo-owned security logic.

Parent sweeps performed:

- Secret-pattern sweep: `grep -RInEi 'password|passwd|token|secret|api[_-]?key|private key|BEGIN .*KEY|op://|OP_SERVICE_ACCOUNT_TOKEN|FORTIOS_ACCESS_TOKEN'`
- Dangerous sink sweep: `grep -RInE 'subprocess|os\.system|shell=True|exec\(|eval\(|requests\.|httpx\.|verify=False|paramiko|ConnectHandler|send_config_set|save_config|write memory|pvesh|curl|ssh|scp|rm -rf'`
- Mutation-gate sweep: `grep -RInE 'CONFIRM_|apply|persist|save|write|delete|remove|set_|post\(|put\(|delete\('`

## Candidates

One reportable candidate was discovered:

- `CS-001`: tracked FortiGate config backup exposes encrypted private keys and credential material.

## Suppressed Or Closed Rows

- Device mutation gates: FortiGate apply, policy apply, persistent-save, Cisco trunk apply, Cisco write-memory, Proxmox SDN shell apply, Ansible FortiGate apply, and service-account creation paths all expose explicit `CONFIRM_*` gates in the reviewed grep output.
- Command execution: MCP SSH execution builds argv lists for fixed command names rather than shell strings; no `shell=True`, `eval`, or `os.system` candidate survived the sink sweep.
- Secret references in docs and wrappers are mostly `op://` references and documented as not plaintext values.
- `configs/test-px-auth.*` prints token prefix and length and disables TLS verification. These are local diagnostic helpers, not live production automation; this remains a secondary hygiene issue, not promoted as a high-impact finding in this scan.
