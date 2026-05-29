$token = $env:PROXMOX_API_TOKEN
$url = $env:PROXMOX_URL.TrimEnd('/')

Write-Host "URL: $url"
Write-Host "Token prefix: $($token.Substring(0,15))..."

$fullUrl = "$url/api2/json/version"
Write-Host "Full URL: $fullUrl"

# Try with .NET HttpClient directly
$handler = New-Object System.Net.Http.HttpClientHandler
$handler.ServerCertificateCustomValidationCallback = { $true }
$client = New-Object System.Net.Http.HttpClient($handler)
$client.Timeout = [TimeSpan]::FromSeconds(10)
$client.DefaultRequestHeaders.Authorization = New-Object System.Net.Http.Headers.AuthenticationHeaderValue("PVEAPIToken", $token)

try {
    $response = $client.GetAsync($fullUrl).Result
    $body = $response.Content.ReadAsStringAsync().Result
    Write-Host "Status: $($response.StatusCode)"
    Write-Host "Body: $body"
} catch {
    Write-Host "Error: $($_.Exception.Message)"
}
