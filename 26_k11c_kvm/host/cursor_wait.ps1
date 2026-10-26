param(
    [int]$TargetX = 300,
    [int]$TargetY = 700,
    [int]$TimeoutMs = 6000
)
# Measures: wall-clock time at which the Windows cursor reaches the target position.
# The page prints its own send timestamp (Date.now, same machine) so the difference is
# the real "finger -> cursor moved" latency of the whole chain.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
$deadline = (Get-Date).AddMilliseconds($TimeoutMs)
$t0 = Get-Date
while ((Get-Date) -lt $deadline) {
    $p = [System.Windows.Forms.Cursor]::Position
    if ([Math]::Abs($p.X - $TargetX) -le 3 -and [Math]::Abs($p.Y - $TargetY) -le 3) {
        $arr = Get-Date
        $unixMs = ([DateTimeOffset]$arr).ToUnixTimeMilliseconds()
        Write-Output ("ARRIVED unixms=" + $unixMs + " sincePollStart=" + [int]($arr - $t0).TotalMilliseconds + " at=" + $p.X + "," + $p.Y)
        exit 0
    }
    Start-Sleep -Milliseconds 1
}
Write-Output "TIMEOUT cursor never reached target"
