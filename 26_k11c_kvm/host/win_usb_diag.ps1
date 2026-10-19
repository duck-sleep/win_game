$ErrorActionPreference = 'SilentlyContinue'
Write-Output "=== A) Any problematic / unknown device ==="
Get-PnpDevice | Where-Object { $_.Status -in @('Error','Unknown','Failure') -and $_.InstanceId -like 'USB*' } | Format-Table Status,FriendlyName,InstanceId -AutoSize | Out-String -Width 4096

Write-Output "=== B) Present USB\\* devices (all) with LastChange ==="
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\*' } | Sort-Object LastChange -Descending | Format-Table Status,Class,FriendlyName,InstanceId,LastChange -AutoSize | Out-String -Width 4096

Write-Output "=== C) Devices changed in the last 2 hours (any bus) ==="
$cutoff = (Get-Date).AddHours(-2)
Get-PnpDevice -PresentOnly | Where-Object { $_.LastChange -gt $cutoff } | Sort-Object LastChange -Descending | Format-Table Status,Class,FriendlyName,InstanceId,LastChange -AutoSize | Out-String -Width 4096

Write-Output "=== D) Kernel-PnP / USBPnP events, last 60 min ==="
Get-WinEvent -FilterHashtable @{LogName='Microsoft-Windows-USB-USBHub4%00PROXY'; StartTime=(Get-Date).AddMinutes(-60)} 2>$null | Select-Object -First 20 | Format-Table TimeCreated,Message -AutoSize | Out-String -Width 4096
Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=(Get-Date).AddMinutes(-60); ProviderName='Microsoft-Windows-Kernel-PnP','Microsoft-Windows-USB-USBXHCI-tracing','usbhub','USBPSP','usbccgp'} 2>$null | Select-Object -First 40 | Format-Table TimeCreated,ProviderName,Id,LevelDisplayName,Message -AutoSize | Out-String -Width 4096

Write-Output "=== E) Is this a VMware guest? ==="
Get-CimInstance Win32_ComputerSystem | Select-Object Manufacturer,Model,HypervisorPresent,TotalPhysicalMemory | Format-List | Out-String
Get-CimInstance Win32_BIOS | Select-Object Manufacturer,SMBIOSBIOSVersion | Format-List | Out-String
