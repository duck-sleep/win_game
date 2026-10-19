$ErrorActionPreference = 'Stop'
$ip = '192.168.31.89'
$port = 8000

function Post-RpcRaw($method, $paramsJson) {
    $c = New-Object System.Net.Sockets.TcpClient
    $c.NoDelay = $true
    $c.Connect($ip, $port)
    $s = $c.GetStream()
    $s.ReadTimeout = 20000
    $body = '{"id":1,"method":"' + $method + '","params":' + $paramsJson + '}'
    $b = [System.Text.Encoding]::UTF8.GetBytes($body)
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

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @"
using System;
using System.Runtime.InteropServices;
public class W {
  [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
  [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h, int n);
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
}
"@

function Shot($path) {
    $b = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bmp = New-Object System.Drawing.Bitmap $b.Width, $b.Height
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.CopyFromScreen($b.X, $b.Y, 0, 0, $b.Size)
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose(); $bmp.Dispose()
    return (Get-FileHash -Algorithm MD5 -LiteralPath $path).Hash
}

# Start-Process notepad 在这台机器上会弹"你要如何打开这个文件"，必须给全路径；
# 且 -PassThru 回来的对象 ProcessName 是空的，所以按进程名找最新的那个
Start-Process "$env:SystemRoot\System32\notepad.exe" | Out-Null
Start-Sleep -Seconds 2
$p = Get-Process notepad -ErrorAction SilentlyContinue | Sort-Object StartTime -Descending | Select-Object -First 1
if ($null -eq $p) { Write-Host 'ABORT_NO_NOTEPAD_PROCESS'; exit 1 }
Write-Host ('notepad pid=' + $p.Id + ' start=' + $p.StartTime.ToString('HH:mm:ss'))
$h = $p.MainWindowHandle
[void][W]::ShowWindow($h, 3)
[void][W]::SetForegroundWindow($h)
Start-Sleep -Milliseconds 900
$fp = 0
$null = [W]::GetWindowThreadProcessId([W]::GetForegroundWindow(), [ref]$fp)
Write-Host ('focused pid=' + $fp + ' notepad pid=' + $p.Id)
if ($fp -ne [uint32]$p.Id) { Write-Host 'ABORT_NOTEPAD_NOT_FOCUSED'; exit 1 }

# --- test 2: IME switch + typeText + clipboard read-back ---
Set-Clipboard -Value 'SENTINEL_SHOULD_NOT_SURVIVE'
$null = Post-RpcRaw 'keyCombo' '{"modifiers":1,"key":44}'   # Ctrl+Space -> English input
Start-Sleep -Milliseconds 500
$t = Post-RpcRaw 'typeText' '{"text":"Hello K11C 123!"}'
Write-Host ('typeText resp: ' + ($t -replace '(?s).*?(\{.*)$', '$1'))
Start-Sleep -Milliseconds 400
$null = Post-RpcRaw 'keyCombo' '{"modifiers":1,"key":4}'    # Ctrl+A
Start-Sleep -Milliseconds 250
$null = Post-RpcRaw 'keyCombo' '{"modifiers":1,"key":6}'    # Ctrl+C
Start-Sleep -Milliseconds 600
$clip = (Get-Clipboard -Raw)
if ($null -ne $clip) { $clip = $clip.TrimEnd("`r", "`n") }
Write-Host ('T6-2 clipboard=[' + $clip + '] match=' + ($clip -eq 'Hello K11C 123!'))

# --- test 3: wheel ---
for ($i = 1; $i -le 60; $i++) {
    $null = Post-RpcRaw 'typeText' ('{"text":"line ' + $i + ' of sixty"}')
    $null = Post-RpcRaw 'keyCombo' '{"modifiers":0,"key":40}'   # Enter
}
$null = Post-RpcRaw 'keyCombo' '{"modifiers":1,"key":74}'      # Ctrl+Home -> top
$null = Post-RpcRaw 'absMouseReport' '{"x":16384,"y":16384,"buttons":0}'
Start-Sleep -Milliseconds 500
$h1 = Shot 'D:\win_game_project\26_k11c_kvm\host\t6_before.png'
$null = Post-RpcRaw 'wheelReport' '{"y":-5,"x":0}'
Start-Sleep -Milliseconds 900
$h2 = Shot 'D:\win_game_project\26_k11c_kvm\host\t6_after.png'
Write-Host ('T6-3 before=' + $h1 + ' after=' + $h2 + ' scrolled=' + ($h1 -ne $h2))
