#!/usr/bin/env python3
"""Proxmox API Read-Only Discovery Script.
Uses 1Password op run for credential injection.
Run: op run --env-file=.env -- python configs/proxmox-api-discover.py
"""
import os, sys, json, urllib.request, urllib.error, ssl

TOKEN = os.environ.get("PROXMOX_API_TOKEN", "")
URL   = os.environ.get("PROXMOX_URL", "https://10.10.10.10:8006").rstrip("/")

if not TOKEN:
    print("ERROR: PROXMOX_API_TOKEN not set. Run via op run.", file=sys.stderr)
    sys.exit(1)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def api_get(path: str) -> dict | None:
    """Make an authenticated GET request to the Proxmox API."""
    full_url = f"{URL}/api2/json{path}"
    print(f"GET {full_url}")
    req = urllib.request.Request(
        full_url,
        headers={"Authorization": f"PVEAPIToken={TOKEN}"}
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"  HTTP {e.code}: {body[:200]}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

def main():
    print("\n=== Proxmox API Read-Only Discovery ===\n")
    print(f"API URL: {URL}")

    # 1. Version
    print("\n--- Version ---")
    v = api_get("/version")
    if v and "data" in v:
        print(f"  Version: {v['data'].get('version', 'unknown')}")

    # 2. Nodes
    print("\n--- Nodes ---")
    nodes = api_get("/nodes")
    node_list = []
    if nodes and "data" in nodes:
        for n in nodes["data"]:
            status = n.get("status", "unknown")
            node_list.append(n["node"])
            print(f"  {n['node']} - {status}")
    else:
        print("  No nodes found")

    # 3. SDN
    print("\n--- SDN ---")
    sdn = api_get("/cluster/sdn")
    if sdn and "data" in sdn:
        print(f"  {json.dumps(sdn['data'], indent=2)}")
    else:
        print("  SDN not configured or empty")

    # 4. SDN Zones
    print("\n--- SDN Zones ---")
    zones = api_get("/cluster/sdn/zones")
    zone_list = []
    if zones and "data" in zones:
        for z in zones["data"]:
            zone_list.append(z.get("zone", "?"))
            print(f"  Zone: {z.get('zone')} type={z.get('type')} bridge={z.get('bridge')} nodes={z.get('nodes')} status={z.get('status')}")
    else:
        print("  No SDN zones found")

    # 5. SDN VNets
    print("\n--- SDN VNets ---")
    vnets = api_get("/cluster/sdn/vnets")
    vnet_list = []
    if vnets and "data" in vnets:
        for v in vnets["data"]:
            vnet_list.append(v.get("vnet", "?"))
            print(f"  VNet: {v.get('vnet')} zone={v.get('zone')} tag={v.get('tag')} alias={v.get('alias','')}")
    else:
        print("  No SDN VNets found")

    # 6. SDN Subnets
    print("\n--- SDN Subnets ---")
    subnets = api_get("/cluster/sdn/subnets")
    if subnets and "data" in subnets:
        for s in subnets["data"]:
            print(f"  Subnet: {s.get('subnet')} vnet={s.get('vnet')} gateway={s.get('gateway')} type={s.get('type')}")
    else:
        print("  No SDN subnets found")

    # 7. Network interfaces on each node (vmbr0 check)
    print("\n--- Network Interfaces (vmbr0) ---")
    for node in node_list:
        ifaces = api_get(f"/nodes/{node}/network")
        if ifaces and "data" in ifaces:
            for iface in ifaces["data"]:
                if iface.get("iface") == "vmbr0":
                    vlan_aware = "VLAN-aware" if iface.get("bridge_vlan_aware") else "NOT VLAN-aware"
                    auto = "autostart" if iface.get("autostart") else "no-autostart"
                    active = "active" if iface.get("active") else "inactive"
                    print(f"  {node} vmbr0: {vlan_aware} {auto} {active} address={iface.get('address','')} ports={iface.get('bridge_ports','')}")

    # Summary: diff against target
    print("\n=== Diff Summary ===\n")
    target_vnets = {"vmgmt", "vstore", "vsvc", "vapps", "vlab", "vdmz"}
    print(f"Nodes found: {node_list}")
    print(f"Zones found: {zone_list}")
    print(f"VNets found: {vnet_list}")

    if "ztrunk" not in zone_list:
        print("MISSING: Zone 'ztrunk' not found")
    else:
        print("OK: Zone 'ztrunk' exists")

    missing_vnets = target_vnets - set(vnet_list)
    if missing_vnets:
        print(f"MISSING VNets: {missing_vnets}")
    else:
        print("OK: All target VNets exist")

    print("\n=== Discovery Complete ===")

if __name__ == "__main__":
    main()
