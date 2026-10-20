$ErrorActionPreference = "Stop"
$B = "http://192.168.31.89:8000/rpc"
function Call($body) {
  Invoke-RestMethod -Method Post -Uri $B -ContentType "application/json" -Body $body | Out-Null
  Start-Sleep -Milliseconds 250
}
function Key($m, $k) { Call ("{""id"":1,""method"":""keyCombo"",""params"":{""modifiers"":" + $m + ",""key"":" + $k + "}}") }

$old = Get-Clipboard -Raw

# 记事本里全选删干净（Ctrl+A 后按退格，选中内容整块消失）
Key 1 4
Key 0 42
# 把中文输入法掰回英文（Ctrl+Space），上一轮就是它把 webrtc 打成了中文
Key 1 44
Start-Sleep -Milliseconds 400
Key 1 4
Key 0 42

$s = "webrtc-ok-15"
Call ("{""id"":2,""method"":""typeText"",""params"":{""text"":""" + $s + """}}")
Start-Sleep -Milliseconds 600
Key 1 4
Key 1 6
Start-Sleep -Milliseconds 400
$got = Get-Clipboard -Raw
if ($null -ne $old) { Set-Clipboard -Value $old }
Write-Output ("typed=[" + $s + "] clipboard=[" + $got + "] match=" + ($got -eq $s))
