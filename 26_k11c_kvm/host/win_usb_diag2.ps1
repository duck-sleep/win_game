$ErrorActionPreference = 'SilentlyContinue'
Write-Output "=== present USB\\* now ==="
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\*' } |
  ForEach-Object {
    $p = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -Key 'DEVPKEY_Device_ProblemCode').Data
    "{0,-10} {1,-9} prob={2,-5} {3} :: {4}" -f $_.Status, $_.Class, $p, $_.FriendlyName, $_.InstanceId
  }
Write-Output ""
Write-Output "=== anything 1D6B / KICKPI / K11C (present or not) ==="
Get-PnpDevice | Where-Object { $_.InstanceId -match '1D6B' -or $_.FriendlyName -match 'KICKPI|K11C' } |
  ForEach-Object {
    $p = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -Key 'DEVPKEY_Device_ProblemCode').Data
    "{0,-10} {1,-9} prob={2,-5} {3} :: {4}" -f $_.Status, $_.Class, $p, $_.FriendlyName, $_.InstanceId
  }
Write-Output ""
Write-Output "=== USB controller root-hub children (physical topology) ==="
$hub = Get-PnpDevice -PresentOnly -Class USB | Where-Object { $_.InstanceId -like 'USB\ROOT_HUB*' -or $_.InstanceId -like 'USB\VID_8086*' }
foreach ($h in $hub) {
  Write-Output "HUB: $($h.InstanceId)  $($h.FriendlyName)"
  Get-PnpDevice -PresentOnly | Where-Object { (Get-PnpDeviceProperty -InstanceId $_.InstanceId -Key 'DEVPKEY_Device_Parent').Data -eq $h.InstanceId } |
    ForEach-Object { "   child: {0,-9} prob={1} {2} :: {3}" -f $_.Status, (Get-PnpDeviceProperty -InstanceId $_.InstanceId -Key 'DEVPKEY_Device_ProblemCode').Data, $_.FriendlyName, $_.InstanceId }
}
