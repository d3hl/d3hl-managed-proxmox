#!/usr/bin/env python3
"""Minimal FortiGate REST API connectivity test (read-only).

Requires:
  FORTIGATE_HOST=https://10.99.99.2:7443
  FORTIOS_ACCESS_TOKEN=<bearer token or op:// ref resolved by wrapper>

Run:
  bash configs/fortigate-discover-op-run.sh   # full discovery
  # or after: eval "$(op signin --account my)"
  FORTIOS_ACCESS_TOKEN="$(op read 'op://d3HLPRV/FORTIOS_ACCESS_TOKEN/credential')" \\
    .venv/bin/python configs/fortigate-api-connect-test.py
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERIFY_SCRIPT = ROOT / "configs" / "fortigate-api-verify.py"


def load_verify_module():
    spec = importlib.util.spec_from_file_location("fortigate_api_verify", VERIFY_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load {VERIFY_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    verify = load_verify_module()
    host = os.environ.get("FORTIGATE_HOST", "")
    token = os.environ.get("FORTIOS_ACCESS_TOKEN", "")
    if not host or not token:
        print("ERROR: Set FORTIGATE_HOST and FORTIOS_ACCESS_TOKEN", file=sys.stderr)
        return 1
    if token.startswith("op://"):
        print("ERROR: Resolve op:// references before calling this script", file=sys.stderr)
        return 1

    base_url = verify.normalize_host(host)
    status = verify.api_get(base_url, token, "/api/v2/monitor/system/status")
    interfaces = verify.api_get(base_url, token, "/api/v2/cmdb/system/interface")

    print("# FortiGate REST API connectivity")
    print(f"Host: {base_url}")
    print(f"VDOM: {verify.VDOM}")
    print(f"Hostname: {status.get('results', {}).get('hostname', 'unknown')}")
    print(f"Version: {status.get('version', 'unknown')}")
    print(f"Interfaces returned: {len(interfaces.get('results', []))}")
    print("OK: authenticated read succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
