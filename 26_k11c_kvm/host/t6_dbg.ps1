$ErrorActionPreference = 'Stop'
$base = 'http://192.168.31.89:8000'

function RpcRaw($method, $params) {
    $body = @{ id = 1; method = $method; params = $params } | ConvertTo-Json -Depth 4 -Compress
    return Invoke-RestMethod -Uri "$base/rpc" -Method Post -ContentType 'application/json' -Body $body -TimeoutSec 10
}

Add-Type -AssemblyName System.Windows.Forms
$vs = [System.Windows.Forms.SystemInformation]::VirtualScreen
$ps = [System.Windows.Forms.SystemInformation]::PrimaryScreen.Bounds
Write-Host ("VirtualScreen=" + $vs.Width + "x" + $vs.Height + "@" + $vs.X + "," + $vs.Y)
Write-Host ("Primary=" + $ps.Width + "x" + $ps.Height + "@" + $ps.X + "," + $ps.Y)
foreach ($s in [System.Windows.Forms.Screen]::AllScreens) {
    Write-Host ("  screen: " + $s.DeviceName + " " + $s.Bounds.Width + "x" + $s.Bounds.Height + "@" + $s.Bounds.X + "," + $s.Bounds.Y + " primary=" + $s.Primary)
}

Write-Host "--- getUsbEmulationState ---"
(RpcRaw 'getUsbEmulationState' $null) | ConvertTo-Json -Compress | Write-Host

foreach ($pt in @(@{x=0;y=0}, @{x=16384;y=16384}, @{x=32767;y=32767})) {
    $r = RpcRaw 'absMouseReport' $pt
    $err = if ($r.error) { 'ERR:' + $r.error.message } else { 'ok' }
    Start-Sleep -Milliseconds 500
    $p = [System.Windows.Forms.Cursor]::Position
    Write-Host ("send x=" + $pt.x + " y=" + $pt.y + " -> " + $err + " cursor=" + $p.X + "," + $p.Y)
}
