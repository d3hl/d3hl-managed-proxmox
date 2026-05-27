# Test Proxmox API token auth
$token = $env:PROXMOX_API_TOKEN
$url   = $env:PROXMOX_URL

Write-Host "Token length: $($token.Length)"
Write-Host "Token prefix: $($token.Substring(0, [Math]::Min(20, $token.Length)))..."
Write-Host "URL: $url"

# Try with Invoke-WebRequest
$headers = @{ Authorization = "PVEAPIToken=$token" }
Write-Host "`nTrying GET /api2/json/version..."
try {
    $r = Invoke-WebRequest -Uri "$url/api2/json/version" -Headers $headers -SkipCertificateCheck -TimeoutSec 10
    Write-Host "SUCCESS: $($r.StatusCode)"
    Write-Host $r.Content
} catch {
    Write-Host "FAILED: $($_.Exception.Message)"
    if ($_.Exception.Response) {
        $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
        Write-Host "Body: $($reader.ReadToEnd())"
    }
}
