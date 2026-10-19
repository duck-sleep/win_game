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
public class W2 {
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
}

$p = Start-Process notepad -PassThru
Start-Sleep -Seconds 2
[void][W2]::ShowWindow($p.MainWindowHandle, 3)
[void][W2]::SetForegroundWindow($p.MainWindowHandle)
Start-Sleep -Milliseconds 900
$fp = 0
$null = [W2]::GetWindowThreadProcessId([W2]::GetForegroundWindow(), [ref]$fp)
Write-Host ('focused=' + $fp + ' notepad=' + $p.Id)
if ($fp -ne [uint32]$p.Id) { Write-Host 'ABORT_NO_FOCUS'; exit 1 }

$null = Post-RpcRaw 'typeText' '{"text":"ABCdef123"}'
Start-Sleep -Milliseconds 500
Shot 'D:\win_game_project\26_k11c_kvm\host\t6_d1.png'
$null = Post-RpcRaw 'keyCombo' '{"modifiers":1,"key":44}'
Start-Sleep -Milliseconds 600
$null = Post-RpcRaw 'typeText' '{"text":"XYZ789"}'
Start-Sleep -Milliseconds 500
Shot 'D:\win_game_project\26_k11c_kvm\host\t6_d2.png'
Write-Host 'shots: t6_d1.png (after ABCdef123) t6_d2.png (after Ctrl+Space + XYZ789)'
