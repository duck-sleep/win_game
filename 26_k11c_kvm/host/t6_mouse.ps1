$ErrorActionPreference = 'Stop'
$base = 'http://kickpi.local:8000'

function Rpc($method, $params) {
    $body = @{ id = 1; method = $method; params = $params } | ConvertTo-Json -Depth 4 -Compress
    return Invoke-RestMethod -Uri "$base/rpc" -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 15
}

Add-Type -AssemblyName System.Windows.Forms

# --- test 1: absolute mouse to screen center ---
$r = Rpc 'absMouseReport' @{ x = 16384; y = 16384; buttons = 0 }
if ($r.error) { Write-Host ('T6-1 RPC ERROR ' + $r.error.message) }
Start-Sleep -Milliseconds 400
$p1 = [System.Windows.Forms.Cursor]::Position
Start-Sleep -Milliseconds 300
$p2 = [System.Windows.Forms.Cursor]::Position
$ok1 = ([Math]::Abs($p1.X - 960) -le 3) -and ([Math]::Abs($p1.Y - 540) -le 3) -and ($p1.X -eq $p2.X) -and ($p1.Y -eq $p2.Y)
Write-Host ("T6-1 cursor=" + $p1.X + "," + $p1.Y + " then " + $p2.X + "," + $p2.Y + " expect 960,540+-3 => " + $ok1)

# --- single call RTT, decides how to send 300 ---
$sw = [System.Diagnostics.Stopwatch]::StartNew()
for ($i = 0; $i -lt 20; $i++) { Rpc 'ping' $null | Out-Null }
$rtt = [double]$sw.ElapsedMilliseconds / 20
Write-Host ("RTT per call " + [Math]::Round($rtt, 1) + "ms -> serial 300 would take " + [int]($rtt * 300 / 1000) + "s")

# --- test 4: 300 absMouseReport over 8 concurrent connections ---
$job = @()
$sw = [System.Diagnostics.Stopwatch]::StartNew()
for ($j = 0; $j -lt 8; $j++) {
    $job += Start-Job -ArgumentList $base, $j, 38 -ScriptBlock {
        param($base, $j, $n)
        $bad = 0
        for ($i = 0; $i -lt $n; $i++) {
            $x = 1000 + (($j * 38 + $i) * 97) % 30000
            $y = 1000 + (($j * 38 + $i) * 53) % 30000
            $b = @{ id = 1; method = 'absMouseReport'; params = @{ x = $x; y = $y; buttons = 0 } } | ConvertTo-Json -Compress
            try {
                $r = Invoke-RestMethod -Uri "$base/rpc" -Method Post -ContentType 'application/json' -Body $b -TimeoutSec 15
                if ($r.error) { $bad++ }
            } catch { $bad++ }
        }
        return $bad
    }
}
$null = Wait-Job -Job $job -Timeout 60
$badAll = @()
foreach ($jj in $job) { $badAll += @(Receive-Job -Job $jj) }
$badTotal = ($badAll | Measure-Object -Sum).Sum
$ms = [int]$sw.ElapsedMilliseconds
Remove-Job -Job $job -Force
$ping = Rpc 'ping' $null
$st = Invoke-RestMethod -Uri "$base/state" -TimeoutSec 10
Write-Host ("T6-4 300 calls via 8 conns in " + $ms + "ms (limit 10000) errors=" + $badTotal + " ping=" + $ping.result + " fps=" + $st.fps)
