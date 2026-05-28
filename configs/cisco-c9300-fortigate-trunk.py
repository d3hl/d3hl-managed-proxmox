#!/usr/bin/env python3
"""Review or update the C9300-to-FortiGate trunk allowed VLAN list.

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
OUT_DIR = ROOT / "ansible" / "artifacts"
OUT_FILE = OUT_DIR / "cisco-fortigate-trunk-review.json"

DEFAULT_INTERFACE = "TwentyFiveGigE2/1/2"
TARGET_VLANS = {30, 40, 50, 60}
PRESERVE_VLANS = {10, 11, 100}


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


def format_vlan_list(vlans: set[int]) -> str:
    return ",".join(str(vlan) for vlan in sorted(vlans))


def parse_allowed_from_running_config(text: str) -> set[int]:
    match = re.search(r"^\s*switchport trunk allowed vlan\s+(.+)$", text, re.MULTILINE)
    if not match:
        return set()
    return parse_vlan_list(match.group(1).strip())


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
    return session.send_command(command, read_timeout=30)


def gather_state(session, interface: str) -> dict:
    running_interface = run_command(session, f"show running-config interface {interface}")
    return {
        "running_interface": running_interface,
        "interfaces_trunk": run_command(session, "show interfaces trunk"),
        "vlan_brief": run_command(session, "show vlan brief"),
        "ip_interface_brief": run_command(session, "show ip interface brief"),
        "vlan10_running": run_command(session, "show running-config interface vlan10"),
        "ping_vlan10_to_fortigate": run_command(session, "ping 10.10.10.2 source vlan10"),
        "allowed_vlans": sorted(parse_allowed_from_running_config(running_interface)),
    }


def summarize_state(host: str, interface: str, before: dict, after: dict | None = None) -> dict:
    before_allowed = set(before["allowed_vlans"])
    desired = before_allowed | TARGET_VLANS | PRESERVE_VLANS
    summary = {
        "verified_at_epoch": int(time.time()),
        "host": host,
        "interface": interface,
        "target_add_vlans": sorted(TARGET_VLANS),
        "must_preserve_vlans": sorted(PRESERVE_VLANS),
        "before_allowed_vlans": sorted(before_allowed),
        "desired_allowed_vlans": sorted(desired),
        "missing_before": sorted(TARGET_VLANS - before_allowed),
        "changed": False,
        "after_allowed_vlans": None,
        "missing_after": None,
        "validation": {
            "vlan10_ping_success": "Success rate is 100 percent" in before["ping_vlan10_to_fortigate"],
        },
    }
    if after:
        after_allowed = set(after["allowed_vlans"])
        summary["changed"] = before_allowed != after_allowed
        summary["after_allowed_vlans"] = sorted(after_allowed)
        summary["missing_after"] = sorted(TARGET_VLANS - after_allowed)
        summary["validation"]["vlan10_ping_success_after"] = (
            "Success rate is 100 percent" in after["ping_vlan10_to_fortigate"]
        )
    return summary


def write_artifact(summary: dict, before: dict, after: dict | None) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_FILE.write_text(
        json.dumps(
            {
                "summary": summary,
                "before": before,
                "after": after,
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def print_summary(summary: dict) -> None:
    print("# C9300 FortiGate trunk review")
    print(f"Host: {summary['host']}")
    print(f"Interface: {summary['interface']}")
    print(f"Before allowed VLANs: {format_vlan_list(set(summary['before_allowed_vlans']))}")
    print(f"Target add VLANs: {format_vlan_list(set(summary['target_add_vlans']))}")
    print(f"Desired allowed VLANs: {format_vlan_list(set(summary['desired_allowed_vlans']))}")
    print(f"Missing before: {format_vlan_list(set(summary['missing_before'])) or 'none'}")
    if summary["after_allowed_vlans"] is not None:
        print(f"After allowed VLANs: {format_vlan_list(set(summary['after_allowed_vlans']))}")
        print(f"Missing after: {format_vlan_list(set(summary['missing_after'])) or 'none'}")
    print(f"VLAN10 ping before: {'ok' if summary['validation']['vlan10_ping_success'] else 'failed'}")
    if "vlan10_ping_success_after" in summary["validation"]:
        result = "ok" if summary["validation"]["vlan10_ping_success_after"] else "failed"
        print(f"VLAN10 ping after: {result}")
    print(f"Evidence: {OUT_FILE.relative_to(ROOT)}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--interface", default=DEFAULT_INTERFACE)
    parser.add_argument("--apply", action="store_true", help="Apply additive trunk VLAN update")
    args = parser.parse_args()

    if args.apply and os.environ.get("CONFIRM_CISCO_TRUNK_APPLY", "") != "yes":
        print(
            "ERROR: refusing to apply; set CONFIRM_CISCO_TRUNK_APPLY=yes after reviewing discovery.",
            file=sys.stderr,
        )
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
        before = gather_state(session, args.interface)
        after = None
        before_allowed = set(before["allowed_vlans"])
        missing = TARGET_VLANS - before_allowed

        if args.apply and missing:
            add_list = format_vlan_list(missing)
            session.send_config_set(
                [
                    f"interface {args.interface}",
                    f"switchport trunk allowed vlan add {add_list}",
                ]
            )
            after = gather_state(session, args.interface)

        summary = summarize_state(host, args.interface, before, after)
        write_artifact(summary, before, after)
        print_summary(summary)

        if summary["after_allowed_vlans"] is not None:
            return 0 if not summary["missing_after"] else 2
        return 0 if not summary["missing_before"] else 2
    finally:
        session.disconnect()


if __name__ == "__main__":
    raise SystemExit(main())
