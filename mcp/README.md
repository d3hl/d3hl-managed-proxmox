# Proxmox MCP Server

This directory contains a read-only MCP server for Proxmox VE discovery.

The server uses the official MCP Python SDK `FastMCP` pattern and exposes only
safe verification tools. It shells out to `ssh` with `BatchMode=yes`, so it
expects SSH keys, an SSH agent, or another non-interactive SSH setup. Do not
put passwords or tokens in this repository.

## Install

```bash
python -m pip install -r mcp/requirements.txt
```

## Run With 1Password

Use 1Password references and scoped runtime injection:

```bash
PROXMOX_USER="op://d3HLPRV/proxmox-cluster/username" \
PROXMOX_MCP_HOSTS="nodeA=10.10.10.18,nodeB=10.10.10.15,nodeD=10.10.10.17,nodeF=10.10.10.10" \
op run -- python mcp/proxmox_mcp_server.py
```

`PROXMOX_MCP_HOSTS` is optional. If omitted, the server uses the documented
node defaults above. `PROXMOX_USER` is required.

Optional SSH settings:

- `PROXMOX_SSH_KEY` - path to an SSH private key.
- `PROXMOX_SSH_PORT` - SSH port if not `22`.

## Tools

- `list_proxmox_nodes` - show configured node aliases and host addresses.
- `list_read_only_commands` - show approved command names.
- `run_read_only_command` - run one approved read-only command on one node.
- `discover_proxmox_node` - run the safe discovery bundle on one node.
- `discover_proxmox_cluster` - run the safe discovery bundle on all nodes.
- `render_op_run_example` - print a secret-safe launch example.

## Local Verification Client

To call a tool from this repo without configuring a separate MCP host yet:

```bash
PROXMOX_USER="op://d3HLPRV/proxmox-cluster/username" \
PROXMOX_MCP_HOSTS="nodeA=10.10.10.18,nodeB=10.10.10.15,nodeD=10.10.10.17,nodeF=10.10.10.10" \
op run -- python mcp/proxmox_mcp_client.py discover_proxmox_cluster
```

## Safety

The MCP server does not expose arbitrary shell execution. It only runs the
allowlisted read-only commands in `mcp/proxmox_mcp_server.py`.

It verifies:

- Proxmox version and node membership.
- SDN zones, VNets, and subnets.
- `/etc/network/interfaces`.
- Open vSwitch state via `ovs-vsctl show` when available.
- IP/link summary and bridge VLAN state.

Apply or mutation workflows should remain separate and explicitly gated.
