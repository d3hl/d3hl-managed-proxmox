import os, sys, urllib.request, ssl, json

token = os.environ.get("PROXMOX_API_TOKEN", "")
url = os.environ.get("PROXMOX_URL", "https://10.10.10.10:8006").rstrip("/")

print(f"URL: {url}")
print(f"Token prefix: {token[:15]}...")
print(f"Token length: {len(token)}")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    f"{url}/api2/json/version",
    headers={"Authorization": f"PVEAPIToken={token}"}
)

try:
    with urllib.request.urlopen(req, context=ctx, timeout=10) as resp:
        print(f"Status: {resp.status}")
        print(f"Body: {resp.read().decode()}")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code}")
    print(f"Body: {e.read().decode()}")
except Exception as e:
    print(f"Error: {e}")
