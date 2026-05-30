#!/usr/bin/env python3
"""Compare live FortiGate state against repo intent (interfaces, trunk VLANs, policies).

Uses FORTIGATE_HOST and FORTIOS_ACCESS_TOKEN from the environment.
Writes ansible/artifacts/fortigate-repo-live-verify.json
"""

from __future__ import annotations

import importlib.util
import ipaddress
import json
import os
import sys
import time
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = ROOT / "configs" / "fortigate-api-verify.py"
INTERFACE_VARS = ROOT / "ansible" / "group_vars" / "fortigates.yml"
POLICY_VARS = ROOT / "ansible" / "group_vars" / "fortigate_policies.yml"
NETWORK_PLAN = ROOT / "data" / "network-plan.json"
OUT_FILE = ROOT / "ansible" / "artifacts" / "fortigate-repo-live-verify.json"

# VLANs that must NOT exist as FortiGate routed interfaces
FORBIDDEN_VLAN_IDS = {20, 99}


def load_verify_module():
    spec = importlib.util.spec_from_file_location("fortigate_api_verify", VERIFY_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {VERIFY_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def normalize_ip(value: str | None) -> str | None:
    if not value:
        return None
    first = str(value).split()[0]
    try:
        return str(ipaddress.ip_interface(first).ip)
    except ValueError:
        return first


def normalize_subnet(value: str) -> str:
    parts = value.split()
    if len(parts) == 2:
        net = ipaddress.ip_network(f"{parts[0]}/{parts[1]}", strict=False)
        return str(net)
    return value


def names_from_refs(items: list) -> set[str]:
    out: set[str] = set()
    for item in items or []:
        if isinstance(item, dict):
            out.add(str(item.get("name", "")))
        else:
            out.add(str(item))
    return out


def compare_sets(label: str, expected: set[str], actual: set[str]) -> dict:
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    status = "match" if not missing and not extra else "mismatch"
    return {
        "label": label,
        "status": status,
        "expected": sorted(expected),
        "actual": sorted(actual),
        "missing": missing,
        "extra": extra,
    }


def policy_signature(item: dict) -> dict:
    return {
        "name": item.get("name"),
        "status": item.get("status"),
        "action": item.get("action"),
        "srcintf": sorted(names_from_refs(item.get("srcintf"))),
        "dstintf": sorted(names_from_refs(item.get("dstintf"))),
        "srcaddr": sorted(names_from_refs(item.get("srcaddr"))),
        "dstaddr": sorted(names_from_refs(item.get("dstaddr"))),
        "service": sorted(names_from_refs(item.get("service"))),
        "nat": item.get("nat", "disable"),
        "schedule": item.get("schedule", "always"),
    }


def run() -> int:
    verify = load_verify_module()
    host = os.environ.get("FORTIGATE_HOST", "")
    token = os.environ.get("FORTIOS_ACCESS_TOKEN", "")
    if not host or not token:
        print("ERROR: FORTIGATE_HOST and FORTIOS_ACCESS_TOKEN are required", file=sys.stderr)
        return 1

    base_url = verify.normalize_host(host)
    vdom = verify.VDOM

    interface_intent = yaml.safe_load(INTERFACE_VARS.read_text(encoding="utf-8"))
    policy_intent = yaml.safe_load(POLICY_VARS.read_text(encoding="utf-8"))
    network_plan = json.loads(NETWORK_PLAN.read_text(encoding="utf-8"))

    interfaces = verify.api_get(base_url, token, "/api/v2/cmdb/system/interface").get("results", [])
    zones = verify.api_get(base_url, token, "/api/v2/cmdb/system/zone").get("results", [])
    addresses = verify.api_get(base_url, token, "/api/v2/cmdb/firewall/address").get("results", [])
    policies = verify.api_get(base_url, token, "/api/v2/cmdb/firewall/policy").get("results", [])

    by_name_iface = {item["name"]: item for item in interfaces}
    by_name_zone = {item["name"]: item for item in zones}
    by_name_addr = {item["name"]: item for item in addresses}
    by_name_policy = {item["name"]: item for item in policies}

    checks: list[dict] = []

    # Parent trunk interface
    parent = interface_intent["fortigate_parent_interface"]
    if parent in by_name_iface:
        checks.append({"label": f"parent interface {parent}", "status": "match", "actual": parent})
    else:
        checks.append({"label": f"parent interface {parent}", "status": "missing", "actual": None})

    # Repo-managed interfaces (existing + vlan candidates)
    for target in (
        interface_intent.get("fortigate_existing_interfaces", [])
        + interface_intent.get("fortigate_vlan_interfaces", [])
    ):
        name = target["name"]
        actual = by_name_iface.get(name)
        if not actual:
            checks.append({"label": f"interface {name}", "status": "missing", "expected": target})
            continue
        mismatches = []
        if target.get("type") and actual.get("type") != target["type"]:
            mismatches.append("type")
        if "vlanid" in target and int(actual.get("vlanid", -1)) != int(target["vlanid"]):
            mismatches.append("vlanid")
        if normalize_ip(actual.get("ip")) != normalize_ip(target["ip"]):
            mismatches.append("ip")
        if target.get("type") == "vlan" and actual.get("interface") != parent:
            mismatches.append("parent")
        checks.append(
            {
                "label": f"interface {name}",
                "status": "match" if not mismatches else "mismatch",
                "mismatches": mismatches,
                "expected": target,
                "actual": {
                    "type": actual.get("type"),
                    "vlanid": actual.get("vlanid"),
                    "ip": actual.get("ip"),
                    "interface": actual.get("interface"),
                    "status": actual.get("status"),
                },
            }
        )

    # Forbidden VLAN interfaces
    for item in interfaces:
        if item.get("type") != "vlan":
            continue
        vlanid = int(item.get("vlanid", 0))
        if vlanid in FORBIDDEN_VLAN_IDS:
            checks.append(
                {
                    "label": f"forbidden vlan interface VLAN{vlanid}",
                    "status": "unexpected",
                    "actual": item.get("name"),
                }
            )

    # Trunk VLAN coverage: C9300-to-FortiGate allowed VLANs should have FG VLAN iface on x2
    trunk_vlans = set(network_plan["trunks"]["c9300_to_fortigate"]["allowed_vlans"])
    live_vlan_on_x2 = {
        int(item["vlanid"])
        for item in interfaces
        if item.get("type") == "vlan"
        and item.get("interface") == parent
        and item.get("vlanid") not in (None, "", 0)
    }
    # VLAN 20 is intentionally not on FortiGate
    expected_trunk_vlans = trunk_vlans - {20}
    checks.append(compare_sets("trunk VLANs on parent x2", expected_trunk_vlans, live_vlan_on_x2))

    # Address objects
    for item in policy_intent["fortigate_address_objects"]:
        name = item["name"]
        actual = by_name_addr.get(name)
        if not actual:
            checks.append({"label": f"address {name}", "status": "missing", "expected": item})
            continue
        mismatches = []
        if actual.get("type") != item["type"]:
            mismatches.append("type")
        if actual.get("interface") != item["interface"]:
            mismatches.append("interface")
        if normalize_subnet(str(actual.get("subnet", ""))) != normalize_subnet(item["subnet"]):
            mismatches.append("subnet")
        checks.append(
            {
                "label": f"address {name}",
                "status": "match" if not mismatches else "mismatch",
                "mismatches": mismatches,
                "expected": item,
                "actual": {
                    "type": actual.get("type"),
                    "interface": actual.get("interface"),
                    "subnet": actual.get("subnet"),
                },
            }
        )

    # Zones
    for item in policy_intent["fortigate_zones"]:
        name = item["name"]
        actual = by_name_zone.get(name)
        if not actual:
            checks.append({"label": f"zone {name}", "status": "missing", "expected": item})
            continue
        live_ifaces = {
            entry.get("interface-name") or entry.get("q_origin_key")
            for entry in actual.get("interface", [])
        }
        mismatches = []
        if item["interface"] not in live_ifaces:
            mismatches.append("interface")
        if actual.get("intrazone") != item.get("intrazone", "deny"):
            mismatches.append("intrazone")
        checks.append(
            {
                "label": f"zone {name}",
                "status": "match" if not mismatches else "mismatch",
                "mismatches": mismatches,
                "expected": item,
                "actual": {
                    "interface": sorted(live_ifaces),
                    "intrazone": actual.get("intrazone"),
                },
            }
        )

    # Firewall policies (repo-managed only)
    for item in policy_intent["fortigate_firewall_policies"]:
        name = item["name"]
        actual = by_name_policy.get(name)
        if not actual:
            checks.append({"label": f"policy {name}", "status": "missing", "expected": item})
            continue
        expected_sig = {
            "status": item.get("status", "enable"),
            "action": item["action"],
            "srcintf": sorted(item["srcintf"]),
            "dstintf": sorted(item["dstintf"]),
            "srcaddr": sorted(item["srcaddr"]),
            "dstaddr": sorted(item["dstaddr"]),
            "service": sorted(item["service"]),
            "nat": item.get("nat", "disable"),
            "schedule": item.get("schedule", "always"),
        }
        actual_sig = policy_signature(actual)
        mismatches = [k for k in expected_sig if expected_sig[k] != actual_sig.get(k)]
        checks.append(
            {
                "label": f"policy {name}",
                "status": "match" if not mismatches else "mismatch",
                "mismatches": mismatches,
                "expected": expected_sig,
                "actual": actual_sig,
            }
        )

    # Informational: live-only policies/zones not in repo intent
    repo_policy_names = {p["name"] for p in policy_intent["fortigate_firewall_policies"]}
    repo_zone_names = {z["name"] for z in policy_intent["fortigate_zones"]}
    live_extra_policies = sorted(
        p["name"] for p in policies if p.get("name") not in repo_policy_names
    )
    live_extra_zones = sorted(
        z["name"]
        for z in zones
        if z.get("name") not in repo_zone_names
        and z.get("name") not in {"HL", "WIFI", "vpn_d3ipsec_zone"}
    )

    summary = {
        "verified_at_epoch": int(time.time()),
        "fortigate_host": base_url.replace("https://", "").replace("http://", ""),
        "vdom": vdom,
        "parent_interface": parent,
        "check_count": len(checks),
        "match_count": sum(1 for c in checks if c["status"] == "match"),
        "mismatch_count": sum(1 for c in checks if c["status"] == "mismatch"),
        "missing_count": sum(1 for c in checks if c["status"] == "missing"),
        "unexpected_count": sum(1 for c in checks if c["status"] == "unexpected"),
        "live_extra_policies": live_extra_policies,
        "live_extra_zones": live_extra_zones,
        "checks": checks,
    }

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("# FortiGate repo vs live verification")
    print(f"Host: {summary['fortigate_host']}")
    print(f"Checks: {summary['check_count']} | match: {summary['match_count']} | "
          f"mismatch: {summary['mismatch_count']} | missing: {summary['missing_count']} | "
          f"unexpected: {summary['unexpected_count']}")
    print(f"Evidence: {OUT_FILE.relative_to(ROOT)}")

    for check in checks:
        if check["status"] != "match":
            print(f"{check['status'].upper()}: {check['label']}")
            if check.get("mismatches"):
                print(f"  fields: {', '.join(check['mismatches'])}")
            if check.get("missing"):
                print(f"  missing: {check['missing']}")
            if check.get("extra"):
                print(f"  extra: {check['extra']}")

    if live_extra_policies:
        print("Live-only policies (not in repo intent, informational):")
        for name in live_extra_policies:
            print(f"  - {name}")
    if live_extra_zones:
        print("Live-only zones (not in repo intent, informational):")
        for name in live_extra_zones:
            print(f"  - {name}")

    failed = (
        summary["mismatch_count"] + summary["missing_count"] + summary["unexpected_count"]
    )
    return 0 if failed == 0 else 2


if __name__ == "__main__":
    raise SystemExit(run())
