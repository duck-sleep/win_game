$ErrorActionPreference = 'Stop'
$ip = '192.168.31.89'
$port = 8000

function Post-RpcRaw($method, $paramsJson) {
    $c = New-Object System.Net.Sockets.TcpClient
    $c.NoDelay = $true
    $c.Connect($ip, $port)
    $s = $c.GetStream()
    $s.ReadTimeout = 15000
    $body = '{"id":1,"method":"' + $method + '","params":' + $paramsJson + '}'
    $b = [System.Text.Encoding]::ASCII.GetBytes($body)
    $head = [System.Text.Encoding]::ASCII.GetBytes("POST /rpc HTTP/1.1`r`nHost: k`r`nContent-Type: application/json`r`nContent-Length: " + $b.Length + "`r`nConnection: close`r`n`r`n")
    $s.Write($head, 0, $head.Length)
    $s.Write($b, 0, $b.Length)
    $buf = New-Object byte[] 8192
    $tot = 0
    while ($true) {
        try { $n = $s.Read($buf, $tot, $buf.Length - $tot) } catch { break }
        if ($n -le 0) { break }
        $tot += $n
        if ($tot -ge $buf.Length) { break }
    }
    $c.Close()
    return [System.Text.Encoding]::UTF8.GetString($buf, 0, $tot)
}

# baseline
$sw = [System.Diagnostics.Stopwatch]::StartNew()
for ($i = 0; $i -lt 20; $i++) { $null = Post-RpcRaw 'ping' '{}' }
$ms = [int]$sw.ElapsedMilliseconds
Write-Host ('20x raw ping = ' + $ms + 'ms -> ' + [Math]::Round($ms / 20, 1) + 'ms each')

# test 4: 300 absMouseReport
$busy = 0; $other = 0
$sw = [System.Diagnostics.Stopwatch]::StartNew()
for ($i = 0; $i -lt 300; $i++) {
    $x = 1000 + ($i * 97) % 30000
    $y = 1000 + ($i * 53) % 30000
    $t = Post-RpcRaw 'absMouseReport' ('{"x":' + $x + ',"y":' + $y + ',"buttons":0}')
    if ($t -match '"code": -32001') { $busy++ }
    elseif ($t -match '"error"') { $other++ }
}
$ms = [int]$sw.ElapsedMilliseconds
$ping = Post-RpcRaw 'ping' '{}'
$st = Post-RpcRaw 'getUsbEmulationState' '{}'
Write-Host ('T6-4 300 serial raw calls in ' + $ms + 'ms (limit 10000) hidBusy=' + $busy + ' otherErr=' + $other)
Write-Host ('  ping after = ' + $ping)
