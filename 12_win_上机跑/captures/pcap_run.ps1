# pcap_run.ps1 — 按场景抓 USB 包（需管理员）
# 用法: .\pcap_run.ps1 1   (1=插拔握手40s  2=震动30s  3=静默15s)
param([int]$scenario = 1)
$ErrorActionPreference = 'Continue'
$log = 'D:\win_game_project\12_win_上机跑\captures'
$usbc = 'C:\Program Files\USBPcap\USBPcapCMD.exe'
$devs = [System.IO.Directory]::GetFiles('\\.\','') | Where-Object { $_ -match 'USBPcap\d+$' }
if (-not $devs) { "NO_USBPCAP_DEVICE" | Out-File "$log\run_log.txt" -Append -Encoding utf8; exit 1 }
$d = ($devs | Select-Object -First 1) -replace '^\\\\\.\\', '\Device\'
"run s$scenario $(Get-Date -Format o) dev=$d" | Out-File "$log\run_log.txt" -Append -Encoding utf8

$pcap = "$log\0$scenario`_scene.pcap"
Remove-Item $pcap -ErrorAction SilentlyContinue
# 写 marker 给 AI 侧做动作时机同步
"started" | Out-File "$log\go$scenario.flag" -Encoding ascii

$proc = Start-Process -FilePath $usbc -ArgumentList @('-d', $d, '-o', $pcap, '-n') -PassThru -WindowStyle Hidden
$dur = switch ($scenario) { 1 {40} 2 {30} 3 {15} default {20} }
Start-Sleep $dur
Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
Start-Sleep 2
$sz = (Get-Item $pcap -ErrorAction SilentlyContinue).Length
"done s$scenario $(Get-Date -Format o) size=$sz" | Out-File "$log\run_log.txt" -Append -Encoding utf8
