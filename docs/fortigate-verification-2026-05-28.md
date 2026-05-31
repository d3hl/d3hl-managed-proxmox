# FortiGate Verification - 2026-05-28

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

## API Verification Result - Initial Attempt

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

Initial attempt was blocked. The FortiGate was reachable by ICMP, and SSH was reachable on `10.10.10.2`, but REST API verification could not proceed on the default HTTPS ports.

## API Verification Result - Corrected Port

The FortiGate API was successfully reached at:

```text
https://10.99.99.2:7443
```

Read-only interface verification returned:

| Check | Result |
|---|---:|
| Interfaces seen | 41 |
| Target interfaces | 7 |
| Exact matches | 0 |
| Present with different name | 1 |
| IP conflicts / different type | 1 |
| Missing | 5 |
| Mismatches | 0 |

Existing VLAN interfaces:

| Interface | VLAN | Parent | IP | Access | Status |
|---|---:|---|---|---|---|
| `hlvl` | 10 | `x2` | `10.10.10.2/24` | `ping https ssh snmp fgfm fabric` | up |
| `k8s` | 11 | `x2` | `10.11.11.2/24` | `ping` | up |
| `Wifi` | 100 | `x2` | `10.100.100.2/24` | `ping` | up |

Target comparison:

| Target | Status | Live object |
|---|---|---|
| `VLAN10_PROXMOX_MGMT` | Present with different name | `hlvl`, VLAN 10, parent `x2`, `10.10.10.2/24` |
| `VLAN20_STORAGE_CEPH` | Missing | none |
| `VLAN30_VM_SERVICES` | Missing | none |
| `VLAN40_CONTAINERS_APPS` | Missing | none |
| `VLAN50_LAB_TEST` | Missing | none |
| `VLAN60_DMZ` | Missing | none |
| `VLAN99_INFRA_MGMT` | IP conflict / different type | `mgt` hard-switch, `10.99.99.2/24` |

Verified parent trunk interface for VLAN gateways: `x2`.

## Current Verification Status

Current FortiGate config was verified read-only. It does not yet match the repo target:

- VLAN 10 exists, but under live name `hlvl` instead of target name `VLAN10_PROXMOX_MGMT`.
- VLANs 20, 30, 40, 50, and 60 are missing.
- VLAN 99 should not be blindly created because `10.99.99.2/24` is already assigned to `mgt` hard-switch.

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
