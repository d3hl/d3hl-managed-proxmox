#!/usr/bin/env python3
"""Validate Proxmox/VM reachability to FortiGate VLAN gateways.

This script is intentionally read-only for Proxmox configuration. It discovers
SDN state and VM NIC placement through the Proxmox API, then uses QEMU guest
agent ping only for running VMs attached to the routed VNets.
"""

from __future__ import annotations

import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "ansible" / "artifacts"
OUT_FILE = OUT_DIR / "proxmox-fortigate-gateway-validation.json"

URL = os.environ.get("PROXMOX_URL", "https://10.10.10.10:8006").rstrip("/")
TARGETS = {
    "vsvc": {"vlan": 30, "subnet": "10.10.30.0/24", "gateway": "10.10.30.2"},
    "vapps": {"vlan": 40, "subnet": "10.10.40.0/24", "gateway": "10.10.40.2"},
    "vlab": {"vlan": 50, "subnet": "10.10.50.0/24", "gateway": "10.10.50.2"},
    "vdmz": {"vlan": 60, "subnet": "10.10.60.0/24", "gateway": "10.10.60.2"},
}
TARGET_BY_VLAN = {item["vlan"]: name for name, item in TARGETS.items()}
TRUNKS = {
    "nodeA": {"port": "en10basep2", "vlans": {3, 10, 11, 30, 40, 50, 60}},
    "nodeB": {"port": "ennic1s1", "vlans": {3, 10, 11, 30, 40, 50, 60}},
    "nodeD": {"port": "eno1", "vlans": {3, 10, 11, 30, 40, 50, 60}},
    "nodeF": {"port": "sfp1", "vlans": {10, 11, 30, 40, 50, 60}},
}

CTX = ssl.create_default_context()
CTX.check_hostname = False
CTX.verify_mode = ssl.CERT_NONE


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def proxmox_token() -> str:
    token = os.environ.get("PROXMOX_API_TOKEN", "").strip()
    if token:
        return token

    token_id = (
        os.environ.get("PROXMOX_API_TOKEN_ID", "").strip()
        or os.environ.get("PROXMOX_API_TOKEN_USER", "").strip()
    )
    token_secret = (
        os.environ.get("PROXMOX_API_TOKEN_SECRET", "").strip()
        or os.environ.get("PROXMOX_API_TOKEN_CREDENTIAL", "").strip()
    )
    if token_id and token_secret:
        return f"{token_id}={token_secret}"
    return ""


TOKEN = proxmox_token()


def api(method: str, path: str, data: dict | None = None) -> tuple[int, dict | None, str]:
    url = f"{URL}/api2/json{path}"
    body = None
    headers = {"Authorization": f"PVEAPIToken={TOKEN}"}
    if data is not None:
        body = urllib.parse.urlencode(data, doseq=True).encode("utf-8")
        headers["Content-Type"] = "application/x-www-form-urlencoded"

    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, context=CTX, timeout=30) as response:
            text = response.read().decode("utf-8")
            return response.status, json.loads(text) if text else {}, ""
    except urllib.error.HTTPError as exc:
        text = exc.read().decode("utf-8", errors="replace")
        return exc.code, None, text[:500]
    except urllib.error.URLError as exc:
        return 0, None, str(exc.reason)


def get(path: str) -> dict | None:
    status, payload, error = api("GET", path)
    if status != 200:
        print(f"  API GET {path}: HTTP {status} {error}")
        return None
    return payload


def parse_kv_list(value: str) -> dict[str, str]:
    parsed = {}
    for part in value.split(","):
        if "=" in part:
            key, val = part.split("=", 1)
            parsed[key] = val
    return parsed


def parse_trunks(options: str) -> set[int]:
    match = re.search(r"\btrunks?=([0-9,\-]+)", options or "")
    value = match.group(1) if match else ""
    vlans = set()
    for item in value.split(","):
        item = item.strip()
        if "-" in item:
            start, end = item.split("-", 1)
            if start.isdigit() and end.isdigit():
                vlans.update(range(int(start), int(end) + 1))
        elif item.isdigit():
            vlans.add(int(item))
    return vlans


