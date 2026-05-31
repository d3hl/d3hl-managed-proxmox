#!/usr/bin/env python3
"""Merge network-plan and discovery artifacts into a unified dashboard snapshot.

Reads existing artifact JSON files (offline by default). Optionally runs live
discovery scripts with --live before merging.

Writes data/network-dashboard-snapshot.json and optionally the canvas sidecar
at ~/.cursor/projects/<workspace>/canvases/homelab-network-dashboard.canvas.data.json
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
PLAN_FILE = ROOT / "data" / "network-plan.json"
OUT_FILE = ROOT / "data" / "network-dashboard-snapshot.json"
ARTIFACTS = ROOT / "ansible" / "artifacts"
FG_FILE = ARTIFACTS / "fortigate-discovery.json"
CISCO_FILE = ARTIFACTS / "cisco-c9300-verification.json"
PVE_FILE = ARTIFACTS / "proxmox-fortigate-gateway-validation.json"

SIDECAR = Path.home() / ".cursor" / "projects" / "home-d3-Github-d3hl-managed-proxmox" / "canvases" / "homelab-network-dashboard.canvas.data.json"

NODE_MGMT_IPS = {
    "nodeA": "10.10.10.18",
    "nodeB": "10.10.10.15",
    "nodeD": "10.10.10.17",
    "nodeF": "10.10.10.10",
}

KNOWN_VM_IPS = [
    {"subnet": "10.10.50.0/24", "address": "10.10.50.10", "device": "VM", "interface": "sg-hl-vm01 net1/vlab", "role": "guest", "status": "known"},
    {"subnet": "10.10.10.0/24", "address": "10.10.10.25", "device": "VM", "interface": "sg-hl-vm01 net0/vmgmt", "role": "guest", "status": "known"},
]

CISCO_SVI_VLAN_MAP = {
    10: "10.10.10.0/24",
    11: "10.11.11.0/24",
    20: "10.20.20.0/24",
    50: "10.10.50.0/24",
    99: "10.99.99.0/24",
    100: "10.100.100.0/24",
}


def load_json(path: Path) -> dict | None:
    if not path.is_file():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def fg_ip_to_cidr(ip_field: str) -> str:
    """Convert FortiOS '10.10.10.2 255.255.255.0' to '10.10.10.2/24'."""
    parts = ip_field.strip().split()
    if len(parts) != 2:
        return ip_field.strip()
    addr, mask = parts
    if mask == "255.255.255.0":
        return f"{addr}/24"
    return f"{addr} {mask}"


def parse_cisco_ip_brief(text: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("Interface"):
            continue
        m = re.match(
            r"^(\S+)\s+(\S+)\s+\S+\s+\S+\s+(\S+)\s+(\S+)",
            line,
        )
        if not m:
            continue
        iface, ip, status, protocol = m.group(1), m.group(2), m.group(3), m.group(4)
        if ip == "unassigned":
            continue
        link = "up" if status == "up" and protocol == "up" else "down"
        rows.append({"interface": iface, "ip": ip, "link_status": link})
    return rows


def parse_cisco_port_status(text: str) -> dict[str, str]:
    """Map interface name to link status from show ip interface brief."""
    status: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("Interface"):
            continue
        parts = line.split()
        if len(parts) < 5:
            continue
        port, link, protocol = parts[0], parts[-2], parts[-1]
        status[port] = "up" if link == "up" and protocol == "up" else "down"
    return status


def cisco_trunk_link_status(port: str, port_status: dict[str, str]) -> str:
    if port in port_status:
        return port_status[port]
    short = port.replace("TwentyFiveGigE", "Twe").replace("TenGigabitEthernet", "Te")
    if short in port_status:
        return port_status[short]
    return "unknown"


def vlan_in_list(vlan_id: int, allowed: list[int]) -> bool:
    return vlan_id in allowed


def build_topology(plan: dict, cisco: dict | None, pve: dict | None) -> dict:
    edges: list[dict] = []
    fg_trunk = plan.get("trunks", {}).get("c9300_to_fortigate", {})
    fg_iface = fg_trunk.get("interface", "TwentyFiveGigE2/1/2")
    fg_vlans = fg_trunk.get("allowed_vlans", [])

    port_status: dict[str, str] = {}
    if cisco and cisco.get("raw", {}).get("show_ip_interface_brief"):
        port_status = parse_cisco_port_status(cisco["raw"]["show_ip_interface_brief"])

    edges.append(
        {
            "from": "fortigate",
            "to": "c9300",
            "interface": fg_iface,
            "allowed_vlans": fg_vlans,
            "status": cisco_trunk_link_status(fg_iface, port_status),
        }
    )

    pve_trunks = plan.get("trunks", {}).get("c9300_to_proxmox", {})
    allowed = pve_trunks.get("allowed_vlans", [])
    for entry in pve_trunks.get("interfaces", []):
        iface = entry.get("interface", "")
        node = "node" + entry.get("description", "").split("node")[-1] if "node" in entry.get("description", "") else None
        if not node:
            desc = entry.get("description", "")
            for n in ["nodeA", "nodeB", "nodeD", "nodeF"]:
                if n in desc:
                    node = n
                    break
        if node:
            edges.append(
                {
                    "from": "c9300",
                    "to": node,
                    "interface": iface,
                    "allowed_vlans": allowed,
                    "status": cisco_trunk_link_status(iface, port_status),
                }
            )

    if pve and pve.get("trunks"):
        for trunk in pve["trunks"]:
            node = trunk.get("node", "")
            if not any(e.get("to") == node for e in edges):
                edges.append(
                    {
                        "from": "c9300",
                        "to": node,
                        "interface": trunk.get("port", ""),
                        "allowed_vlans": trunk.get("live_vlans", trunk.get("expected_vlans", [])),
                        "status": "up" if trunk.get("ok") else "down",
                    }
                )
            else:
                for e in edges:
                    if e.get("to") == node and trunk.get("ok") is False:
                        e["status"] = "down"

    return {"layers": ["fortigate", "c9300", "proxmox"], "edges": edges}


def build_vlans(plan: dict, fg: dict | None, cisco: dict | None, pve: dict | None) -> list[dict]:
    fg_trunk_vlans = set(plan.get("trunks", {}).get("c9300_to_fortigate", {}).get("allowed_vlans", []))
    pve_trunk_vlans = set(plan.get("trunks", {}).get("c9300_to_proxmox", {}).get("allowed_vlans", []))

    fg_status_by_vlan: dict[int, str] = {}
    if fg:
        for check in fg.get("interfaces", {}).get("target_checks", []):
            actual = check.get("actual", {})
            vid = actual.get("vlanid")
            if vid:
                fg_status_by_vlan[vid] = actual.get("status", "unknown")
        for iface in fg.get("interfaces", {}).get("vlan_interfaces", []):
            vid = iface.get("vlanid")
            if vid:
                fg_status_by_vlan[vid] = iface.get("status", "unknown")

    pve_vnet_by_vlan: dict[int, str] = {}
    if pve:
        for vnet in pve.get("sdn", {}).get("vnets", []):
            tag = vnet.get("tag")
            if tag is not None:
                pve_vnet_by_vlan[tag] = vnet.get("vnet", "")

    rows: list[dict] = []
    for vlan in plan.get("vlans", []):
        vid = vlan.get("vlan")
        rows.append(
            {
                "id": vid,
                "name": vlan.get("name", ""),
                "purpose": vlan.get("purpose", ""),
                "subnet": vlan.get("subnet", ""),
                "gateway": vlan.get("gateway"),
                "fortigate_if": vlan.get("fortigate_interface"),
                "vnet": vlan.get("vnet"),
                "fg_status": fg_status_by_vlan.get(vid, "unknown"),
                "on_fg_trunk": vlan_in_list(vid, list(fg_trunk_vlans)) if vid else False,
                "on_pve_trunk": vlan_in_list(vid, list(pve_trunk_vlans)) if vid else False,
                "pve_vnet": pve_vnet_by_vlan.get(vid),
            }
        )
    return rows


def build_interfaces(plan: dict, fg: dict | None, cisco: dict | None, pve: dict | None) -> list[dict]:
    rows: list[dict] = []

    if fg:
        for check in fg.get("interfaces", {}).get("target_checks", []):
            actual = check.get("actual", {})
            rows.append(
                {
                    "device": "FortiGate",
                    "name": actual.get("name", check.get("name", "")),
                    "vlan": actual.get("vlanid") or None,
                    "ip": fg_ip_to_cidr(actual.get("ip", "")) if actual.get("ip") else "",
                    "link_status": actual.get("status", "unknown"),
                    "role": "gateway" if actual.get("type") == "vlan" else "management",
                }
            )
        parent = fg.get("interfaces", {}).get("parent_trunk", {})
        if parent:
            rows.append(
                {
                    "device": "FortiGate",
                    "name": parent.get("name", "x2"),
                    "vlan": None,
                    "ip": "",
                    "link_status": parent.get("status", "unknown"),
                    "role": "trunk_parent",
                }
            )

    cisco_svies: list[dict] = []
    if cisco:
        raw_brief = cisco.get("raw", {}).get("show_ip_interface_brief", "")
        cisco_svies = parse_cisco_ip_brief(raw_brief)
        port_status = parse_cisco_port_status(raw_brief)

        for trunk in cisco.get("checks", {}).get("trunks", []):
            iface = trunk.get("interface", "")
            rows.append(
                {
                    "device": "C9300",
                    "name": iface,
                    "vlan": None,
                    "ip": "",
                    "link_status": cisco_trunk_link_status(iface, port_status),
                    "role": "trunk",
                    "allowed_vlans": trunk.get("actual_allowed_vlans", []),
                }
            )

        for svi in cisco_svies:
            if svi["interface"].startswith("Vlan"):
                vid = int(svi["interface"].replace("Vlan", ""))
                rows.append(
                    {
                        "device": "C9300",
                        "name": svi["interface"],
                        "vlan": vid,
                        "ip": f"{svi['ip']}/24",
                        "link_status": svi["link_status"],
                        "role": "SVI",
                    }
                )

    if pve:
        for trunk in pve.get("trunks", []):
            rows.append(
                {
                    "device": "Proxmox",
                    "name": f"{trunk.get('node')}/{trunk.get('port')}",
                    "vlan": None,
                    "ip": NODE_MGMT_IPS.get(trunk.get("node", ""), ""),
                    "link_status": "up" if trunk.get("ok") else "down",
                    "role": "ovs_trunk",
                    "allowed_vlans": trunk.get("live_vlans", []),
                }
            )

    return rows


def build_ip_inventory(plan: dict, fg: dict | None, cisco: dict | None, pve: dict | None) -> list[dict]:
    inventory: list[dict] = []

    for vlan in plan.get("vlans", []):
        subnet = vlan.get("subnet", "")
        gw = vlan.get("gateway")
        if gw:
            inventory.append(
                {
                    "subnet": subnet,
                    "address": gw,
                    "device": "FortiGate",
                    "interface": vlan.get("fortigate_interface") or f"VLAN{vlan.get('vlan')}",
                    "role": "gateway",
                    "status": "up",
                }
            )

    if cisco:
        for svi in parse_cisco_ip_brief(cisco.get("raw", {}).get("show_ip_interface_brief", "")):
            if svi["interface"].startswith("Vlan"):
                vid = int(svi["interface"].replace("Vlan", ""))
                subnet = CISCO_SVI_VLAN_MAP.get(vid, "")
                inventory.append(
                    {
                        "subnet": subnet,
                        "address": svi["ip"],
                        "device": "C9300",
                        "interface": svi["interface"],
                        "role": "SVI",
                        "status": svi["link_status"],
                    }
                )

    for node, ip in NODE_MGMT_IPS.items():
        inventory.append(
            {
                "subnet": "10.10.10.0/24",
                "address": ip,
                "device": "Proxmox",
                "interface": f"{node} mgmt",
                "role": "node",
                "status": "known",
            }
        )

    inventory.extend({**entry} for entry in KNOWN_VM_IPS)

    return inventory


def build_subnet_utilization(ip_inventory: list[dict], plan: dict) -> list[dict]:
    subnets: list[dict] = []
    by_subnet: dict[str, list[dict]] = {}
    for entry in ip_inventory:
        subnet = entry.get("subnet", "")
        if subnet:
            by_subnet.setdefault(subnet, []).append(entry)

    for vlan in plan.get("vlans", []):
        cidr = vlan.get("subnet", "")
        if not cidr or "/24" not in cidr:
            continue
        entries = by_subnet.get(cidr, [])
        segments: dict[str, int] = {}
        for e in entries:
            role = e.get("role", "other")
            segments[role] = segments.get(role, 0) + 1
        known_used = len(entries)
        subnets.append(
            {
                "cidr": cidr,
                "vlan": vlan.get("vlan"),
                "name": vlan.get("name", ""),
                "total_hosts": 254,
                "known_used": known_used,
                "segments": [{"id": k, "value": v} for k, v in sorted(segments.items())],
            }
        )
    return subnets


def collect(plan: dict, fg: dict | None, cisco: dict | None, pve: dict | None) -> dict:
    ip_inventory = build_ip_inventory(plan, fg, cisco, pve)
    return {
        "collected_at_epoch": int(time.time()),
        "sources": {
            "fortigate": str(FG_FILE.relative_to(ROOT)) if fg else None,
            "cisco": str(CISCO_FILE.relative_to(ROOT)) if cisco else None,
            "proxmox": str(PVE_FILE.relative_to(ROOT)) if pve else None,
            "plan": str(PLAN_FILE.relative_to(ROOT)),
        },
        "topology": build_topology(plan, cisco, pve),
        "vlans": build_vlans(plan, fg, cisco, pve),
        "interfaces": build_interfaces(plan, fg, cisco, pve),
        "ip_inventory": ip_inventory,
        "subnet_utilization": build_subnet_utilization(ip_inventory, plan),
    }


def run_live() -> None:
    scripts = [
        ["bash", str(ROOT / "configs" / "fortigate-discover-op-run.sh")],
        ["python", str(ROOT / "configs" / "cisco-c9300-verify.py")],
        ["python", str(ROOT / "configs" / "proxmox-fortigate-gateway-validate.py")],
    ]
    for cmd in scripts:
        print(f"# Running: {' '.join(cmd)}")
        result = subprocess.run(cmd, cwd=ROOT)
        if result.returncode != 0:
            print(f"WARNING: {' '.join(cmd)} exited {result.returncode}", file=sys.stderr)


def write_sidecar(snapshot: dict) -> None:
    SIDECAR.parent.mkdir(parents=True, exist_ok=True)
    payload = {"dashboardSnapshot": snapshot}
    SIDECAR.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"# Wrote sidecar: {SIDECAR}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect homelab network dashboard snapshot")
    parser.add_argument("--live", action="store_true", help="Run live discovery scripts before merge")
    parser.add_argument("--write-sidecar", action="store_true", help="Write canvas .canvas.data.json sidecar")
    args = parser.parse_args()

    if args.live:
        run_live()

    plan = load_json(PLAN_FILE)
    if not plan:
        print(f"ERROR: missing {PLAN_FILE}", file=sys.stderr)
        return 1

    fg = load_json(FG_FILE)
    cisco = load_json(CISCO_FILE)
    pve = load_json(PVE_FILE)

    if not fg:
        print(f"WARNING: missing {FG_FILE}", file=sys.stderr)
    if not cisco:
        print(f"WARNING: missing {CISCO_FILE}", file=sys.stderr)
    if not pve:
        print(f"WARNING: missing {PVE_FILE}", file=sys.stderr)

    snapshot = collect(plan, fg, cisco, pve)
    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
    print(f"# Wrote snapshot: {OUT_FILE}")

    if args.write_sidecar:
        write_sidecar(snapshot)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
