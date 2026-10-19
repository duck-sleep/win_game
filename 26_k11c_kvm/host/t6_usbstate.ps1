Write-Host '=== 1D6B any state ==='
Get-PnpDevice | Where-Object { $_.InstanceId -like '*1D6B*' } | ForEach-Object {
    Write-Host ($_.Status + ' | ' + $_.Class + ' | ' + $_.FriendlyName + ' | ' + $_.InstanceId + ' | present=' + $_.Present)
}
Write-Host '=== USB devices not OK ==='
Get-PnpDevice -Class USB -ErrorAction SilentlyContinue | Where-Object { $_.Status -ne 'OK' } | ForEach-Object {
    Write-Host ($_.Status + ' | ' + $_.FriendlyName + ' | ' + $_.InstanceId)
}
Write-Host '=== HID devices not OK ==='
Get-PnpDevice -Class HIDClass -ErrorAction SilentlyContinue | Where-Object { $_.Status -ne 'OK' } | ForEach-Object {
    Write-Host ($_.Status + ' | ' + $_.FriendlyName + ' | ' + $_.InstanceId)
}
Write-Host '=== done ==='
