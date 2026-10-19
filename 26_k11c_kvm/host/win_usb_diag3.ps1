$ErrorActionPreference = 'SilentlyContinue'
Write-Output "=== 1) VMware USB nodes: where do they sit, what are they ==="
Get-PnpDevice | Where-Object { $_.InstanceId -like '*VID_0E0F*' } |
  ForEach-Object {
    $id = $_.InstanceId
    $parent = (Get-PnpDeviceProperty -InstanceId $id -Key 'DEVPKEY_Device_Parent').Data
    $addr   = (Get-PnpDeviceProperty -InstanceId $id -Key 'DEVPKEY_Device_Address').Data
    $hwids  = (Get-PnpDeviceProperty -InstanceId $id -Key 'DEVPKEY_Device_HardwareIds').Data -join ','
    $arrive = (Get-PnpDeviceProperty -InstanceId $id -Key 'DEVPKEY_Device_LastArrivalDate').Data
    $problem= (Get-PnpDeviceProperty -InstanceId $id -Key 'DEVPKEY_Device_ProblemCode').Data
    "{0,-9} addr={1,-4} problem={2,-4} parent={3}`n      id={4}`n      hw={5}`n      lastArrival={6}" -f $_.Status,$addr,$problem,$parent,$id,$hwids,$arrive
  }

Write-Output ""
Write-Output "=== 2) Children of the USB2 root hub (real ports) ==="
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like 'USB\ROOT_HUB*' } | ForEach-Object {
  $rh = $_.InstanceId
  Write-Output "ROOT: $rh ($($_.FriendlyName))"
  Get-PnpDevice -PresentOnly | Where-Object { (Get-PnpDeviceProperty -InstanceId $_.InstanceId -Key 'DEVPKEY_Device_Parent').Data -eq $rh } |
    ForEach-Object {
      $addr = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -Key 'DEVPKEY_Device_Address').Data
      $hw   = (Get-PnpDeviceProperty -InstanceId $_.InstanceId -Key 'DEVPKEY_Device_HardwareIds').Data -join ','
      "   port=$addr  status=$($_.Status) prob=$((Get-PnpDeviceProperty -InstanceId $_.InstanceId -Key 'DEVPKEY_Device_ProblemCode').Data)  $($_.FriendlyName)  ::  $($_.InstanceId)  [$hw]"
    }
}

Write-Output ""
Write-Output "=== 3) System log, last 20 min, any USB/PnP error or warning ==="
Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=(Get-Date).AddMinutes(-20)} -ErrorAction SilentlyContinue |
  Where-Object { $_.Message -match 'USB|device' -or $_.ProviderName -match 'USB|PnP' } |
  Select-Object -First 25 |
  ForEach-Object { "{0}  {1}  Id={2}  {3}  {4}" -f $_.TimeCreated,$_.ProviderName,$_.Id,$_.LevelDisplayName,($_.Message -replace '\s+',' ') }

Write-Output ""
Write-Output "=== 4) USB devices ever seen with 1D6B, with arrival dates ==="
Get-PnpDevice | Where-Object { $_.InstanceId -match '1D6B' } | ForEach-Object {
  $id=$_.InstanceId
  "{0,-9} lastArrival={1}  {2} :: {3}" -f $_.Status,(Get-PnpDeviceProperty -InstanceId $id -Key 'DEVPKEY_Device_LastArrivalDate').Data,$_.FriendlyName,$id
}
