$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output "### now $(Get-Date -Format 'HH:mm:ss')"
Write-Output "=== System log, last 45 min, any USB-ish event ==="
Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=(Get-Date).AddMinutes(-45)} |
  Where-Object { ($_.Message -match 'USB|1D6B|Rockchip|K11C|device') -or ($_.ProviderName -match 'USB|PnP|Kernel-PnP') } |
  Select-Object -First 40 |
  ForEach-Object { "{0}  {1,-42} Id={2,-6} {3}  {4}" -f $_.TimeCreated.ToString('HH:mm:ss'), $_.ProviderName, $_.Id, $_.LevelDisplayName, (($_.Message -replace '\s+',' ').Substring(0,[Math]::Min(140,($_.Message -replace '\s+',' ').Length))) }

Write-Output ""
Write-Output "=== USB-related providers that exist in System log ==="
Get-WinEvent -ListProvider 'Microsoft-Windows-USB-USBXHCI-tracing','Microsoft-Windows-USB-USBHub4-tracing','Microsoft-Windows-USB-USBPRINT','Microsoft-Windows-usbccgp','USBPSP','Microsoft-Windows-Kernel-PnP' -ErrorAction SilentlyContinue | ForEach-Object { $_.Name }

Write-Output ""
Write-Output "=== present devices whose parent is a USB root hub (all ports) ==="
$roots = Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\ROOT_HUB*' -or $_.InstanceId -like 'USB\VID_8086&PID_06ED*' }
foreach ($r in $roots) {
    Write-Output "PARENT $($r.InstanceId)"
    Get-PnpDevice -PresentOnly | Where-Object { (Get-PnpDeviceProperty -InstanceId $_.InstanceId -Key 'DEVPKEY_Device_Parent').Data -eq $r.InstanceId } | ForEach-Object {
        $a = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -Key 'DEVPKEY_Device_Address').Data
        "   port={0,-4} {1,-9} {2} :: {3}" -f $a, $_.Status, $_.FriendlyName, $_.InstanceId
    }
}

Write-Output ""
Write-Output "=== is any USB hub device present besides root hubs? ==="
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\*' -and (Get-PnpDeviceProperty -InstanceId $_.InstanceId -Key 'DEVPKEY_Device_HardwareIds').Data -notmatch 'ROOT' } |
  Where-Object { $_.Class -eq 'USB' } | ForEach-Object { "  {0} :: {1}" -f $_.FriendlyName, $_.InstanceId }
