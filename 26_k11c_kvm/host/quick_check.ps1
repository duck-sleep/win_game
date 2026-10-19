$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
Write-Output "### now: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
Write-Output "=== 1D6B present ==="
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -match '1D6B' } |
  Format-Table Status,Class,FriendlyName,InstanceId -AutoSize | Out-String -Width 300
Write-Output "=== all present USB-device nodes (non-hub) ==="
Get-PnpDevice -PresentOnly -Class USB,HIDClass,Keyboard,Mouse,Ports,USBDevice,mtd,Image,Audio -ErrorAction SilentlyContinue |
  Where-Object { $_.InstanceId -like 'USB\*' -or $_.InstanceId -like 'HID\*' -or $_.InstanceId -like 'USBPRINT\*' } |
  Sort-Object InstanceId | Format-Table Status,Class,FriendlyName,InstanceId -AutoSize | Out-String -Width 300
Write-Output "=== problem codes for present USB top-level nodes ==="
foreach ($id in @('USB\VID_0E0F&PID_0001\5&299D89E&0&10','USB\VID_1D6B&PID_0104\00000001')) {
  $d = Get-PnpDevice -InstanceId $id
  if ($d) {
    $prob = (Get-PnpDeviceProperty -InstanceId $id -Key 'DEVPKEY_Device_ProblemCode').Data
    $arr  = (Get-PnpDeviceProperty -InstanceId $id -Key 'DEVPKEY_Device_LastArrivalDate').Data
    $rem  = (Get-PnpDeviceProperty -InstanceId $id -Key 'DEVPKEY_Device_LastRemovalDate').Data
    $par  = (Get-PnpDeviceProperty -InstanceId $id -Key 'DEVPKEY_Device_Parent').Data
    "{0}`n   present={1} status={2} problem={3} parent={4}`n   arrival={5} removal={6}" -f $id,$d.Present,$d.Status,$prob,$par,$arr,$rem
  } else { "{0}  (no such node)" -f $id }
}
