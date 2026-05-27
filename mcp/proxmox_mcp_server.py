#!/usr/bin/env python3
"""Read-only Proxmox VE MCP server.

This server intentionally exposes discovery and verification commands only.
Credential values must come from the caller's environment, preferably through
`op run`, and are never accepted as tool arguments.
"""

from __future__ import annotations

import os
import shlex
import subprocess
from dataclasses import dataclass

from mcp.server.fastmcp import FastMCP


mcp = FastMCP("d3hl-proxmox-readonly")


DEFAULT_HOSTS = {
    "nodeA": "10.10.10.18",
    "nodeB": "10.10.10.15",
    "nodeD": "10.10.10.17",
    "nodeF": "10.10.10.10",
}


READ_ONLY_COMMANDS = {
    "hostname": "hostname",
    "pveversion": "pveversion",
    "nodes": "pvesh get /nodes",
    "sdn": "pvesh get /cluster/sdn",
    "sdn_zones": "pvesh get /cluster/sdn/zones",
    "sdn_vnets": "pvesh get /cluster/sdn/vnets",
    "sdn_subnets": "pvesh get /cluster/sdn/subnets",
    "network_interfaces": "sed -n '1,240p' /etc/network/interfaces",
    "ovs_show": "command -v ovs-vsctl >/dev/null 2>&1 && ovs-vsctl show || true",
    "ip_brief": "ip -br address",
    "link_brief": "ip -br link",
    "bridge_vlan": "command -v bridge >/dev/null 2>&1 && bridge vlan show || true",
}


DISCOVERY_ORDER = [
    "hostname",
    "pveversion",
    "nodes",
    "sdn",
    "sdn_zones",
    "sdn_vnets",
    "sdn_subnets",
    "network_interfaces",
    "ovs_show",
    "ip_brief",
    "link_brief",
    "bridge_vlan",
]


@dataclass(frozen=True)
class SshTarget:
    label: str
    host: str
    user: str

    @property
    def destination(self) -> str:
        return f"{self.user}@{self.host}"


def _configured_hosts() -> dict[str, str]:
    """Return host aliases from env or the safe documented defaults."""
    raw_hosts = os.environ.get("PROXMOX_MCP_HOSTS", "").strip()
    if not raw_hosts:
        host = os.environ.get("PROXMOX_HOST", "").strip()
        if host:
            return {"default": host}
        return DEFAULT_HOSTS

    hosts: dict[str, str] = {}
    for item in raw_hosts.split(","):
        item = item.strip()
        if not item:
            continue
        if "=" in item:
            label, value = item.split("=", 1)
            hosts[label.strip()] = value.strip()
        else:
            hosts[item] = item

    return hosts or DEFAULT_HOSTS


def _ssh_user() -> str:
    user = os.environ.get("PROXMOX_USER", "").strip()
    if not user:
        raise RuntimeError(
            "PROXMOX_USER is required. Use op run with "
            "op://d3HLPRV/proxmox-cluster/username."
        )
    return user


def _target(node: str | None) -> SshTarget:
    hosts = _configured_hosts()
    label = node or next(iter(hosts))
    if label not in hosts:
        valid = ", ".join(sorted(hosts))
        raise ValueError(f"Unknown Proxmox node '{label}'. Valid nodes: {valid}")
    return SshTarget(label=label, host=hosts[label], user=_ssh_user())


def _ssh_options() -> list[str]:
    options = [
        "-o",
        "BatchMode=yes",
        "-o",
        "ConnectTimeout=8",
        "-o",
        "StrictHostKeyChecking=accept-new",
    ]
    ssh_key = os.environ.get("PROXMOX_SSH_KEY", "").strip()
    if ssh_key:
        options.extend(["-o", "IdentitiesOnly=yes", "-i", ssh_key])
    ssh_port = os.environ.get("PROXMOX_SSH_PORT", "").strip()
    if ssh_port:
        options.extend(["-p", ssh_port])
    return options


def _run_ssh(node: str | None, command_name: str) -> str:
    if command_name not in READ_ONLY_COMMANDS:
        valid = ", ".join(sorted(READ_ONLY_COMMANDS))
        raise ValueError(f"Unsupported read-only command '{command_name}'. Valid commands: {valid}")

    target = _target(node)
    remote_command = READ_ONLY_COMMANDS[command_name]
    args = ["ssh", *_ssh_options(), target.destination, remote_command]
    completed = subprocess.run(
        args,
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=30,
    )

    output = [
        f"# node: {target.label}",
        f"# host: {target.host}",
        f"# command: {remote_command}",
        f"# exit_code: {completed.returncode}",
    ]
    if completed.stdout:
        output.extend(["", completed.stdout.rstrip()])
    if completed.stderr:
        output.extend(["", "# stderr", completed.stderr.rstrip()])
    return "\n".join(output)


@mcp.tool()
def list_proxmox_nodes() -> dict[str, str]:
    """List configured Proxmox node aliases and host addresses."""
    return _configured_hosts()


@mcp.tool()
def list_read_only_commands() -> dict[str, str]:
    """List the read-only Proxmox commands this MCP server can run."""
    return READ_ONLY_COMMANDS


@mcp.tool()
def run_read_only_command(command_name: str, node: str | None = None) -> str:
    """Run one approved read-only Proxmox command over SSH.

    Use list_read_only_commands first to see valid command_name values.
    """
    return _run_ssh(node, command_name)


@mcp.tool()
def discover_proxmox_node(node: str | None = None) -> str:
    """Run the safe Proxmox discovery bundle on one node."""
    sections = []
    for command_name in DISCOVERY_ORDER:
        sections.append(_run_ssh(node, command_name))
    return "\n\n---\n\n".join(sections)


@mcp.tool()
def discover_proxmox_cluster() -> str:
    """Run the safe Proxmox discovery bundle on every configured node."""
    sections = []
    for node in _configured_hosts():
        sections.append(discover_proxmox_node(node))
    return "\n\n========\n\n".join(sections)


@mcp.tool()
def render_op_run_example() -> str:
    """Return an op run example without exposing secret values."""
    hosts = ",".join(f"{name}={host}" for name, host in _configured_hosts().items())
    quoted_hosts = shlex.quote(hosts)
    return "\n".join(
        [
            "PROXMOX_USER='op://d3HLPRV/proxmox-cluster/username' \\",
            f"PROXMOX_MCP_HOSTS={quoted_hosts} \\",
            "op run -- python mcp/proxmox_mcp_server.py",
        ]
    )


if __name__ == "__main__":
    mcp.run(transport="stdio")
