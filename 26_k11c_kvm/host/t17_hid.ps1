Add-Type -AssemblyName System.Windows.Forms
$p = [System.Windows.Forms.Cursor]::Position
Write-Output ("cursor=" + $p.X + "," + $p.Y)
Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like '*VID_1D6B*' } |
  Select-Object Status, Class, FriendlyName, InstanceId | Format-Table -AutoSize | Out-String -Width 140
$k = Get-PnpDevice -PresentOnly | Where-Object { $_.InstanceId -like '*VID_1D6B*' -and $_.Class -eq 'HIDClass' }
Write-Output ("hid_children=" + ($k | Measure-Object).Count)
Get-PnpDevice -PresentOnly -Class HIDClass | Where-Object { $_.FriendlyName -like '*HID-Compliant*' } | Measure-Object | ForEach-Object { Write-Output ("generic_hid=" + $_.Count) }
