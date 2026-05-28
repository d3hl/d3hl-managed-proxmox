#!/usr/bin/env python3
"""Proxmox OVS SDN Implementation Script.
Idempotent - creates only missing objects, updates trunk VLANs safely.
Run: op run --env-file=.env -- python configs/proxmox-sdn-apply.py [plan|apply]
"""
import os, sys, json, urllib.request, urllib.error, ssl, time

TOKEN = os.environ.get("PROXMOX_API_TOKEN", "")
URL   = os.environ.get("PROXMOX_URL", "https://10.10.10.10:8006").rstrip("/")
MODE  = sys.argv[1] if len(sys.argv) > 1 else "plan"

if not TOKEN:
    print("ERROR: PROXMOX_API_TOKEN not set.", file=sys.stderr)
    sys.exit(1)

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def api(method: str, path: str, data: dict | None = None) -> dict | None:
    """Make an authenticated API request."""
    full_url = f"{URL}/api2/json{path}"
    body_bytes = None
    headers = {
        "Authorization": f"PVEAPIToken={TOKEN}",
    }
    if data is not None:
        body_bytes = json.dumps(data).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(
        full_url,
        data=body_bytes,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=20) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode()
        if e.code == 501:
            return None  # Not implemented
        print(f"  HTTP {e.code}: {body_text[:300]}")
        return None
    except Exception as e:
        print(f"  Error: {e}")
        return None

def api_get(path: str) -> dict | None:
    return api("GET", path)

def api_put(path: str, data: dict) -> dict | None:
    return api("PUT", path, data)

def api_post(path: str, data: dict) -> dict | None:
    return api("POST", path, data)

# ── Target definitions ──

ZONE = "ztrunk"
BRIDGE = "vmbr0"

VNets = [
    ("vmgmt", 10, "10.10.10.0/24", "10.10.10.2"),
    ("vstore", 20, "10.20.20.0/24", None),
    ("vsvc", 30, "10.10.30.0/24", "10.10.30.2"),
    ("vapps", 40, "10.10.40.0/24", "10.10.40.2"),
    ("vlab", 50, "10.10.50.0/24", "10.10.50.2"),
    ("vdmz", 60, "10.10.60.0/24", "10.10.60.2"),
]

# Trunk ports per node - synced from live Proxmox 2026-05-28
TRUNK_UPDATES = {
    "nodeA": {
        "port": "en10basep2",
        "current_trunk": "3,10,11,30,40,50,60",
        "target_trunk": "3,10,11,30,40,50,60",
    },
    "nodeB": {
        "port": "ennic1s1",
        "current_trunk": "3,10,11,30,40,50,60",
        "target_trunk": "3,10,11,30,40,50,60",
    },
    "nodeD": {
        "port": "eno1",
        "current_trunk": "3,10,11,30,40,50,60",
        "target_trunk": "3,10,11,30,40,50,60",
    },
    "nodeF": {
        "port": "sfp1",
        "current_trunk": "10,11,30,40,50,60",
        "target_trunk": "10,11,30,40,50,60",  # VLAN 3 via dedicated vmbr3/nic4
    },
}

