param(
    [string]$Label = "run",
    [int]$Samples = 30,
    [int]$IdleMs = 800,
    [string]$HostIp = "192.168.31.89",
    [int]$Port = 8000
)
# Why the idle gap: WiFi power save costs show up on the idle->awake transition.
# Firing 300 back-to-back requests keeps the radio awake and measures nothing.
# Metric: wall clock of ONE full TCP connection (connect + POST /rpc ping + read response).
# The board itself spends 0.2-0.4 ms, so this is essentially the WiFi round trip.
# NOTE: keep this file ASCII only - Windows PowerShell 5.1 reads .ps1 as GBK.
$ErrorActionPreference = 'Stop'
$body = '{"id":1,"method":"ping"}'
$out = @()

for ($i = 0; $i -lt $Samples; $i++) {
    Start-Sleep -Milliseconds $IdleMs
    $c = New-Object System.Net.Sockets.TcpClient
    $c.NoDelay = $true
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $c.Connect($HostIp, $Port)
        $s = $c.GetStream()
        $req = "POST /rpc HTTP/1.1`r`nHost: x`r`nContent-Type: application/json`r`nContent-Length: " +
               $body.Length + "`r`nConnection: close`r`n`r`n" + $body
        $b = [System.Text.Encoding]::ASCII.GetBytes($req)
        $s.Write($b, 0, $b.Length)
        $s.Flush()
        $buf = New-Object byte[] 4096
        $total = 0
        while ($true) {
            $n = $s.Read($buf, 0, $buf.Length)
            if ($n -le 0) { break }
            $total += $n
            if ($total -gt 200) { break }
        }
        $sw.Stop()
        $out += [int]$sw.ElapsedMilliseconds
    } catch {
        $sw.Stop()
        $out += -1
    } finally {
        $c.Close()
    }
}

$ok = @($out | Where-Object { $_ -ge 0 } | Sort-Object)
$n = $ok.Count
Write-Output ("[$Label] n=$n min=" + $ok[0] + " med=" + $ok[[int](($n - 1) * 0.5)] +
    " p90=" + $ok[[int](($n - 1) * 0.90)] + " p95=" + $ok[[int](($n - 1) * 0.95)] +
    " max=" + $ok[$n - 1] + " fail=" + ($out.Count - $n))
Write-Output ("[$Label] all: " + (($ok | ForEach-Object { "$_" }) -join " "))
