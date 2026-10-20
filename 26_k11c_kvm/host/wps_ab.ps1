param(
    [int]$Rounds = 5,
    [int]$PerRound = 12,
    [int]$IdleMs = 400,
    [string]$HostIp = "192.168.31.89"
)
# A single in-time A/B is not proof: the tail on this link is also driven by the
# laptop's own adapter power save, the AP and neighbour noise. Alternating ON/OFF
# rounds puts both arms in the same environment.
# NOTE: keep this file ASCII only - Windows PowerShell 5.1 reads .ps1 as GBK.
$ErrorActionPreference = 'Stop'
$body = '{"id":1,"method":"ping"}'

function SetPowersave([string]$state) {
    # sudo -S writes "[sudo] password for..." to stderr; with ErrorActionPreference=Stop
    # PowerShell promotes that native stderr line into a terminating error. Merge and drop it.
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    ssh -o BatchMode=yes -o ConnectTimeout=6 "kickpi@$HostIp" "printf kickpi | sudo -S iw dev wlan0 set power_save $state" 2>&1 | Out-Null
    $ErrorActionPreference = $prev
}

function Probe([int]$n) {
    $r = @()
    for ($i = 0; $i -lt $n; $i++) {
        Start-Sleep -Milliseconds $IdleMs
        $c = New-Object System.Net.Sockets.TcpClient
        $c.NoDelay = $true
        $sw = [System.Diagnostics.Stopwatch]::StartNew()
        try {
            $c.Connect($HostIp, 8000)
            $s = $c.GetStream()
            $req = "POST /rpc HTTP/1.1`r`nHost: x`r`nContent-Type: application/json`r`nContent-Length: " +
                   $body.Length + "`r`nConnection: close`r`n`r`n" + $body
            $b = [System.Text.Encoding]::ASCII.GetBytes($req)
            $s.Write($b, 0, $b.Length); $s.Flush()
            $buf = New-Object byte[] 4096
            $got = 0
            while ($true) { $k = $s.Read($buf, 0, $buf.Length); if ($k -le 0) { break }; $got += $k; if ($got -gt 200) { break } }
            $sw.Stop(); $r += [int]$sw.ElapsedMilliseconds
        } catch { $sw.Stop(); $r += -1 } finally { $c.Close() }
    }
    return $r
}

$on = @(); $off = @()
for ($k = 0; $k -lt $Rounds; $k++) {
    SetPowersave 'on';  Start-Sleep -Seconds 2; $on  += Probe $PerRound
    SetPowersave 'off'; Start-Sleep -Seconds 2; $off += Probe $PerRound
    Write-Output ("round $k done")
}

function Stat($name, $arr) {
    $a = @($arr | Where-Object { $_ -ge 0 } | Sort-Object)
    $n = $a.Count
    if ($n -lt 4) { Write-Output "$name not enough samples"; return }
    Write-Output ("{0}: n={1} min={2} med={3} p90={4} max={5}" -f $name, $n, $a[0],
        $a[[int](($n - 1) * 0.5)], $a[[int](($n - 1) * 0.90)], $a[$n - 1])
    Write-Output ("  all: " + (($a | ForEach-Object { "$_" }) -join " "))
}
Stat "PS-ON " $on
Stat "PS-OFF" $off