def plan():
    """Print the plan without mutating anything."""
    print("\n" + "="*60)
    print("  OVS SDN IMPLEMENTATION PLAN (read-only)")
    print("="*60)

    # Check current state
    print("\n--- Current SDN State ---")
    zones = api_get("/cluster/sdn/zones")
    if zones and zones.get("data"):
        for z in zones["data"]:
            print(f"  Zone: {z['zone']} type={z['type']} bridge={z['bridge']}")
    else:
        print("  No SDN zones")

    vnets = api_get("/cluster/sdn/vnets")
    if vnets and vnets.get("data"):
        for v in vnets["data"]:
            print(f"  VNet: {v['vnet']} tag={v.get('tag')} zone={v.get('zone')}")
    else:
        print("  No SDN VNets")

    # Plan trunk updates
    print("\n--- Phase 1: OVS Trunk VLAN Updates ---")
    for node, cfg in TRUNK_UPDATES.items():
        iface_data = api_get(f"/nodes/{node}/network/{cfg['port']}")
        if not iface_data or "data" not in iface_data:
            print(f"  {node}/{cfg['port']}: NOT FOUND")
            continue

        current = iface_data["data"]
        options = current.get("ovs_options", "")
        tag = current.get("ovs_tag")

        print(f"\n  {node}/{cfg['port']}:")
        print(f"    Current ovs_options: {options}")
        print(f"    Current ovs_tag: {tag}")

        if cfg.get("needs_conversion"):
            print(f"    ACTION: Convert from access (tag={tag}) to trunk")
            print(f"    New ovs_options: trunks={cfg['target_trunk']} vlan_mode=native-untagged")
            print(f"    New ovs_tag: 1")
        else:
            print(f"    ACTION: Update trunk list")
            print(f"    New ovs_options: trunks={cfg['target_trunk']} vlan_mode=native-untagged")

    # Plan SDN objects
    print("\n--- Phase 2: SDN Zone ---")
    zone_exists = zones and any(z.get("zone") == ZONE for z in (zones.get("data") or []))
    if zone_exists:
        print(f"  Zone '{ZONE}' already exists - skipping")
    else:
        print(f"  CREATE zone '{ZONE}' type=vlan bridge={BRIDGE}")
        print(f"  nodes: nodeA,nodeB,nodeD,nodeF")

    print("\n--- Phase 3: SDN VNets ---")
    existing_vnets = set()
    if vnets and vnets.get("data"):
        existing_vnets = {v["vnet"] for v in vnets["data"]}

    for vnet_name, tag, subnet, gw in VNets:
        if vnet_name in existing_vnets:
            print(f"  VNet '{vnet_name}' already exists - skipping")
        else:
            print(f"  CREATE VNet '{vnet_name}' tag={tag}")
            if gw:
                print(f"    Subnet: {subnet} gateway={gw}")
            else:
                print(f"    Subnet: {subnet} gateway=none")

    print("\n--- Phase 4: SDN Apply ---")
    print(f"  RUN: pvesh set /cluster/sdn")
    print("\n" + "="*60)


