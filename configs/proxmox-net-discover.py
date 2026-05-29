#!/usr/bin/env python3
"""Deep Proxmox network discovery - bridges, OVS, interfaces.
Run: op run --env-file=.env -- python configs/proxmox-net-discover.py
"""
import os, sys, json, urllib.request, urllib.error, ssl

TOKEN = os.environ.get("PROXMOX_API_TOKEN", "")
URL   = os.environ.get("PROXMOX_URL", "https://10.10.10.10:8006").rstrip("/")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def api_get(path: str) -> dict | None:
    full_url = f"{URL}/api2/json{path}"
    req = urllib.request.Request(full_url, headers={"Authorization": f"PVEAPIToken={TOKEN}"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"  HTTP {e.code}: {e.read().decode()[:200]}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

# Get nodes
nodes_data = api_get("/nodes")
nodes = [n["node"] for n in nodes_data.get("data", [])] if nodes_data else []
print(f"Nodes: {nodes}")

for node in nodes:
    print(f"\n{'='*60}")
    print(f"  NODE: {node}")
    print(f"{'='*60}")

    # All network interfaces
    net = api_get(f"/nodes/{node}/network")
    if net and "data" in net:
        bridges = []
        for iface in net["data"]:
            iftype = iface.get("type", "unknown")
            iface_name = iface.get("iface", "?")
            
            # Collect bridge-like interfaces
            if iftype in ("bridge", "OVSBridge"):
                bridges.append(iface)
            
            print(f"\n  [{iftype}] {iface_name}")
            for key in sorted(iface.keys()):
                if key in ("iface", "type", "node"):
                    continue
                val = iface[key]
                if val is not None and val != "":
                    print(f"    {key}: {val}")

        print(f"\n  --- Bridges/OVS Summary ---")
        for b in bridges:
            print(f"  {b.get('type')}: {b.get('iface')} "
                  f"active={b.get('active')} "
                  f"autostart={b.get('autostart')} "
                  f"vlan_aware={b.get('bridge_vlan_aware')} "
                  f"ports={b.get('bridge_ports','')} "
                  f"address={b.get('address','')} "
                  f"gateway={b.get('gateway','')}")

    # Check for ovs-vsctl
    print(f"\n  --- Interfaces config snippet ---")
    config = api_get(f"/nodes/{node}/config")
    
    # SDN status per node
    sdn_status = api_get(f"/cluster/sdn/status/{node}")
    if sdn_status and "data" in sdn_status:
        print(f"\n  --- SDN Status on {node} ---")
        print(f"  {json.dumps(sdn_status['data'], indent=2)}")
