# 1Password Secrets Standard

Use 1Password as the only supported source for live credentials and secrets in this project.

## Vault

- Vault name: `d3HLPRV`
- Do not store plaintext secrets in this repository.
- Do not paste secrets into Codex, DeepSeek, tickets, markdown files, terminal transcripts, or validation reports.
- If a command prints a secret, discard the transcript and rerun with masked output.

## Recommended Item Names

Use stable item names so Codex, DeepSeek, and Composer can reference credentials without knowing the secret values:

| Domain | Suggested item | Expected fields |
|---|---|---|
| Proxmox | `proxmox-cluster` | `username`, `password`, `host` |
| Cisco C9300 | `C9300` | `username`, `password`, `IP`; optional `enable_password` |
| FortiGate 100F | `fortigate-100f` | `username`, `password`, `host`, optional `access_token` |

If the real item names differ, document only the item names and field labels. Never document the values.

## Secret References

Prefer 1Password secret references over direct secret reads:

```bash
op://d3HLPRV/proxmox-cluster/username
op://d3HLPRV/proxmox-cluster/password
op://d3HLPRV/C9300/username
op://d3HLPRV/C9300/password
op://d3HLPRV/C9300/IP
op://d3HLPRV/fortigate-100f/username
op://d3HLPRV/fortigate-100f/password
op://d3HLPRV/fortigate-100f/access_token
```

Use `op read` only when a tool cannot consume a secret reference directly:

```bash
op read "op://d3HLPRV/proxmox-cluster/username"
```

## Runtime Injection

Prefer `op run` for commands that need credentials at runtime. It keeps secrets scoped to the subprocess.

Example pattern:

```bash
export PROXMOX_USER="op://d3HLPRV/proxmox-cluster/username"
export PROXMOX_PASSWORD="op://d3HLPRV/proxmox-cluster/password"
op run -- bash configs/proxmox-sdn-pvesh.sh discover
```

Do not use `op run --no-masking` in this project.

## Agent Rules

Codex, DeepSeek, and Composer must:

- Check that 1Password CLI is available before credentialed actions: `op --version`.
- Confirm the signed-in/account context without printing secrets.
- Use vault `d3HLPRV` for project credentials.
- Request only the minimum item and field required for the current task.
- Redact credential values from handoff notes.
- Stop if an expected item or field is missing and report the missing reference path only.

Codex, DeepSeek, and Composer must not:

- Commit `.env` files, exported secrets, service account tokens, SSH keys, API keys, passwords, or command output containing secrets.
- Use `--no-masking`.
- Store credentials in generated configs.
- Copy secrets from 1Password into prompts or markdown.

## Handoff Format

When credentials are needed, handoffs should identify references, not values:

```text
Credential source:
Vault: d3HLPRV
Item:
Fields required:
Secret references used:
Values printed: no
```

## WSL / Linux CLI Install

On Fedora WSL:

```bash
sudo rpm --import https://downloads.1password.com/linux/keys/1password.asc
sudo sh -c 'echo -e "[1password]\nname=1Password Stable Channel\nbaseurl=https://downloads.1password.com/linux/rpm/stable/\$basearch\nenabled=1\ngpgcheck=1\nrepo_gpgcheck=1\ngpgkey=\"https://downloads.1password.com/linux/keys/1password.asc\"" > /etc/yum.repos.d/1password.repo'
sudo dnf install -y 1password-cli
op --version
```

Sign in once per shell session:

```bash
eval "$(op signin)"
# or, without the desktop app:
eval "$(op account add --signin)"
```

## Service Account (Headless / Agent Automation)

For Cursor agents and scripts that cannot use interactive sign-in, create a scoped service account with read access to the project vaults only:

- `d3HL`
- `d3HLPRV`
- `AI`

Recommended name: `d3hl-managed-proxmox-wsl`

After `eval "$(op signin)"`:

```bash
CONFIRM_OP_SERVICE_ACCOUNT_CREATE=yes bash configs/setup-1password-service-account.sh
```

Or create manually:

```bash
op service-account create "d3hl-managed-proxmox-wsl" \
  --vault d3HL:read_items \
  --vault d3HLPRV:read_items \
  --vault "AI Vault":read_items \
  --raw
```

Save the returned token in 1Password immediately. Use it at runtime only:

```bash
export OP_SERVICE_ACCOUNT_TOKEN='op://d3HLPRV/d3hl-managed-proxmox-wsl/credential'
op run -- op vault list
```

Do not commit service account tokens, `.env` files, or command output containing token values.

## Preflight

Before any credentialed discovery or implementation:

```bash
op --version
op account list
```

Then verify only the needed item metadata or secret references. If field values must be read for a tool, read them into environment variables in the shortest possible scope and do not echo them.
