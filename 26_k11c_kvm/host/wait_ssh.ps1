$ip = '192.168.31.89'
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$deadline = 180
$ok = $false
while ($sw.Elapsed.TotalSeconds -lt $deadline) {
    Start-Sleep -Seconds 5
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect($ip, 22, $null, $null)
        if ($iar.AsyncWaitHandle.WaitOne(2000)) {
            $c.EndConnect($iar)
            $c.Close()
            Write-Host ("SSH_UP after {0:N0}s" -f $sw.Elapsed.TotalSeconds)
            $ok = $true
            break
        }
        $c.Close()
    } catch { }
    Write-Host ("  t={0:N0}s not yet" -f $sw.Elapsed.TotalSeconds)
}
if (-not $ok) { Write-Host "SSH_NOT_UP_WITHIN_$deadline`S" ; exit 1 }
