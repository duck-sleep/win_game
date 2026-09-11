# pcap_setup.ps1 — USBPcap 激活：启动服务 + 重绑 xHCI 控制器（需管理员）
# 效果：所有 USB 设备会断电 3~5 秒后自动恢复（鼠标键盘可能短暂卡一下）
$ErrorActionPreference = 'Continue'
$log = 'D:\win_game_project\12_win_上机跑\captures\setup_log.txt'
"=== setup $(Get-Date -Format o) ===" | Out-File $log -Encoding utf8

"--- net start USBPcap ---" | Out-File $log -Append -Encoding utf8
net start USBPcap 2>&1 | Out-File $log -Append -Encoding utf8
Start-Sleep 2

"--- before bounce: USBPcap devices ---" | Out-File $log -Append -Encoding utf8
[System.IO.Directory]::GetFiles('\\.\','') | Where-Object { $_ -match 'USBPcap' } | Out-File $log -Append -Encoding utf8

# 找 Intel xHCI 控制器并重绑（让 USBPcap 过滤驱动挂上设备栈）
$ctl = Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'PCI\VEN_8086*' -and $_.Class -eq 'USB' } | Select-Object -First 1
"CONTROLLER: $($ctl.InstanceId) / $($ctl.FriendlyName)" | Out-File $log -Append -Encoding utf8

"--- disable ---" | Out-File $log -Append -Encoding utf8
pnputil /disable-device "$($ctl.InstanceId)" 2>&1 | Out-File $log -Append -Encoding utf8
Start-Sleep 4
"--- enable ---" | Out-File $log -Append -Encoding utf8
pnputil /enable-device "$($ctl.InstanceId)" 2>&1 | Out-File $log -Append -Encoding utf8
Start-Sleep 6

"--- after bounce: USBPcap devices ---" | Out-File $log -Append -Encoding utf8
[System.IO.Directory]::GetFiles('\\.\','') | Where-Object { $_ -match 'USBPcap' } | Out-File $log -Append -Encoding utf8
"--- done ---" | Out-File $log -Append -Encoding utf8
