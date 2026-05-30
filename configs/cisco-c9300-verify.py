#!/usr/bin/env python3
"""Verify C9300 VLAN, trunk, SVI, and persistence state against repo intent.

Credentials are read from environment variables so the script can run through
1Password `op run` without printing secrets.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from pathlib import Path

from netmiko import ConnectHandler
from netmiko.exceptions import NetmikoAuthenticationException, NetmikoTimeoutException


ROOT = Path(__file__).resolve().parents[1]
PLAN_FILE = ROOT / "data" / "network-plan.json"
OUT_DIR = ROOT / "ansible" / "artifacts"
OUT_FILE = OUT_DIR / "cisco-c9300-verification.json"


def parse_vlan_list(value: str) -> set[int]:
    vlans: set[int] = set()
    for part in value.replace(" ", "").split(","):
        if not part:
            continue
        if "-" in part:
            start, end = part.split("-", 1)
            vlans.update(range(int(start), int(end) + 1))
        else:
            vlans.add(int(part))
    return vlans


def format_vlan_list(vlans: set[int] | list[int]) -> str:
    return ",".join(str(vlan) for vlan in sorted(vlans))


def required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def connect():
    host = os.environ.get("CISCO_HOST", "").strip() or "10.10.10.1"
    username = required_env("CISCO_USERNAME")
    password = required_env("CISCO_PASSWORD")
    enable_password = os.environ.get("CISCO_ENABLE_PASSWORD", "").strip()
    device = {
        "device_type": "cisco_ios",
        "host": host,
        "username": username,
        "password": password,
        "secret": enable_password or password,
        "fast_cli": False,
    }
    session = ConnectHandler(**device)
    if enable_password:
        session.enable()
    return session, host


def run_command(session, command: str) -> str:
    return session.send_command(command, read_timeout=45)


def load_plan() -> dict:
    return json.loads(PLAN_FILE.read_text(encoding="utf-8"))


def parse_allowed_from_running_config(text: str) -> set[int]:
    match = re.search(r"^\s*switchport trunk allowed vlan\s+(.+)$", text, re.MULTILINE)
    if not match:
        return set()
    return parse_vlan_list(match.group(1).strip())


def parse_vlan_ids_from_brief(text: str) -> set[int]:
    vlans: set[int] = set()
    for line in text.splitlines():
        match = re.match(r"^\s*(\d+)\s+\S+", line)
        if match:
            vlans.add(int(match.group(1)))
    return vlans


def parse_vlan10_status(text: str) -> dict:
    for line in text.splitlines():
        if line.lower().startswith("vlan10"):
            parts = line.split()
            return {
                "line": line,
                "ip": parts[1] if len(parts) > 1 else "",
                "status": parts[-2] if len(parts) > 2 else "",
                "protocol": parts[-1] if len(parts) > 1 else "",
            }
    return {"line": "", "ip": "", "status": "", "protocol": ""}


def check_trunk(name: str, expected: list[int], running_config: str) -> dict:
    actual = parse_allowed_from_running_config(running_config)
    expected_set = set(expected)
    return {
        "interface": name,
        "expected_allowed_vlans": sorted(expected_set),
        "actual_allowed_vlans": sorted(actual),
        "missing": sorted(expected_set - actual),
        "extra": sorted(actual - expected_set),
        "match": actual == expected_set,
    }


def build_expected_trunks(plan: dict) -> list[dict]:
    trunks = plan["trunks"]
    expected = [
        {
            "interface": trunks["c9300_to_fortigate"]["interface"],
            "allowed_vlans": trunks["c9300_to_fortigate"]["allowed_vlans"],
        }
    ]
    proxmox_vlans = trunks["c9300_to_proxmox"]["allowed_vlans"]
    for item in trunks["c9300_to_proxmox"]["interfaces"]:
        expected.append({"interface": item["interface"], "allowed_vlans": proxmox_vlans})
    return expected


def gather(session, plan: dict) -> dict:
    expected_trunks = build_expected_trunks(plan)
    trunk_configs = {
        item["interface"]: run_command(session, f"show running-config interface {item['interface']}")
        for item in expected_trunks
    }
    vlan_brief = run_command(session, "show vlan brief")
    ip_brief = run_command(session, "show ip interface brief")
    vlan10_running = run_command(session, "show running-config interface vlan10")
    interfaces_trunk = run_command(session, "show interfaces trunk")
    ping_vlan10 = run_command(session, "ping 10.10.10.2 source vlan10")
    startup_vlan10 = run_command(session, "show startup-config interface vlan10")
    startup_fgt = run_command(session, "show startup-config interface TwentyFiveGigE2/1/2")

    expected_vlans = sorted(int(item["vlan"]) for item in plan["vlans"])
    actual_vlans = parse_vlan_ids_from_brief(vlan_brief)
    trunk_checks = [
        check_trunk(item["interface"], item["allowed_vlans"], trunk_configs[item["interface"]])
        for item in expected_trunks
    ]
    vlan10_status = parse_vlan10_status(ip_brief)

    return {
        "raw": {
            "show_vlan_brief": vlan_brief,
            "show_interfaces_trunk": interfaces_trunk,
            "show_ip_interface_brief": ip_brief,
            "show_running_config_interface_vlan10": vlan10_running,
            "ping_10_10_10_2_source_vlan10": ping_vlan10,
            "show_startup_config_interface_vlan10": startup_vlan10,
            "show_startup_config_interface_fortigate_trunk": startup_fgt,
            "trunk_running_configs": trunk_configs,
        },
        "checks": {
            "vlans": {
                "expected": expected_vlans,
                "actual": sorted(vlan for vlan in actual_vlans if vlan in set(expected_vlans)),
                "missing": sorted(set(expected_vlans) - actual_vlans),
                "match": not (set(expected_vlans) - actual_vlans),
            },
            "trunks": trunk_checks,
            "vlan10": {
                "expected_ip": "10.10.10.1",
                "actual": vlan10_status,
                "running_has_expected_ip": "ip address 10.10.10.1 255.255.255.0" in vlan10_running,
                "up_up": vlan10_status.get("status") == "up" and vlan10_status.get("protocol") == "up",
            },
            "ping_vlan10_to_fortigate": {
                "success": "Success rate is 100 percent" in ping_vlan10 or "Success rate is 80 percent" in ping_vlan10,
                "output": ping_vlan10,
            },
        },
    }


def summarize(host: str, gathered: dict, saved: bool = False) -> dict:
    checks = gathered["checks"]
    trunk_failures = [item for item in checks["trunks"] if not item["match"]]
    failures = []
    if not checks["vlans"]["match"]:
        failures.append("vlans")
    if trunk_failures:
        failures.append("trunks")
    if not checks["vlan10"]["running_has_expected_ip"] or not checks["vlan10"]["up_up"]:
        failures.append("vlan10")
    if not checks["ping_vlan10_to_fortigate"]["success"]:
        failures.append("ping_vlan10_to_fortigate")
    return {
        "verified_at_epoch": int(time.time()),
        "host": host,
        "saved": saved,
        "pass": not failures,
        "failures": failures,
        "vlan_missing": checks["vlans"]["missing"],
        "trunk_failures": trunk_failures,
        "vlan10": checks["vlan10"],
        "ping_vlan10_to_fortigate_success": checks["ping_vlan10_to_fortigate"]["success"],
    }


def write_artifact(summary: dict, gathered: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(json.dumps({"summary": summary, **gathered}, indent=2), encoding="utf-8")


def print_summary(summary: dict, gathered: dict) -> None:
    print("# C9300 verification")
    print(f"Host: {summary['host']}")
    print(f"Result: {'PASS' if summary['pass'] else 'FAIL'}")
    print(f"Saved this run: {'yes' if summary['saved'] else 'no'}")
    print(f"VLAN missing: {format_vlan_list(summary['vlan_missing']) or 'none'}")
    for item in gathered["checks"]["trunks"]:
        status = "ok" if item["match"] else "mismatch"
        print(
            f"Trunk {item['interface']}: {status} "
            f"expected={format_vlan_list(item['expected_allowed_vlans'])} "
            f"actual={format_vlan_list(item['actual_allowed_vlans'])}"
        )
    vlan10 = summary["vlan10"]
    print(f"Vlan10: ip={vlan10['actual'].get('ip')} status={vlan10['actual'].get('status')}/{vlan10['actual'].get('protocol')}")
    print(f"Ping 10.10.10.2 source vlan10: {'ok' if summary['ping_vlan10_to_fortigate_success'] else 'failed'}")
    print(f"Evidence: {OUT_FILE.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-memory", action="store_true", help="Save running-config to startup-config after verification passes")
    args = parser.parse_args()

    if args.write_memory and os.environ.get("CONFIRM_CISCO_WRITE_MEMORY", "") != "yes":
        print("ERROR: refusing to save; set CONFIRM_CISCO_WRITE_MEMORY=yes after verification.", file=sys.stderr)
        return 1

    try:
        session, host = connect()
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (NetmikoAuthenticationException, NetmikoTimeoutException) as exc:
        print(f"ERROR: Cisco SSH connection failed: {exc}", file=sys.stderr)
        return 1

    try:
        plan = load_plan()
        gathered = gather(session, plan)
        summary = summarize(host, gathered)
        if args.write_memory:
            if not summary["pass"]:
                write_artifact(summary, gathered)
                print_summary(summary, gathered)
                print("ERROR: refusing write memory because verification failed.", file=sys.stderr)
                return 2
            save_output = session.save_config()
            gathered["raw"]["write_memory"] = save_output
            gathered = gather(session, plan)
            summary = summarize(host, gathered, saved=True)
            summary["write_memory_output"] = save_output
        write_artifact(summary, gathered)
        print_summary(summary, gathered)
        return 0 if summary["pass"] else 2
    finally:
        session.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
