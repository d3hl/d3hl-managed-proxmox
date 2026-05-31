#!/usr/bin/env python3
"""Read-only FortiGate discovery: interfaces, zones, policies, and address objects.

Uses FORTIGATE_HOST and FORTIOS_ACCESS_TOKEN from the environment (via `op run`).
Writes ansible/artifacts/fortigate-discovery.json without printing secret values.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = ROOT / "configs" / "fortigate-api-verify.py"
OUT_DIR = ROOT / "ansible" / "artifacts"
OUT_FILE = OUT_DIR / "fortigate-discovery.json"
VERIFY_FILE = OUT_DIR / "fortigate-verification.json"

HOMELAB_INTERFACES = {
    "hlvl",
    "mgt",
    "k8s",
    "Wifi",
    "vsvc",
    "vapps",
    "vlab",
    "vdmz",
    "x2",
}

HOMELAB_ZONES = {
    "HL",
    "VSVC",
    "VAPPS",
    "VLAB",
    "VDMZ",
}


def load_verify_module():
    spec = importlib.util.spec_from_file_location("fortigate_api_verify", VERIFY_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {VERIFY_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def policy_summary(item: dict) -> dict:
    return {
        "policyid": item.get("policyid"),
        "name": item.get("name"),
        "status": item.get("status"),
        "action": item.get("action"),
        "srcintf": item.get("srcintf"),
        "dstintf": item.get("dstintf"),
        "srcaddr": item.get("srcaddr"),
        "dstaddr": item.get("dstaddr"),
        "service": item.get("service"),
        "nat": item.get("nat"),
        "comments": item.get("comments"),
    }


def zone_summary(item: dict) -> dict:
    return {
        "name": item.get("name"),
        "interface": item.get("interface"),
        "intrazone": item.get("intrazone"),
    }


def address_summary(item: dict) -> dict:
    return {
        "name": item.get("name"),
        "type": item.get("type"),
        "subnet": item.get("subnet"),
        "interface": item.get("interface"),
    }


def homelab_related_policy(item: dict) -> bool:
    names: set[str] = set()
    for key in ("srcintf", "dstintf"):
        for entry in item.get(key) or []:
            if isinstance(entry, dict):
                names.add(str(entry.get("name", "")))
            else:
                names.add(str(entry))
    return bool(names & (HOMELAB_INTERFACES | HOMELAB_ZONES))


def discover_policies_and_zones(verify_mod) -> dict:
    host = os.environ.get("FORTIGATE_HOST", "")
    token = os.environ.get("FORTIOS_ACCESS_TOKEN", "")
    base_url = verify_mod.normalize_host(host)

    zones_resp = verify_mod.api_get(base_url, token, "/api/v2/cmdb/system/zone")
    policies_resp = verify_mod.api_get(base_url, token, "/api/v2/cmdb/firewall/policy")
    addresses_resp = verify_mod.api_get(base_url, token, "/api/v2/cmdb/firewall/address")

    zones = [zone_summary(item) for item in zones_resp.get("results", [])]
    policies = [policy_summary(item) for item in policies_resp.get("results", [])]
    homelab_policies = [p for p in policies if homelab_related_policy(p)]

    homelab_subnets = ("10.10.", "10.11.", "10.20.", "10.99.", "10.100.")
    addresses = []
    for item in addresses_resp.get("results", []):
        subnet = str(item.get("subnet", ""))
        name = str(item.get("name", ""))
        if any(subnet.startswith(prefix) for prefix in homelab_subnets) or name.startswith("NET_"):
            addresses.append(address_summary(item))

    return {
        "zone_count": len(zones),
        "zones": zones,
        "policy_count": len(policies),
        "homelab_related_policy_count": len(homelab_policies),
        "homelab_related_policies": homelab_policies,
        "homelab_address_object_count": len(addresses),
        "homelab_address_objects": addresses,
    }


def run() -> int:
    verify_mod = load_verify_module()

    print("# FortiGate read-only discovery")
    print(f"Host: {os.environ.get('FORTIGATE_HOST', '')}")
    print(f"VDOM: {verify_mod.VDOM}")

    verify_code = verify_mod.run()
    if not VERIFY_FILE.is_file():
        return verify_mod.fail(f"Interface verification artifact missing: {VERIFY_FILE}")

    verification = json.loads(VERIFY_FILE.read_text(encoding="utf-8"))

    try:
        network = discover_policies_and_zones(verify_mod)
    except Exception as exc:  # noqa: BLE001 - surface API errors to operator
        return verify_mod.fail(f"Policy/zone discovery failed: {exc}")

    discovery = {
        "discovered_at_epoch": int(time.time()),
        "vdom": verify_mod.VDOM,
        "fortigate_host": verification.get("fortigate_host"),
        "interfaces": {
            "total_seen": verification.get("total_interfaces_seen"),
            "target_checks": verification.get("checks"),
            "vlan_interfaces": [
                item
                for item in verification.get("actual_interfaces", [])
                if item.get("type") == "vlan"
            ],
            "match_count": verification.get("match_count"),
            "missing_count": verification.get("missing_count"),
            "mismatch_count": verification.get("mismatch_count"),
        },
        "zones_and_policies": network,
    }

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(discovery, indent=2), encoding="utf-8")

    print(
        f"Interface targets: {verification.get('target_count')} "
        f"({verification.get('match_count')} match)"
    )
    print(f"Zones: {network['zone_count']}")
    print(f"Firewall policies (total): {network['policy_count']}")
    print(f"Homelab-related policies: {network['homelab_related_policy_count']}")
    print(f"Homelab-related address objects: {network['homelab_address_object_count']}")
    print(f"Evidence: {OUT_FILE.relative_to(ROOT)}")

    homelab_policies = network["homelab_related_policies"]
    if homelab_policies:
        print("Homelab-related policies:")
        for item in homelab_policies[:20]:
            print(
                f"  id={item.get('policyid')} name={item.get('name')!r} "
                f"action={item.get('action')} "
                f"src={item.get('srcintf')} dst={item.get('dstintf')}"
            )
        if len(homelab_policies) > 20:
            print(f"  ... and {len(homelab_policies) - 20} more (see artifact)")

    return 0 if verify_code == 0 else verify_code


if __name__ == "__main__":
    raise SystemExit(run())
