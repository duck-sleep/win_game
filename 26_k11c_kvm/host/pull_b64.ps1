param([string]$Remote = '/tmp/bench_frame.jpg', [string]$Local = 'D:\win_game_project\26_k11c_kvm\host\bench_frame.jpg', [string]$Port = 'COM14', [int]$Baud = 1500000, [int]$Chunk = 20)
# 串口一次性 base64 大文件会丢字节：按 $Chunk 行一块取，每行校验长度，坏块重取
$sp = New-Object System.IO.Ports.SerialPort -ArgumentList $Port, $Baud, ([System.IO.Ports.Parity]::None), 8, ([System.IO.Ports.StopBits]::One)
$sp.ReadTimeout = 100; $sp.DtrEnable = $true; $sp.Encoding = [System.Text.Encoding]::ASCII
$sp.Open()

function Ask([string]$cmd, [string]$end, [int]$sec = 10) {
    $sp.DiscardInBuffer()
    $sp.Write("$cmd`n")
    $sw = [Diagnostics.Stopwatch]::StartNew(); $buf = New-Object Text.StringBuilder
    while ($sw.Elapsed.TotalSeconds -lt $sec) {
        try { $buf.Append($sp.ReadExisting()) | Out-Null } catch {}
        if ($buf.ToString().Contains($end)) { break }
        Start-Sleep -Milliseconds 30
    }
    return $buf.ToString()
}

$sp.Write([string][char]3); Start-Sleep -Milliseconds 300
Ask 'stty -echo; bind "set enable-bracketed-paste off" 2>/dev/null' 'xx' 1 | Out-Null
$r = Ask "base64 -w76 $Remote > /tmp/_b64.txt; printf 'N%s\n' `$(wc -l < /tmp/_b64.txt)Z" 'Z' 5
$n = [int]([regex]::Match($r, 'N(\d+)Z').Groups[1].Value)
Write-Host "lines=$n"
$lines = New-Object 'System.Collections.Generic.List[string]'
for ($i = 1; $i -le $n; $i += $Chunk) {
    $j = [Math]::Min($n, $i + $Chunk - 1)
    for ($try = 0; $try -lt 5; $try++) {
        $r = Ask "printf 'S%sS\n' X; sed -n '$i,${j}p' /tmp/_b64.txt; printf 'E%sE\n' X" 'EXE' 5
        $a = $r.IndexOf('SXS'); $b = $r.IndexOf('EXE')
        if ($a -lt 0 -or $b -lt 0) { continue }
        $got = @($r.Substring($a + 3, $b - $a - 3) -split "`r?`n" | ForEach-Object { $_.Trim() } | Where-Object { $_ -ne '' })
        $want = $j - $i + 1
        $okLen = @($got | Select-Object -First ($want - 1) | Where-Object { $_.Length -ne 76 }).Count -eq 0
        if ($got.Count -eq $want -and $okLen) { $lines.AddRange([string[]]$got); break }
    }
    if ($try -ge 5) { throw "chunk $i-$j failed" }
}
$sp.Write("stty echo`n"); $sp.Close()
[IO.File]::WriteAllBytes($Local, [Convert]::FromBase64String(($lines -join '')))
Get-Item $Local | Select-Object Name, Length
