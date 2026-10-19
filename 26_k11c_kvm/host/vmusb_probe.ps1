$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$id = 'USB\VID_0E0F&PID_0001\5&299D89E&0&10'
Write-Output "##### present node $id"
foreach ($k in 'DEVPKEY_Device_LastArrivalDate','DEVPKEY_Device_LastRemovalDate','DEVPKEY_Device_Parent','DEVPKEY_Device_ProblemCode','DEVPKEY_Device_ProblemStatus','DEVPKEY_Device_BusReportedDeviceDesc','DEVPKEY_Device_FriendlyName','DEVPKEY_Device_Class','DEVPKEY_Device_Service','DEVPKEY_Device_HardwareIds','DEVPKEY_Device_CompatibleIds','DEVPKEY_Device_Address','DEVPKEY_Device_InstallState','DEVPKEY_usb_DeviceEnumNumberOfOpenHandles') {
    $v = (Get-PnpDeviceProperty -InstanceId $id -Key $k)
    if ($v) { "{0,-45} = {1}" -f $k.Split('_')[-1], ($v.Data -join '|') }
}

Write-Output ""
Write-Output "##### vmusb Device Parameters in registry"
$p = 'HKLM:\SYSTEM\CurrentControlSet\Enum\USB\VID_0E0F&PID_0001\5&299d89e&0&10'
if (Test-Path $p) {
    Get-ItemProperty $p | Format-List | Out-String -Width 300
    $dp = Join-Path $p 'Device Parameters'
    if (Test-Path $dp) { Get-ItemProperty $dp | Format-List | Out-String -Width 300 }
} else { Write-Output "  (missing)" }

Write-Output "##### all vmusb instances sorted by arrival"
Get-PnpDevice | Where-Object { $_.InstanceId -like 'USB\VID_0E0F&PID_0001*' } | ForEach-Object {
    $a = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -Key 'DEVPKEY_Device_LastArrivalDate').Data
    "{0,-9} arrive={1}  {2}" -f $_.Status, $a, $_.InstanceId
} | Sort-Object -Descending

Write-Output ""
Write-Output "##### 1D6B:0104 node detail (historical success)"
$id2 = (Get-PnpDevice | Where-Object { $_.InstanceId -match '1D6B&PID_0104' -and $_.InstanceId -notmatch 'MI_' }).InstanceId
Write-Output "  instance: $id2"
foreach ($k in 'DEVPKEY_Device_LastArrivalDate','DEVPKEY_Device_LastRemovalDate','DEVPKEY_Device_Service','DEVPKEY_Device_ProblemCode') {
    "{0,-28} = {1}" -f $k.Split('_')[-1], (Get-PnpDeviceProperty -InstanceId $id2 -Key $k).Data
}
Get-PnpDevice | Where-Object { $_.InstanceId -match '6&32ECFF3A' } | ForEach-Object { "   {0,-9} {1} :: {2}" -f $_.Status, $_.FriendlyName, $_.InstanceId }
