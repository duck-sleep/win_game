$ErrorActionPreference = 'Stop'
$cfg = Join-Path $env:USERPROFILE '.ssh\config'
$existing = Get-Content -LiteralPath $cfg -Raw
if ($existing -match '(?m)^\s*Host\s+k11c\s*$') {
    Write-Host 'CONFIG_ALREADY_HAS_k11c'
} else {
    $block = @(
        '',
        '# K11C IP-KVM board (RK3566, WiFi Duck_5G). IP drifts after reboot -> use mDNS name.',
        'Host k11c',
        '  HostName kickpi.local',
        '  User kickpi',
        '  IdentityFile ~/.ssh/id_ed25519',
        '  IdentitiesOnly yes',
        '  ServerAliveInterval 30'
    ) -join "`r`n"
    Add-Content -LiteralPath $cfg -Value $block -Encoding ASCII
    Write-Host 'CONFIG_APPENDED'
}
$boardDir = 'D:\win_game_project\26_k11c_kvm\board'
New-Item -ItemType Directory -Force -Path $boardDir | Out-Null
Write-Host ('BOARD_DIR=' + (Test-Path $boardDir))
Write-Host '--- tail of config ---'
Get-Content -LiteralPath $cfg | Select-Object -Last 9
