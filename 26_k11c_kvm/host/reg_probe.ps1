$ErrorActionPreference = 'SilentlyContinue'
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$paths = @(
  'HKLM:\SYSTEM\CurrentControlSet\Enum\USB\VID_0E0F&PID_0001',
  'HKLM:\SYSTEM\CurrentControlSet\Enum\USB\VID_1D6B&PID_0104',
  'HKLM:\SYSTEM\CurrentControlSet\Enum\USB\VID_0000&PID_0002'
)

foreach ($p in $paths) {
    Write-Output ""
    Write-Output "##### $p"
    if (-not (Test-Path $p)) { Write-Output "   (key missing)"; continue }
    Get-ChildItem $p | ForEach-Object {
        $inst = $_.PSChildName
        $ip = Get-ItemProperty $_.PSPath
        $fn = $_.GetValue('FriendlyName')
        $pp = $_.GetValue('ParentIdPrefix')
        $hw = $_.GetValue('HardwareID') -join ','
        Write-Output "  INSTANCE: $inst"
        Write-Output "     FriendlyName = $fn"
        Write-Output "     ParentIdPrefix = $pp   Class = $($ip.Class)   Service = $($ip.Service)"
        Write-Output "     HWIDs = $hw"
        Get-ChildItem $_.PSPath | ForEach-Object {
            $sub = $_.PSChildName
            $sip = Get-ItemProperty $_.PSPath
            $lc = $sip.'LastConnectTime'
            $lct = ''
            if ($lc) { try { $lct = ([DateTime]::FromFileTime([BitConverter]::ToUInt64($lc,0))).ToString('yyyy-MM-dd HH:mm:ss') } catch { $lct = '(raw)' } }
            Write-Output "        sub[$sub] Status=$($sip.Status) ConfigFlags=$($sip.ConfigFlags) LastConfigApplied=$($sip.LastConfigApplied) ConnectTime=$lct Problem=$((Get-ItemProperty (Join-Path $_.PSPath '0000') -ErrorAction SilentlyContinue).Problem)"
        }
    }
}

Write-Output ""
Write-Output "##### VMware arbitration service image path"
Get-CimInstance Win32_Service -Filter "Name='VMUSBArbService'" | Select-Object Name,State,StartMode,PathName | Format-List | Out-String
Write-Output "##### vmware vmdb: which VM is running + usb autoconnect prefs"
Get-ChildItem 'C:\Users\123456\AppData\Local\VirtualMachine\*.vmx' -ErrorAction SilentlyContinue | Select-Object -First 10 FullName | Out-String
Select-String -Path 'C:\Program Files (x86)\VMware\VMware Workstation\*.ini','C:\Users\123456\AppData\Roaming\VMware\preferences.ini' -Pattern 'usb|autoConnect' -ErrorAction SilentlyContinue | Select-Object -First 20 | Out-String -Width 300
