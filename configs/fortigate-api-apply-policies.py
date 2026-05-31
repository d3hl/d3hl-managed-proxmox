#!/usr/bin/env python3
"""Apply FortiGate address objects, zones, and firewall policies from repo intent.

Requires:
  FORTIGATE_HOST
  FORTIOS_ACCESS_TOKEN
  CONFIRM_FORTIGATE_POLICY_PLAN_REVIEW=yes
  CONFIRM_FORTIGATE_POLICY_APPLY=yes
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
INTENT_FILE = ROOT / "ansible" / "group_vars" / "fortigate_policies.yml"
OUT_DIR = ROOT / "ansible" / "artifacts"
OUT_FILE = OUT_DIR / "fortigate-policy-apply.json"


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def normalize_host(value: str) -> str:
    value = value.strip().rstrip("/")
    parsed = urllib.parse.urlparse(value if "://" in value else f"https://{value}")
    if not parsed.hostname:
        raise ValueError("FORTIGATE_HOST is not a valid host or URL")
    return f"{parsed.scheme or 'https'}://{parsed.netloc}"


def cidr_to_fortios_subnet(value: str) -> str:
    interface = ipaddress.ip_interface(value)
    return f"{interface.network.network_address} {interface.network.netmask}"


def request(base_url: str, token: str, method: str, path: str, vdom: str, data: dict | None = None) -> dict:
    query = urllib.parse.urlencode({"vdom": vdom})
    url = f"{base_url}{path}?{query}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }
    body = None
    if data is not None:
        body = json.dumps(data).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=30, context=context) as response:
        text = response.read().decode("utf-8")
        return json.loads(text) if text else {}


def list_results(base_url: str, token: str, path: str, vdom: str) -> list[dict]:
    return request(base_url, token, "GET", path, vdom).get("results", [])


def named_refs(names: list[str]) -> list[dict]:
    return [{"name": name} for name in names]


def load_intent() -> dict:
    return yaml.safe_load(INTENT_FILE.read_text(encoding="utf-8"))


def address_payload(item: dict) -> dict:
    payload = {
        "name": item["name"],
        "type": item["type"],
        "interface": item["interface"],
        "subnet": cidr_to_fortios_subnet(item["subnet"]),
    }
    return payload


def zone_payload(item: dict) -> dict:
    return {
        "name": item["name"],
        "intrazone": item.get("intrazone", "deny"),
        "interface": [{"interface-name": item["interface"]}],
    }


def policy_payload(item: dict) -> dict:
    payload = {
        "name": item["name"],
        "status": item.get("status", "enable"),
        "action": item["action"],
        "srcintf": named_refs(item["srcintf"]),
        "dstintf": named_refs(item["dstintf"]),
        "srcaddr": named_refs(item["srcaddr"]),
        "dstaddr": named_refs(item["dstaddr"]),
        "service": named_refs(item["service"]),
        "schedule": item.get("schedule", "always"),
        "nat": item.get("nat", "disable"),
        "comments": item.get("comments", ""),
    }
    return payload


def apply_named_objects(
    base_url: str,
    token: str,
    vdom: str,
    collection_path: str,
    existing: dict[str, dict],
    items: list[dict],
    payload_builder,
    label: str,
) -> list[dict]:
    operations: list[dict] = []
    for item in items:
        name = item["name"]
        payload = payload_builder(item)
        if name in existing:
            operations.append({"kind": label, "name": name, "method": "SKIP", "status": "ok"})
            continue
        try:
            request(base_url, token, "POST", collection_path, vdom, payload)
            operations.append({"kind": label, "name": name, "method": "POST", "status": "ok"})
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            operations.append(
                {
                    "kind": label,
                    "name": name,
                    "method": "POST",
                    "status": "error",
                    "http_status": exc.code,
                    "body": body[:500],
                }
            )
    return operations


def run() -> int:
    if os.environ.get("CONFIRM_FORTIGATE_POLICY_PLAN_REVIEW", "") != "yes":
        return fail("Refusing to apply: set CONFIRM_FORTIGATE_POLICY_PLAN_REVIEW=yes")
    if os.environ.get("CONFIRM_FORTIGATE_POLICY_APPLY", "") != "yes":
        return fail("Refusing to apply: set CONFIRM_FORTIGATE_POLICY_APPLY=yes")

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
    vdom = intent["fortigate_policy_vdom"]
    operations: list[dict] = []

    try:
        existing_addresses = {item["name"]: item for item in list_results(base_url, token, "/api/v2/cmdb/firewall/address", vdom)}
        existing_zones = {item["name"]: item for item in list_results(base_url, token, "/api/v2/cmdb/system/zone", vdom)}
        existing_policies = {item["name"]: item for item in list_results(base_url, token, "/api/v2/cmdb/firewall/policy", vdom)}
    except urllib.error.HTTPError as exc:
        return fail(f"FortiGate API returned HTTP {exc.code} during pre-check")
    except urllib.error.URLError as exc:
        return fail(f"FortiGate API connection failed: {exc.reason}")

    operations.extend(
        apply_named_objects(
            base_url,
            token,
            vdom,
            "/api/v2/cmdb/firewall/address",
            existing_addresses,
            intent["fortigate_address_objects"],
            address_payload,
            "address",
        )
    )
    operations.extend(
        apply_named_objects(
            base_url,
            token,
            vdom,
            "/api/v2/cmdb/system/zone",
            existing_zones,
            intent["fortigate_zones"],
            zone_payload,
            "zone",
        )
    )
    operations.extend(
        apply_named_objects(
            base_url,
            token,
            vdom,
            "/api/v2/cmdb/firewall/policy",
            existing_policies,
            intent["fortigate_firewall_policies"],
            policy_payload,
            "policy",
        )
    )

    failed = [item for item in operations if item["status"] != "ok"]
    summary = {
        "applied_at_epoch": int(time.time()),
        "host": base_url.replace("https://", "").replace("http://", ""),
        "vdom": vdom,
        "operation_count": len(operations),
        "failed_count": len(failed),
        "operations": operations,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("# FortiGate policy apply")
    print(f"Host: {summary['host']}")
    print(f"VDOM: {vdom}")
    for item in operations:
        print(f"{item['status'].upper()}: {item['method']} {item['kind']} {item['name']}")
        if item["status"] != "ok":
            print(f"  HTTP {item.get('http_status')}: {item.get('body')}")
    print(f"Evidence: {OUT_FILE.relative_to(ROOT)}")
    return 2 if failed else 0


if __name__ == "__main__":
    raise SystemExit(run())