def discover_sdn() -> dict:
    zones = (get("/cluster/sdn/zones") or {}).get("data", [])
    vnets = (get("/cluster/sdn/vnets") or {}).get("data", [])
    subnets = []
    for vnet in TARGETS:
        for item in (get(f"/cluster/sdn/vnets/{vnet}/subnets") or {}).get("data", []):
            item["vnet"] = vnet
            subnets.append(item)

    vnet_by_name = {item.get("vnet"): item for item in vnets}
    subnet_by_vnet = {item.get("vnet"): item for item in subnets}
    checks = []
    for vnet, target in TARGETS.items():
        live_vnet = vnet_by_name.get(vnet, {})
        live_subnet = subnet_by_vnet.get(vnet, {})
        checks.append(
            {
                "vnet": vnet,
                "expected_vlan": target["vlan"],
                "live_vlan": live_vnet.get("tag"),
                "expected_gateway": target["gateway"],
                "live_gateway": live_subnet.get("gateway"),
                "vnet_ok": str(live_vnet.get("tag")) == str(target["vlan"]),
                "gateway_ok": live_subnet.get("gateway") == target["gateway"],
            }
        )
    return {"zones": zones, "vnets": vnets, "subnets": subnets, "checks": checks}


def discover_trunks() -> list[dict]:
    results = []
    for node, target in TRUNKS.items():
        iface = (get(f"/nodes/{node}/network/{target['port']}") or {}).get("data", {})
        live_vlans = parse_trunks(iface.get("ovs_options", ""))
        missing = sorted(target["vlans"] - live_vlans)
        results.append(
            {
                "node": node,
                "port": target["port"],
                "ovs_options": iface.get("ovs_options"),
                "expected_vlans": sorted(target["vlans"]),
                "live_vlans": sorted(live_vlans),
                "missing_vlans": missing,
                "ok": not missing,
            }
        )
    return results


def vm_nics(config: dict) -> list[dict]:
    nics = []
    for key, value in sorted(config.items()):
        if key.startswith("net") and isinstance(value, str):
            parsed = parse_kv_list(value)
            bridge = parsed.get("bridge")
            tag = parsed.get("tag")
            target_vnet = bridge if bridge in TARGETS else None
            if not target_vnet and tag and tag.isdigit():
                target_vnet = TARGET_BY_VLAN.get(int(tag))
            if bridge:
                nics.append({"key": key, "bridge": bridge, "tag": tag, "target_vnet": target_vnet, "raw": value})
    return nics


def discover_vms() -> list[dict]:
    resources = (get("/cluster/resources?type=vm") or {}).get("data", [])
    attached = []
    total = 0
    for vm in resources:
        node = vm.get("node")
        vmid = vm.get("vmid")
        vm_type = vm.get("type")
        if not node or not vmid or vm_type not in {"qemu", "lxc"}:
            continue
        total += 1
        config = (get(f"/nodes/{node}/{vm_type}/{vmid}/config") or {}).get("data", {})
        target_nics = [nic for nic in vm_nics(config) if nic.get("target_vnet") in TARGETS]
        if target_nics:
            attached.append(
                {
                    "vmid": vmid,
                    "name": vm.get("name"),
                    "node": node,
                    "type": vm_type,
                    "status": vm.get("status"),
                    "nics": target_nics,
                }
            )
    return {"total": total, "attached": attached}


def agent_ping(node: str, vmid: int, gateway: str) -> dict:
    status, _, error = api("GET", f"/nodes/{node}/qemu/{vmid}/agent/ping")
    if status != 200:
        return {"status": "agent_unavailable", "http_status": status, "error": error}

    attempts = [
        {"style": "linux", "args": ["-c", "3", "-W", "2", gateway]},
        {"style": "windows", "args": ["-n", "3", "-w", "2000", gateway]},
    ]
    last_result = {
        "status": "failed",
        "error": "guest agent ping attempts did not return exitcode 0",
    }
    for attempt in attempts:
        status, payload, error = api(
            "POST",
            f"/nodes/{node}/qemu/{vmid}/agent/exec",
            {
                "command": "ping",
                "extra-args": attempt["args"],
                "capture-output": 1,
            },
        )
        if status != 200 or not payload:
            continue
        pid = payload.get("data", {}).get("pid")
        if pid is None:
            continue

        final = {}
        for _ in range(10):
            time.sleep(1)
            poll_status, poll_payload, poll_error = api(
                "GET",
                f"/nodes/{node}/qemu/{vmid}/agent/exec-status?pid={pid}",
            )
            if poll_status != 200 or not poll_payload:
                final = {"status": "exec_status_error", "http_status": poll_status, "error": poll_error}
                break
            data = poll_payload.get("data", {})
            final = data
            if data.get("exited"):
                break
        if final.get("exited") and final.get("exitcode") == 0:
            return {
                "status": "ok",
                "style": attempt["style"],
                "exitcode": final.get("exitcode"),
                "stdout_preview": (final.get("out-data") or "")[:300],
            }
        if final.get("exited"):
            last_result = {
                "status": "ping_failed",
                "style": attempt["style"],
                "exitcode": final.get("exitcode"),
                "stdout_preview": (final.get("out-data") or "")[:300],
                "error": f"guest agent ping exited with code {final.get('exitcode')}",
            }
            continue
        if final.get("status") != "exec_status_error":
            last_result = {
                "status": "exec_timeout",
                "style": attempt["style"],
                "error": "guest agent ping command did not exit within polling window",
            }

    return last_result


