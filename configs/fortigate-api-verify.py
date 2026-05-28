#!/usr/bin/env python3
"""Read-only FortiGate interface verification.

Uses FORTIGATE_HOST and FORTIOS_ACCESS_TOKEN from the environment. Intended to
be run via 1Password `op run` so no token is stored or printed.
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


ROOT = Path(__file__).resolve().parents[1]
NETWORK_PLAN = ROOT / "data" / "network-plan.json"
OUT_DIR = ROOT / "ansible" / "artifacts"
OUT_FILE = OUT_DIR / "fortigate-verification.json"

VDOM = os.environ.get("FORTIGATE_VDOM", "root")


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def normalize_host(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        raise ValueError("FORTIGATE_HOST is empty")
    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    if not parsed.hostname:
        raise ValueError("FORTIGATE_HOST is not a valid host or URL")
    netloc = parsed.netloc
    return f"{parsed.scheme or 'https'}://{netloc}"


def api_get(base_url: str, token: str, path: str) -> dict:
    query = urllib.parse.urlencode({"vdom": VDOM})
    url = f"{base_url}{path}?{query}"
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        method="GET",
    )
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=20, context=context) as response:
        return json.loads(response.read().decode("utf-8"))


def target_interfaces() -> list[dict]:
    plan = json.loads(NETWORK_PLAN.read_text(encoding="utf-8"))
    targets = []
    for item in plan["vlans"]:
        vlan = item["vlan"]
        if vlan == 99:
            role = "lan"
            allowaccess = ["ping", "https", "ssh"]
        elif vlan == 60:
            role = "dmz"
            allowaccess = ["ping"]
        elif vlan == 10:
            role = "lan"
            allowaccess = ["ping", "https", "ssh"]
        else:
            role = "lan"
            allowaccess = ["ping"]
        targets.append(
            {
                "name": f"VLAN{vlan}_{item['name']}",
                "vlanid": vlan,
                "ip": item["gateway"],
                "alias": item["purpose"],
                "role": role,
                "allowaccess": allowaccess,
            }
        )
    return targets


def normalize_ip(value: str | None) -> str | None:
    if not value:
        return None
    first = str(value).split()[0]
    try:
        return str(ipaddress.ip_interface(first).ip)
    except ValueError:
        return first


def run() -> int:
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

    try:
        response = api_get(base_url, token, "/api/v2/cmdb/system/interface")
    except urllib.error.HTTPError as exc:
        return fail(f"FortiGate API returned HTTP {exc.code}; check token permissions and host")
    except urllib.error.URLError as exc:
        return fail(f"FortiGate API connection failed: {exc.reason}")
    except TimeoutError:
        return fail("FortiGate API connection timed out")

    interfaces = response.get("results", [])
    by_name = {item.get("name"): item for item in interfaces}
    targets = target_interfaces()

    checks = []
    parent_interfaces = set()
    for target in targets:
        actual = by_name.get(target["name"])
        if not actual:
            checks.append(
                {
                    "name": target["name"],
                    "status": "missing",
                    "expected": target,
                    "actual": None,
                }
            )
            continue

        actual_ip = normalize_ip(actual.get("ip"))
        expected_ip = normalize_ip(target["ip"])
        parent = actual.get("interface")
        if parent:
            parent_interfaces.add(parent)

        mismatches = []
        if int(actual.get("vlanid", -1)) != int(target["vlanid"]):
            mismatches.append("vlanid")
        if actual_ip != expected_ip:
            mismatches.append("ip")
        if actual.get("type") not in ("vlan", "vdom-link"):
            mismatches.append("type")

        checks.append(
            {
                "name": target["name"],
                "status": "match" if not mismatches else "mismatch",
                "mismatches": mismatches,
                "expected": target,
                "actual": {
                    "name": actual.get("name"),
                    "type": actual.get("type"),
                    "interface": parent,
                    "vlanid": actual.get("vlanid"),
                    "ip": actual.get("ip"),
                    "allowaccess": actual.get("allowaccess"),
                    "alias": actual.get("alias"),
                    "role": actual.get("role"),
                    "status": actual.get("status"),
                },
            }
        )

    summary = {
        "verified_at_epoch": int(time.time()),
        "vdom": VDOM,
        "fortigate_host": base_url.replace("https://", "").replace("http://", ""),
        "total_interfaces_seen": len(interfaces),
        "target_count": len(targets),
        "match_count": sum(1 for item in checks if item["status"] == "match"),
        "missing_count": sum(1 for item in checks if item["status"] == "missing"),
        "mismatch_count": sum(1 for item in checks if item["status"] == "mismatch"),
        "candidate_parent_interfaces": sorted(parent_interfaces),
        "checks": checks,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("# FortiGate interface verification")
    print(f"Host: {summary['fortigate_host']}")
    print(f"VDOM: {VDOM}")
    print(f"Interfaces seen: {summary['total_interfaces_seen']}")
    print(f"Targets: {summary['target_count']}")
    print(f"Matches: {summary['match_count']}")
    print(f"Missing: {summary['missing_count']}")
    print(f"Mismatches: {summary['mismatch_count']}")
    print(f"Candidate parent interfaces: {', '.join(summary['candidate_parent_interfaces']) or 'none'}")
    print(f"Evidence: {OUT_FILE.relative_to(ROOT)}")
    for check in checks:
        marker = {"match": "OK", "missing": "MISSING", "mismatch": "MISMATCH"}[check["status"]]
        print(f"{marker}: {check['name']}")
        if check["status"] == "mismatch":
            print(f"  fields: {', '.join(check['mismatches'])}")

    return 0 if summary["missing_count"] == 0 and summary["mismatch_count"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(run())
