#!/usr/bin/env python3
"""Quick validation of nodeF esfp1 trunk conversion."""
import os, sys, json, urllib.request, urllib.error, ssl

TOKEN = os.environ.get("PROXMOX_API_TOKEN", "")
URL   = os.environ.get("PROXMOX_URL", "https://10.10.10.10:8006").rstrip("/")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def get(path):
    req = urllib.request.Request(f"{URL}/api2/json{path}", headers={"Authorization": f"PVEAPIToken={TOKEN}"})
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=10) as r:
            return json.loads(r.read().decode())
    except: return None

# Check nodeF esfp1
print("=== nodeF esfp1 ===")
iface = get("/nodes/nodeF/network/esfp1")
if iface and "data" in iface:
    d = iface["data"]
    print(f"  type: {d.get('ovs_type')}")
    print(f"  options: {d.get('ovs_options')}")
    print(f"  tag: {d.get('ovs_tag')}")
    print(f"  active: {d.get('active')}")

# Quick SDN check
print("\n=== SDN Summary ===")
zones = get("/cluster/sdn/zones")
if zones and zones.get("data"):
    for z in zones["data"]:
        print(f"  Zone: {z['zone']} type={z['type']} bridge={z['bridge']}")

vnets = get("/cluster/sdn/vnets")
if vnets and vnets.get("data"):
    for v in vnets["data"]:
        print(f"  VNet: {v['vnet']} tag={v.get('tag')} status={v.get('status')}")

# All trunks
print("\n=== All Trunk Ports ===")
for node in ["nodeA","nodeB","nodeD","nodeF"]:
    ports = {"nodeA":"en10basep2","nodeB":"ennic1s1","nodeD":"eno1","nodeF":"esfp1"}
    iface = get(f"/nodes/{node}/network/{ports[node]}")
    if iface and "data" in iface:
        d = iface["data"]
        print(f"  {node}/{ports[node]}: trunks={d.get('ovs_options')} tag={d.get('ovs_tag')} active={d.get('active')}")