def validate_guest_reachability(vms: list[dict]) -> list[dict]:
    results = []
    for vm in vms:
        for nic in vm["nics"]:
            target_vnet = nic["target_vnet"]
            gateway = TARGETS[target_vnet]["gateway"]
            result = {
                "vmid": vm["vmid"],
                "name": vm["name"],
                "node": vm["node"],
                "type": vm["type"],
                "status": vm["status"],
                "bridge": nic["bridge"],
                "tag": nic.get("tag"),
                "target_vnet": target_vnet,
                "gateway": gateway,
            }
            if vm["type"] != "qemu":
                result["reachability"] = {"status": "not_tested", "reason": "LXC guest exec is not implemented in this helper"}
            elif vm["status"] != "running":
                result["reachability"] = {"status": "not_tested", "reason": "VM is not running"}
            else:
                result["reachability"] = agent_ping(vm["node"], int(vm["vmid"]), gateway)
            results.append(result)
    return results


def main() -> int:
    if not TOKEN:
        return fail("Set PROXMOX_API_TOKEN or PROXMOX_API_TOKEN_ID + PROXMOX_API_TOKEN_SECRET")

    version = get("/version")
    if not version:
        return fail("Could not authenticate to Proxmox API")

    sdn = discover_sdn()
    trunks = discover_trunks()
    vm_discovery = discover_vms()
    vms = vm_discovery["attached"]
    guest_results = validate_guest_reachability(vms)

    summary = {
        "validated_at_epoch": int(time.time()),
        "proxmox_url": URL,
        "version": version.get("data", {}),
        "sdn": sdn,
        "trunks": trunks,
        "vm_count": vm_discovery["total"],
        "attached_vms": vms,
        "guest_reachability": guest_results,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    sdn_ok = all(item["vnet_ok"] and item["gateway_ok"] for item in sdn["checks"])
    trunk_ok = all(item["ok"] for item in trunks)
    guest_ok = [item for item in guest_results if item["reachability"].get("status") == "ok"]
    guest_failed = [
        item
        for item in guest_results
        if item["reachability"].get("status") not in {"ok", "not_tested", "agent_unavailable"}
    ]

    print("# Proxmox/FortiGate gateway validation")
    print(f"API: {URL}")
    print(f"Version: {version.get('data', {}).get('version', 'unknown')}")
    print(f"SDN gateway checks: {'ok' if sdn_ok else 'failed'}")
    for item in sdn["checks"]:
        state = "ok" if item["vnet_ok"] and item["gateway_ok"] else "failed"
        print(
            f"  {state}: {item['vnet']} vlan={item['live_vlan']} "
            f"gateway={item['live_gateway']}"
        )
    print(f"OVS trunk checks: {'ok' if trunk_ok else 'failed'}")
    for item in trunks:
        state = "ok" if item["ok"] else f"missing {item['missing_vlans']}"
        print(f"  {item['node']}/{item['port']}: {state}")
    print(f"VMs/CTs discovered: {vm_discovery['total']}")
    print(f"VMs/CTs attached to routed VNets: {len(vms)}")
    print(f"Guest-agent gateway pings OK: {len(guest_ok)}")
    if guest_failed:
        print(f"Guest-agent gateway ping failures: {len(guest_failed)}")
        for item in guest_failed:
            print(
                f"  {item['vmid']} {item['name']} {item['bridge']} -> "
                f"{item['gateway']}: {item['reachability'].get('status')}"
            )
    print(f"Evidence: {OUT_FILE.relative_to(ROOT)}")

    if not sdn_ok or not trunk_ok or guest_failed:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
