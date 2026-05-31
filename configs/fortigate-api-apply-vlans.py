#!/usr/bin/env python3
"""Apply FortiGate VLAN interfaces from Ansible intent via FortiOS REST API.

This is a fallback for workstations where the Ansible CLI cannot start. It uses
the same `ansible/group_vars/fortigates.yml` data and requires explicit apply
confirmation environment variables.
"""

from __future__ import annotations

import ipaddress
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
FORTIGATE_VARS = ROOT / "ansible" / "group_vars" / "fortigates.yml"
OUT_DIR = ROOT / "ansible" / "artifacts"
OUT_FILE = OUT_DIR / "fortigate-vlan-apply.json"


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def normalize_host(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    if not parsed.hostname:
        raise ValueError("FORTIGATE_HOST is not a valid host or URL")
    return f"{parsed.scheme or 'https'}://{parsed.netloc}"


def cidr_to_fortios_ip(value: str) -> str:
    interface = ipaddress.ip_interface(value)
    return f"{interface.ip} {interface.network.netmask}"


def request(base_url: str, token: str, method: str, path: str, vdom: str, data: dict | None = None) -> dict:
    query = urllib.parse.urlencode({"vdom": vdom})
    url = f"{base_url}{path}?{query}"
    body = None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=30, context=context) as response:
        text = response.read().decode("utf-8")
        return json.loads(text) if text else {}


def load_intent() -> dict:
    return yaml.safe_load(FORTIGATE_VARS.read_text(encoding="utf-8"))


def interface_payload(item: dict, parent: str, vdom: str) -> dict:
    return {
        "name": item["name"],
        "type": "vlan",
        "interface": parent,
        "vlanid": int(item["vlanid"]),
        "ip": cidr_to_fortios_ip(item["ip"]),
        "allowaccess": " ".join(item.get("allowaccess", [])),
        "alias": item.get("alias", ""),
        "role": item.get("role", "lan"),
        "vdom": vdom,
    }


def run() -> int:
    if os.environ.get("CONFIRM_FORTIGATE_APPLY", "") != "yes":
        return fail("Refusing to apply: set CONFIRM_FORTIGATE_APPLY=yes")
    if os.environ.get("CONFIRM_FORTIGATE_TRUNK_REVIEW", "") != "yes":
        return fail("Refusing to apply: set CONFIRM_FORTIGATE_TRUNK_REVIEW=yes")

    host = os.environ.get("FORTIGATE_HOST", "")
    token = os.environ.get("FORTIOS_ACCESS_TOKEN", "")
    if not host:
        return fail("FORTIGATE_HOST is required")
    if not token:
        return fail("FORTIOS_ACCESS_TOKEN is required")

    try:
        base_url = normalize_host(host)
    except ValueError as exc:
        return fail(str(exc))

    intent = load_intent()
    vdom = intent["fortigate_vdom"]
    parent = intent["fortigate_parent_interface"]
    candidates = intent["fortigate_vlan_interfaces"]

    try:
        current = request(base_url, token, "GET", "/api/v2/cmdb/system/interface", vdom)
    except urllib.error.HTTPError as exc:
        return fail(f"FortiGate API returned HTTP {exc.code}; check token permissions")
    except urllib.error.URLError as exc:
        return fail(f"FortiGate API connection failed: {exc.reason}")

    existing = {item.get("name"): item for item in current.get("results", [])}
    operations = []

    for item in candidates:
        payload = interface_payload(item, parent, vdom)
        name = item["name"]
        method = "PUT" if name in existing else "POST"
        path = f"/api/v2/cmdb/system/interface/{urllib.parse.quote(name, safe='')}" if method == "PUT" else "/api/v2/cmdb/system/interface"
        try:
            response = request(base_url, token, method, path, vdom, payload)
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            operations.append(
                {
                    "name": name,
                    "method": method,
                    "status": "error",
                    "http_status": exc.code,
                    "body": body[:500],
                }
            )
            continue
        operations.append(
            {
                "name": name,
                "method": method,
                "status": "ok",
                "http_status": response.get("http_status"),
                "revision_changed": response.get("revision_changed"),
            }
        )

    failed = [item for item in operations if item["status"] != "ok"]
    summary = {
        "applied_at_epoch": int(time.time()),
        "host": base_url.replace("https://", "").replace("http://", ""),
        "vdom": vdom,
        "parent_interface": parent,
        "candidate_count": len(candidates),
        "failed_count": len(failed),
        "operations": operations,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("# FortiGate VLAN interface apply")
    print(f"Host: {summary['host']}")
    print(f"VDOM: {vdom}")
    print(f"Parent: {parent}")
    for item in operations:
        print(f"{item['status'].upper()}: {item['method']} {item['name']}")
        if item["status"] != "ok":
            print(f"  HTTP {item.get('http_status')}: {item.get('body')}")
    print(f"Evidence: {OUT_FILE.relative_to(ROOT)}")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
