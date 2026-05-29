#!/usr/bin/env python3
"""Inspect or update a Proxmox VM network config through the Proxmox API.

This helper is intentionally narrow:
- inspect: print relevant VM network/cloud-init fields
- ensure-net: ensure a specific NIC exists on a target bridge
- set-ipconfig: set a cloud-init ipconfig slot for a VM

The script expects the following environment variables:
- PROXMOX_URL
- PROXMOX_API_TOKEN_ID
- PROXMOX_API_TOKEN_SECRET

The caller should inject them from 1Password with `op read` or `op run`.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request


CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def fail(message: str, code: int = 1) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return code


def token() -> str:
    token_id = os.environ.get("PROXMOX_API_TOKEN_ID", "").strip()
    token_secret = os.environ.get("PROXMOX_API_TOKEN_SECRET", "").strip()
    if not token_id or not token_secret:
        return ""
    return f"{token_id}={token_secret}"


def base_url() -> str:
    url = os.environ.get("PROXMOX_URL", "https://10.10.10.10:8006").strip().rstrip("/")
    if not url:
        raise ValueError("PROXMOX_URL is required")
    return url


def api(method: str, path: str, data: dict | None = None) -> dict:
    url = f"{base_url()}/api2/json{path}"
    headers = {"Authorization": f"PVEAPIToken={token()}"}
    body = None
    if data is not None:
        body = urllib.parse.urlencode(data, doseq=True).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, context=CTX, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def get_vm_config(node: str, vmtype: str, vmid: str) -> dict:
    payload = api("GET", f"/nodes/{node}/{vmtype}/{vmid}/config")
    return payload.get("data", {})


def print_relevant(config: dict) -> None:
    keys = [
        "name",
        "status",
        "ostype",
        "agent",
        "onboot",
        "machine",
        "bios",
        "vga",
        "serial0",
        "scsi0",
        "scsi1",
        "ide0",
        "ide1",
        "ide2",
        "net0",
        "net1",
        "ipconfig0",
        "ipconfig1",
        "cicustom",
        "tags",
        "description",
    ]
    print(json.dumps({key: config.get(key) for key in keys if key in config}, indent=2))


def ensure_net(args: argparse.Namespace) -> int:
    config = get_vm_config(args.node, args.vmtype, args.vmid)
    current = config.get(args.nic)
    desired = f"{args.model}={args.mac},bridge={args.bridge},firewall=1"
    if current == desired:
        print(f"{args.nic}: already matches desired bridge {args.bridge}")
        return 0

    print(f"{args.nic}: updating")
    print(f"  current: {current or '<missing>'}")
    print(f"  desired: {desired}")
    try:
        api(
            "PUT",
            f"/nodes/{args.node}/{args.vmtype}/{args.vmid}/config",
            {args.nic: desired},
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return fail(f"Proxmox rejected NIC update: HTTP {exc.code} {body[:400]}")
    print(f"{args.nic}: updated")
    return 0


def set_ipconfig(args: argparse.Namespace) -> int:
    config = get_vm_config(args.node, args.vmtype, args.vmid)
    cloudinit_drive = None
    for key in ("ide0", "ide1", "ide2", "sata0", "sata1", "sata2", "scsi0", "scsi1", "scsi2"):
        value = config.get(key, "")
        if isinstance(value, str) and "cloudinit" in value.lower():
            cloudinit_drive = f"{key}={value}"
            break
    if not cloudinit_drive:
        return fail("No cloud-init drive was found in the VM config; ipconfig updates would not apply.")

    value = f"ip={args.ip}/{args.cidr},gw={args.gateway}"
    current = config.get(args.slot)
    if current == value:
        print(f"{args.slot}: already set to {value}")
        return 0

    print(f"{args.slot}: updating")
    print(f"  cloud-init drive: {cloudinit_drive}")
    print(f"  current: {current or '<missing>'}")
    print(f"  desired: {value}")
    try:
        api(
            "PUT",
            f"/nodes/{args.node}/{args.vmtype}/{args.vmid}/config",
            {args.slot: value},
        )
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return fail(f"Proxmox rejected ipconfig update: HTTP {exc.code} {body[:400]}")
    print(f"{args.slot}: updated")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["inspect", "ensure-net", "set-ipconfig"])
    parser.add_argument("--node", default="nodeF")
    parser.add_argument("--vmtype", default="qemu", choices=["qemu", "lxc"])
    parser.add_argument("--vmid", default="444")
    parser.add_argument("--nic", default="net1")
    parser.add_argument("--bridge", default="vlab")
    parser.add_argument("--mac", default="BC:24:11:DF:0A:C4")
    parser.add_argument("--model", default="virtio")
    parser.add_argument("--slot", default="ipconfig1")
    parser.add_argument("--ip", default="10.10.50.20")
    parser.add_argument("--cidr", default="24")
    parser.add_argument("--gateway", default="10.10.50.2")
    args = parser.parse_args()

    if not token():
        return fail("Set PROXMOX_API_TOKEN_ID and PROXMOX_API_TOKEN_SECRET")

    try:
        api("GET", "/version")
    except urllib.error.HTTPError as exc:
        return fail(f"Proxmox authentication failed: HTTP {exc.code}")
    except urllib.error.URLError as exc:
        return fail(f"Proxmox connection failed: {exc.reason}")

    config = get_vm_config(args.node, args.vmtype, args.vmid)
    if args.action == "inspect":
        print_relevant(config)
        return 0
    if args.action == "ensure-net":
        return ensure_net(args)
    if args.action == "set-ipconfig":
        return set_ipconfig(args)
    return fail("Unknown action")


if __name__ == "__main__":
    raise SystemExit(main())
