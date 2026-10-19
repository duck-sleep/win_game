$ErrorActionPreference = 'Stop'
Write-Host '--- ICMP ping board from laptop ---'
ping -n 10 192.168.31.89 | Select-String -Pattern 'ms|时间|TTL' | ForEach-Object { Write-Host $_.Line }
Write-Host '--- 20x bare TCP connect to :8000 ---'
$sw = [System.Diagnostics.Stopwatch]::StartNew()
for ($i = 0; $i -lt 20; $i++) {
    $c = New-Object System.Net.Sockets.TcpClient
    $c.Connect('192.168.31.89', 8000)
    $c.Close()
}
$ms = [int]$sw.ElapsedMilliseconds
Write-Host ('  20 connects = ' + $ms + 'ms -> ' + [Math]::Round($ms / 20, 1) + 'ms each')
Write-Host '--- 20x raw HTTP GET (one socket, no keep-alive) ---'
$sw = [System.Diagnostics.Stopwatch]::StartNew()
for ($i = 0; $i -lt 20; $i++) {
    $c = New-Object System.Net.Sockets.TcpClient
    $c.Connect('192.168.31.89', 8000)
    $s = $c.GetStream()
    $req = [System.Text.Encoding]::ASCII.GetBytes("GET /state HTTP/1.0`r`nHost: k`r`n`r`n")
    $s.Write($req, 0, $req.Length)
    $buf = New-Object byte[] 4096
    $n = $s.Read($buf, 0, 4096)
    $c.Close()
}
$ms = [int]$sw.ElapsedMilliseconds
Write-Host ('  20 raw GET = ' + $ms + 'ms -> ' + [Math]::Round($ms / 20, 1) + 'ms each')
Write-Host '--- laptop WLAN adapter power management ---'
Get-NetAdapterPowerManagement -ErrorAction SilentlyContinue | Where-Object { $_.Name -like '*WLAN*' -or $_.Name -like '*Wi*' } | ForEach-Object {
    Write-Host ('  ' + $_.Name + ' AllowComputerToTurnOffDevice=' + $_.AllowComputerToTurnOffDevice)
}
(Get-NetAdapterAdvancedProperty -ErrorAction SilentlyContinue | Where-Object { $_.DisplayName -match 'Power|Roam|Sleep' } | Select-Object -First 8 | ForEach-Object { Write-Host ('  ' + $_.DisplayName + ' = ' + $_.DisplayValue) })
