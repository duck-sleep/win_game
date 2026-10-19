$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Net.Http
[System.Net.ServicePointManager]::DefaultConnectionLimit = 64
[System.Net.ServicePointManager]::UseNagleAlgorithm = $false
$base = 'http://kickpi.local:8000'
$http = New-Object System.Net.Http.HttpClient
$http.Timeout = [TimeSpan]::FromSeconds(30)

function PostRpc($method, $params) {
    $body = @{ id = 1; method = $method; params = $params } | ConvertTo-Json -Depth 4 -Compress
    $content = New-Object System.Net.Http.StringContent($body, [System.Text.Encoding]::UTF8, 'application/json')
    $resp = $http.PostAsync("$base/rpc", $content).GetAwaiter().GetResult()
    $txt = $resp.Content.ReadAsStringAsync().GetAwaiter().GetResult()
    $resp.Dispose()
    return ($txt | ConvertFrom-Json)
}

# baseline: how fast is one HTTP round trip from this process
$sw = [System.Diagnostics.Stopwatch]::StartNew()
for ($i = 0; $i -lt 20; $i++) { $null = $http.GetStringAsync("$base/state").GetAwaiter().GetResult() }
$get20 = [int]$sw.ElapsedMilliseconds
Write-Host ("20x GET /state in " + $get20 + "ms -> " + [Math]::Round($get20 / 20, 1) + "ms each")

$sw = [System.Diagnostics.Stopwatch]::StartNew()
for ($i = 0; $i -lt 20; $i++) { $null = PostRpc 'ping' $null }
$rpc20 = [int]$sw.ElapsedMilliseconds
Write-Host ("20x POST /rpc ping in " + $rpc20 + "ms -> " + [Math]::Round($rpc20 / 20, 1) + "ms each")

# test 4: 300 sequential absMouseReport
$busy = 0; $other = 0
$sw = [System.Diagnostics.Stopwatch]::StartNew()
for ($i = 0; $i -lt 300; $i++) {
    $x = 1000 + ($i * 97) % 30000
    $y = 1000 + ($i * 53) % 30000
    $r = PostRpc 'absMouseReport' @{ x = $x; y = $y; buttons = 0 }
    if ($r.error) {
        if ($r.error.code -eq -32001) { $busy++ } else { $other++ }
    }
}
$ms = [int]$sw.ElapsedMilliseconds
$ping = PostRpc 'ping' $null
$st = ($http.GetStringAsync("$base/state").GetAwaiter().GetResult() | ConvertFrom-Json)
Write-Host ("T6-4 300 serial calls in " + $ms + "ms (limit 10000) hidBusy=" + $busy + " otherErr=" + $other + " ping=" + $ping.result + " fps=" + $st.fps)
$http.Dispose()
