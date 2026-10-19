$ErrorActionPreference = 'Continue'
$ips = @('192.168.31.89', '192.168.31.90')
$sw = [System.Diagnostics.Stopwatch]::StartNew()
$dead = $false
$tHttp = $null; $tHid = $null; $fps = $null
while ($sw.Elapsed.TotalSeconds -lt 200) {
    Start-Sleep -Seconds 3
    if (-not $tHttp) {
        foreach ($ip in $ips) {
            try {
                $s = Invoke-RestMethod ("http://" + $ip + ":8000/state") -TimeoutSec 3
                if ($s.fps -gt 20) { $tHttp = [int]$sw.Elapsed.TotalSeconds; $fps = $s.fps; $script:ip = $ip; break }
            } catch { }
        }
    }
    if (-not $tHid) {
        $kb = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like '*VID_1D6B&PID_0104&MI_00*' }
        $ms = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like '*VID_1D6B&PID_0104&MI_01*' }
        $acm = Get-PnpDevice -PresentOnly -ErrorAction SilentlyContinue | Where-Object { $_.InstanceId -like '*VID_1D6B&PID_0104&MI_02*' }
        if ($kb -and $ms -and $acm -and $kb.Status -eq 'OK' -and $ms.Status -eq 'OK') {
            $tHid = [int]$sw.Elapsed.TotalSeconds
            Write-Host ("  HID: kb=" + $kb.Status + " mouse=" + $ms.Status + " acm=" + $acm.Status + " acmName=" + $acm.FriendlyName)
        }
    }
    if ($tHttp -and $tHid) { break }
    Write-Host ("  t=" + [int]$sw.Elapsed.TotalSeconds + "s http=" + $tHttp + " hid=" + $tHid)
}
Write-Host ("RESULT http_up_at=" + $tHttp + "s fps=" + $fps + " ip=" + $script:ip)
Write-Host ("RESULT hid_up_at=" + $tHid + "s")
if (-not $tHttp -or -not $tHid) { Write-Host 'T8_NOT_READY_IN_200S' }
