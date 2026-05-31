#!/usr/bin/env python3
"""Verify FortiGate vs repo, align HOMELAB-TO-MGMT-LIMITED if needed, backup running config.

FortiOS persists CMDB changes automatically; this script records a config backup artifact
as evidence of the saved running configuration.

Requires:
  FORTIGATE_HOST, FORTIOS_ACCESS_TOKEN
  CONFIRM_FORTIGATE_PERSISTENT_SAVE=yes
"""

from __future__ import annotations

import importlib.util
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
VERIFY_SCRIPT = ROOT / "configs" / "fortigate-api-verify.py"
REPO_VERIFY_SCRIPT = ROOT / "configs" / "fortigate-repo-live-verify.py"
POLICY_VARS = ROOT / "ansible" / "group_vars" / "fortigate_policies.yml"
OUT_DIR = ROOT / "ansible" / "artifacts"
OUT_FILE = OUT_DIR / "fortigate-persistent-save.json"
BACKUP_FILE = OUT_DIR / "fortigate-config-backup.conf"


def fail(message: str) -> int:
    print(f"ERROR: {message}", file=sys.stderr)
    return 1


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def named_refs(names: list[str]) -> list[dict]:
    return [{"name": name} for name in names]


def policy_intent_by_name() -> dict:
    data = yaml.safe_load(POLICY_VARS.read_text(encoding="utf-8"))
    return {item["name"]: item for item in data["fortigate_firewall_policies"]}


def fix_homelab_policy(verify_mod, base_url: str, token: str, vdom: str) -> dict | None:
    intent = policy_intent_by_name().get("HOMELAB-TO-MGMT-LIMITED")
    if not intent:
        return None

    policies = verify_mod.api_get(base_url, token, "/api/v2/cmdb/firewall/policy").get("results", [])
    live = next((p for p in policies if p.get("name") == "HOMELAB-TO-MGMT-LIMITED"), None)
    if not live:
        return {"status": "missing", "name": "HOMELAB-TO-MGMT-LIMITED"}

    expected_srcaddr = set(intent["srcaddr"])
    live_srcaddr = {
        entry.get("name") if isinstance(entry, dict) else str(entry)
        for entry in live.get("srcaddr", [])
    }
    if live_srcaddr == expected_srcaddr:
        return {"status": "ok", "action": "no_change", "name": "HOMELAB-TO-MGMT-LIMITED"}

    policyid = live["policyid"]
    payload = {
        "srcintf": named_refs(intent["srcintf"]),
        "dstintf": named_refs(intent["dstintf"]),
        "srcaddr": named_refs(intent["srcaddr"]),
        "dstaddr": named_refs(intent["dstaddr"]),
        "service": named_refs(intent["service"]),
        "action": intent["action"],
        "status": intent.get("status", "enable"),
        "schedule": intent.get("schedule", "always"),
        "nat": intent.get("nat", "disable"),
        "comments": intent.get("comments", ""),
    }
    path = f"/api/v2/cmdb/firewall/policy/{policyid}"
    query = urllib.parse.urlencode({"vdom": vdom})
    url = f"{base_url}{path}?{query}"
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        },
        method="PUT",
    )
    context = ssl._create_unverified_context()
    try:
        with urllib.request.urlopen(req, timeout=30, context=context) as response:
            response.read()
        return {
            "status": "ok",
            "action": "updated",
            "name": "HOMELAB-TO-MGMT-LIMITED",
            "policyid": policyid,
            "removed_srcaddr": sorted(live_srcaddr - expected_srcaddr),
        }
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        return {
            "status": "error",
            "name": "HOMELAB-TO-MGMT-LIMITED",
            "http_status": exc.code,
            "body": body[:500],
        }


def backup_config(verify_mod, base_url: str, token: str, vdom: str) -> dict:
    query = urllib.parse.urlencode({"scope": "global", "vdom": vdom})
    url = f"{base_url}/api/v2/monitor/system/config/backup?{query}"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {token}"},
        method="POST",
    )
    context = ssl._create_unverified_context()
    with urllib.request.urlopen(req, timeout=120, context=context) as response:
        content = response.read()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_FILE.write_bytes(content)
    return {
        "status": "ok",
        "backup_path": str(BACKUP_FILE.relative_to(ROOT)),
        "bytes": len(content),
    }


def run_repo_verify() -> int:
    repo_verify = load_module(REPO_VERIFY_SCRIPT, "fortigate_repo_live_verify")
    return repo_verify.run()


def run() -> int:
    if os.environ.get("CONFIRM_FORTIGATE_PERSISTENT_SAVE", "") != "yes":
        return fail("Refusing to persist: set CONFIRM_FORTIGATE_PERSISTENT_SAVE=yes")

    host = os.environ.get("FORTIGATE_HOST", "")
    token = os.environ.get("FORTIOS_ACCESS_TOKEN", "")
    if not host or not token:
        return fail("FORTIGATE_HOST and FORTIOS_ACCESS_TOKEN are required")

    verify_mod = load_module(VERIFY_SCRIPT, "fortigate_api_verify")
    base_url = verify_mod.normalize_host(host)
    vdom = verify_mod.VDOM

    print("# FortiGate persistent save workflow")
    print(f"Host: {base_url}")

    policy_fix = fix_homelab_policy(verify_mod, base_url, token, vdom)
    if policy_fix:
        print(f"Policy align: {policy_fix.get('status')} {policy_fix.get('action', '')}")
        if policy_fix.get("status") == "error":
            print(f"  HTTP {policy_fix.get('http_status')}: {policy_fix.get('body')}")
            return 1

    print("Running repo-vs-live verification...")
    verify_code = run_repo_verify()
    if verify_code != 0:
        return fail("Repo-vs-live verification failed; persistent save aborted")

    try:
        backup = backup_config(verify_mod, base_url, token, vdom)
    except urllib.error.HTTPError as exc:
        return fail(f"Config backup failed HTTP {exc.code}")
    except urllib.error.URLError as exc:
        return fail(f"Config backup connection failed: {exc.reason}")

    summary = {
        "saved_at_epoch": int(time.time()),
        "host": base_url.replace("https://", "").replace("http://", ""),
        "vdom": vdom,
        "note": "FortiOS persists CMDB/API changes automatically; backup artifact records running config.",
        "policy_alignment": policy_fix,
        "repo_live_verify": "pass",
        "backup": backup,
    }
    OUT_FILE.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("Repo-vs-live verification: PASS")
    print(f"Config backup: {backup['backup_path']} ({backup['bytes']} bytes)")
    print(f"Evidence: {OUT_FILE.relative_to(ROOT)}")
    print("FortiGate running configuration is persisted (CMDB auto-save) and backed up.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
