#!/usr/bin/env pwsh
# Proxmox API Read-Only Discovery Script
# Uses 1Password op run for credential injection.
# Supports both API token and ticket-based auth.
param([switch]$Plan)

$ErrorActionPreference = "Continue"

# Credentials from op run environment
$API_TOKEN = $env:PROXMOX_API_TOKEN
$API_USER  = $env:PROXMOX_USER
$API_PASS  = $env:PROXMOX_PASS
$API_URL   = $env:PROXMOX_URL

if (-not $API_URL) { $API_URL = "https://10.10.10.10:8006" }
$baseUrl = $API_URL.TrimEnd('/') + "/api2/json"
$skipCert = @{ SkipCertificateCheck = $true }

# --- Auth: try API token first, fall back to ticket ---
$headers = @{}

if ($API_TOKEN) {
    Write-Host "Trying API token auth..." -ForegroundColor Cyan
    $headers["Authorization"] = "PVEAPIToken=$API_TOKEN"
} elseif ($API_USER -and $API_PASS) {
    Write-Host "Authenticating with ticket..." -ForegroundColor Cyan
    try {
        $ticketResp = Invoke-RestMethod -Uri "$baseUrl/access/ticket" -Method Post `
            -Body @{username=$API_USER; password=$API_PASS} @skipCert -TimeoutSec 15
        $headers["Cookie"] = "PVEAuthCookie=$($ticketResp.data.ticket)"
        $headers["CSRFPreventionToken"] = $ticketResp.data.CSRFPreventionToken
        Write-Host "Authenticated as: $($ticketResp.data.username)" -ForegroundColor Green
    } catch {
        Write-Error "Ticket auth failed: $_"
        exit 1
    }
} else {
    Write-Error "Set PROXMOX_API_TOKEN or (PROXMOX_USER+PROXMOX_PASS)"
    exit 1
}

function Invoke-ProxmoxApi {
    param([string]$Path, [string]$Method = "Get")
    $uri = "$baseUrl$Path"
    Write-Host "GET $uri" -ForegroundColor Cyan
    try {
        return Invoke-RestMethod -Uri $uri -Method $Method -Headers $headers @skipCert -TimeoutSec 15
    } catch {
        Write-Warning "Request failed: $_"
        return $null
    }
}

Write-Host "`n=== Proxmox API Read-Only Discovery ===`n" -ForegroundColor Green
Write-Host "API URL: $API_URL`n"

# 1. Version info
Write-Host "--- Version ---"
$ver = Invoke-ProxmoxApi -Path "/version"
if ($ver) { Write-Host "Version: $($ver.data.version)" }

# 2. Nodes
Write-Host "`n--- Nodes ---"
$nodes = Invoke-ProxmoxApi -Path "/nodes"
if ($nodes -and $nodes.data) {
    foreach ($n in $nodes.data) {
        $status = if ($n.status) { $n.status } else { "unknown" }
        Write-Host "  $($n.node) - $status"
    }
}

# 3. SDN status
Write-Host "`n--- SDN ---"
$sdn = Invoke-ProxmoxApi -Path "/cluster/sdn"
if ($sdn -and $sdn.data) {
    $sdn.data | ConvertTo-Json -Depth 3
} else {
    Write-Host "  SDN not configured or empty"
}

# 4. SDN Zones
Write-Host "`n--- SDN Zones ---"
$zones = Invoke-ProxmoxApi -Path "/cluster/sdn/zones"
if ($zones -and $zones.data) {
    foreach ($z in $zones.data) {
        Write-Host "  Zone: $($z.zone) type=$($z.type) bridge=$($z.bridge) nodes=$($z.nodes) status=$($z.status)"
    }
} else {
    Write-Host "  No SDN zones found"
}

# 5. SDN VNets
Write-Host "`n--- SDN VNets ---"
$vnets = Invoke-ProxmoxApi -Path "/cluster/sdn/vnets"
if ($vnets -and $vnets.data) {
    foreach ($v in $vnets.data) {
        Write-Host "  VNet: $($v.vnet) zone=$($v.zone) tag=$($v.tag) alias=$($v.alias)"
    }
} else {
    Write-Host "  No SDN VNets found"
}

# 6. SDN Subnets
Write-Host "`n--- SDN Subnets ---"
$subnets = Invoke-ProxmoxApi -Path "/cluster/sdn/subnets"
if ($subnets -and $subnets.data) {
    foreach ($s in $subnets.data) {
        Write-Host "  Subnet: $($s.subnet) vnet=$($s.vnet) gateway=$($s.gateway) type=$($s.type)"
    }
} else {
    Write-Host "  No SDN subnets found"
}

# 7. Network interfaces on each node (vmbr0 check)
Write-Host "`n--- Network Interfaces (vmbr0) ---"
if ($nodes -and $nodes.data) {
    foreach ($n in $nodes.data) {
        $nodeName = $n.node
        $ifaces = Invoke-ProxmoxApi -Path "/nodes/$nodeName/network"
        if ($ifaces -and $ifaces.data) {
            foreach ($iface in $ifaces.data) {
                if ($iface.iface -eq "vmbr0") {
                    $vlanAware = if ($iface.bridge_vlan_aware) { "VLAN-aware" } else { "NOT VLAN-aware" }
                    $autostart = if ($iface.autostart) { "autostart" } else { "no-autostart" }
                    $active = if ($iface.active) { "active" } else { "inactive" }
                    Write-Host "  $nodeName vmbr0: $vlanAware $autostart $active address=$($iface.address) ports=$($iface.bridge_ports)"
                }
            }
        }
    }
}

Write-Host "`n=== Discovery Complete ===`n" -ForegroundColor Green

if ($Plan) {
    Write-Host "`n=== Target Plan (per session-handoff.md) ===`n" -ForegroundColor Yellow
    Write-Host "Zone: ztrunk (VLAN, bridge=vmbr0, nodes=nodeA,nodeB,nodeD,nodeF)"
    $targets = @(
        @{VNet="vmgmt"; VLAN=10; Subnet="10.10.10.0/24"; Gateway="10.10.10.2"},
        @{VNet="vstore"; VLAN=20; Subnet="10.20.20.0/24"; Gateway=$null},
        @{VNet="vsvc"; VLAN=30; Subnet="10.10.30.0/24"; Gateway="10.10.30.2"},
        @{VNet="vapps"; VLAN=40; Subnet="10.10.40.0/24"; Gateway="10.10.40.2"},
        @{VNet="vlab"; VLAN=50; Subnet="10.10.50.0/24"; Gateway="10.10.50.2"},
        @{VNet="vdmz"; VLAN=60; Subnet="10.10.60.0/24"; Gateway="10.10.60.2"}
    )
    foreach ($t in $targets) {
        Write-Host "  $($t.VNet) VLAN=$($t.VLAN) $($t.Subnet) gw=$($t.Gateway)"
    }
}
