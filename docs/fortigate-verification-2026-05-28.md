# FortiGate Verification Attempt - 2026-05-28

Scope: read-only verification of current FortiGate interface configuration.

No live FortiGate configuration changes were attempted.

## Credential Sources Checked

- Vault: `d3HLPRV`
- Expected item from repo docs: `fortigate-100f`
- Result: item `fortigate-100f` was not found.
- Discovered likely API token item: `FORTIOS_ACCESS_TOKEN`
- Secret reference used for API probe: `op://d3HLPRV/FORTIOS_ACCESS_TOKEN/credential`
- Secret values printed: no

## Baseline

- `bash ./init.sh` passed before live verification.
- `op --version` succeeded.
- `op account list` confirmed the signed-in 1Password context.

## Reachability

| Target | ICMP | TCP/22 | TCP/443 | Notes |
|---|---|---:|---:|---|
| `10.99.99.2` | reachable | closed/filtered | closed/filtered | Documented VLAN 99 management IP, but admin services are not reachable from this workstation. |
| `10.10.10.2` | reachable | open | open | VLAN 10 gateway is reachable for SSH and has a listener on 443. |

SSH banner probe on `10.10.10.2:22` returned:

```text
SSH-2.0-eD_Z8
```

## API Verification Result

Read-only FortiGate API verification was attempted with:

- Host: `10.99.99.2`
- Host: `10.10.10.2`
- Endpoint: `/api/v2/cmdb/system/interface?vdom=root`
- Auth style: `Authorization: Bearer <1Password-injected token>`

Results:

- `10.99.99.2`: API connection timed out.
- `10.10.10.2`: TCP/443 is open, but TLS handshake fails before a certificate is presented.
- `curl -k https://10.10.10.2/` failed with TLS handshake failure.
- `openssl s_client` with TLS 1.2 and TLS 1.3 both reported unexpected EOF before receiving a peer certificate.

## Current Verification Status

Blocked. The FortiGate is reachable by ICMP, and SSH is reachable on `10.10.10.2`, but REST API verification cannot proceed until one of these is fixed:

- FortiGate HTTPS/API admin service is enabled and completes TLS on a reachable interface.
- The correct management IP/port for FortiGate API is documented.
- A usable SSH credential item is added to 1Password so verification can be performed by CLI.

## Next Safe Commands

From FortiGate console or an already trusted admin session:

```text
show system interface
show system admin
show system global
get system status
```

Confirm:

- Which interface allows `https` and/or `ssh`.
- Whether REST API admin is enabled for the token.
- Whether trusted hosts/local-in policy restrict API access from this workstation.
- The actual parent interface for VLAN gateways.