def apply():
    """Apply changes idempotently."""
    print("\n" + "="*60)
    print("  OVS SDN IMPLEMENTATION (apply mode)")
    print("="*60)

    # Phase 1: Update OVS trunk ports
    print("\n--- Phase 1: OVS Trunk VLAN Updates ---")
    for node, cfg in TRUNK_UPDATES.items():
        if cfg.get("skip"):
            print(f"  {node}/{cfg['port']}: SKIPPED (needs manual verification)")
            continue
        iface_data = api_get(f"/nodes/{node}/network/{cfg['port']}")
        if not iface_data or "data" not in iface_data:
            print(f"  {node}/{cfg['port']}: NOT FOUND - skipping")
            continue

        current = iface_data["data"]
        current_options = current.get("ovs_options", "")
        current_tag = current.get("ovs_tag")

        new_options = f"trunks={cfg['target_trunk']} vlan_mode=native-untagged"
        new_tag = 1  # trunk native VLAN tag is always 1 for native-untagged

        if cfg.get("needs_conversion"):
            print(f"  {node}/{cfg['port']}: Converting access->trunk")
        else:
            # Check if current options already contain the exact target trunk set
            if f"trunks={cfg['target_trunk']}" in current_options or f"trunk={cfg['target_trunk']}" in current_options:
                print(f"  {node}/{cfg['port']}: Already has target trunk - skipping")
                continue
            print(f"  {node}/{cfg['port']}: Updating trunk -> {cfg['target_trunk']}")

        update_data = {
            "type": "OVSPort",
            "ovs_options": new_options,
            "ovs_tag": new_tag,
        }
        result = api_put(f"/nodes/{node}/network/{cfg['port']}", update_data)
        if result and "data" in result:
            print(f"    OK: trunk updated")
        else:
            print(f"    FAILED")

        # Reload network on node
        print(f"    Reloading network on {node}...")
        api_put(f"/nodes/{node}/network", {})

    # Phase 2: Create SDN zone
    print("\n--- Phase 2: SDN Zone ---")
    zones = api_get("/cluster/sdn/zones")
    zone_exists = zones and any(
        z.get("zone") == ZONE for z in (zones.get("data") or [])
    )
    if zone_exists:
        print(f"  Zone '{ZONE}' already exists - skipping")
    else:
        result = api_post("/cluster/sdn/zones", {
            "zone": ZONE,
            "type": "vlan",
            "bridge": BRIDGE,
            "nodes": "nodeA,nodeB,nodeD,nodeF",
        })
        if result and "data" in result:
            print(f"  OK: Zone '{ZONE}' created")
        else:
            print(f"  FAILED to create zone - may already exist or need different params")

    # Phase 3: Create VNets
    print("\n--- Phase 3: SDN VNets ---")
    vnets = api_get("/cluster/sdn/vnets")
    existing_vnets = set()
    if vnets and vnets.get("data"):
        existing_vnets = {v["vnet"] for v in vnets["data"]}

    for vnet_name, tag, subnet, gw in VNets:
        if vnet_name in existing_vnets:
            print(f"  VNet '{vnet_name}' already exists - skipping")
        else:
            result = api_post("/cluster/sdn/vnets", {
                "vnet": vnet_name,
                "zone": ZONE,
                "tag": tag,
            })
            if result and "data" in result:
                print(f"  OK: VNet '{vnet_name}' created (tag={tag})")
            else:
                print(f"  FAILED to create VNet '{vnet_name}'")
                continue

        # Create subnet
        subnet_path = f"/cluster/sdn/vnets/{vnet_name}/subnets"
        subnet_data = {
            "subnet": subnet,
            "type": "subnet",
        }
        if gw:
            subnet_data["gateway"] = gw
        result = api_post(subnet_path, subnet_data)
        if result and "data" in result:
            print(f"    OK: Subnet {subnet} gateway={gw or 'none'}")
        else:
            print(f"    Subnet may already exist or creation failed")

    # Phase 4: Apply SDN
    print("\n--- Phase 4: SDN Apply ---")
    print("  Applying SDN configuration cluster-wide...")
    # PUT /cluster/sdn with reload action
    result = api_put("/cluster/sdn", {"reload": 1})
    if result:
        print(f"  OK: SDN applied")
    else:
        # Try without body
        print("  Retrying with no body...")
        result = api("PUT", "/cluster/sdn")
        if result:
            print(f"  OK: SDN applied (no body)")
        else:
            print(f"  SDN apply may need manual: pvesh set /cluster/sdn")

    print("\n" + "="*60)
    print("  Implementation complete. Run validation.")
    print("="*60)


def validate():
    """Run validation."""
    print("\n=== SDN Validation ===\n")

    zones = api_get("/cluster/sdn/zones")
    if zones and zones.get("data"):
        for z in zones["data"]:
            print(f"Zone: {z['zone']} type={z['type']} bridge={z['bridge']} status={z.get('status')}")
    else:
        print("No zones found!")

    vnets = api_get("/cluster/sdn/vnets")
    if vnets and vnets.get("data"):
        for v in vnets["data"]:
            print(f"VNet: {v['vnet']} tag={v.get('tag')} zone={v.get('zone')} status={v.get('status')}")
    else:
        print("No VNets found!")

    # Check trunk ports
    for node, cfg in TRUNK_UPDATES.items():
        iface = api_get(f"/nodes/{node}/network/{cfg['port']}")
        if iface and "data" in iface:
            print(f"{node}/{cfg['port']}: options={iface['data'].get('ovs_options')} tag={iface['data'].get('ovs_tag')}")


if MODE == "plan":
    plan()
elif MODE == "apply":
    apply()
elif MODE == "validate":
    validate()
else:
    print(f"Usage: {sys.argv[0]} [plan|apply|validate]")
    sys.exit(1)
