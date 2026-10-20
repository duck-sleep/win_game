$ErrorActionPreference = "Stop"
$B = "http://192.168.31.89:8000/rpc"
function Call($body) {
  Invoke-RestMethod -Method Post -Uri $B -ContentType "application/json" -Body $body | Out-Null
  Start-Sleep -Milliseconds 250
}
function Key($m, $k) { Call ("{""id"":1,""method"":""keyCombo"",""params"":{""modifiers"":" + $m + ",""key"":" + $k + "}}") }

$old = Get-Clipboard -Raw
$s = "ab1cd1ef"
for ($i = 0; $i -le 2; $i++) {
  Key 1 4
  Key 0 42
  Call ("{""id"":2,""method"":""typeText"",""params"":{""text"":""" + $s + """}}")
  Start-Sleep -Milliseconds 500
  Key 1 4
  Key 1 6
  Start-Sleep -Milliseconds 350
  $got = Get-Clipboard -Raw
  $ok = ($got -eq $s)
  Write-Output ("try" + $i + " clipboard=[" + $got + "] match=" + $ok)
  if ($ok) { break }
  # 上一轮是中文输入法在捣乱，切一次输入法再来（Ctrl+Space 是开关，可能要按两次才回到英文）
  Key 1 44
}
if ($null -ne $old) { Set-Clipboard -Value $old }
