$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Net.Http
[System.Net.ServicePointManager]::DefaultConnectionLimit = 64
[System.Net.ServicePointManager]::UseNagleAlgorithm = $false

function Bench($label, $base) {
    $http = New-Object System.Net.Http.HttpClient
    $http.Timeout = [TimeSpan]::FromSeconds(30)
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    for ($i = 0; $i -lt 20; $i++) {
        $b = '{"id":1,"method":"ping"}'
        $c = New-Object System.Net.Http.StringContent($b, [System.Text.Encoding]::UTF8, 'application/json')
        $r = $http.PostAsync("$base/rpc", $c).GetAwaiter().GetResult()
        $null = $r.Content.ReadAsStringAsync().GetAwaiter().GetResult()
        $r.Dispose(); $c.Dispose()
    }
    $ms = [int]$sw.ElapsedMilliseconds
    Write-Host ($label + " 20x ping = " + $ms + "ms -> " + [Math]::Round($ms / 20, 1) + "ms each")
    $http.Dispose()
}

Write-Host '--- DNS answers for kickpi.local ---'
try {
    [System.Net.Dns]::GetHostAddresses('kickpi.local') | ForEach-Object { Write-Host ('  ' + $_.AddressFamily + ' ' + $_.ToString()) }
} catch { Write-Host ('  dns fail: ' + $_.Exception.Message) }

Bench 'IP  192.168.31.89' 'http://192.168.31.89:8000'
Bench 'mDNS kickpi.local' 'http://kickpi.local:8000'
