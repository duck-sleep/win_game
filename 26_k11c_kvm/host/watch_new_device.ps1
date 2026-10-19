param([int]$Seconds = 30)
$ErrorActionPreference = 'SilentlyContinue'

function Snap {
    (Get-PnpDevice -PresentOnly | ForEach-Object { $_.InstanceId.ToUpper() })
}

$base = Snap
$end = (Get-Date).AddSeconds($Seconds)
$seen = @{}
Write-Output "### polling for $Seconds s; baseline count = $($base.Count)"
while ((Get-Date) -lt $end) {
    $now = Snap
    foreach ($id in $now) {
        if ($base -notcontains $id -and -not $seen.ContainsKey($id)) {
            $seen[$id] = $true
            $d = Get-PnpDevice -InstanceId $id
            $prob = (Get-PnpDeviceProperty -InstanceId $id -Key 'DEVPKEY_Device_ProblemCode').Data
            $svc  = (Get-PnpDeviceProperty -InstanceId $id -Key 'DEVPKEY_Device_Service').Data
            $ts = Get-Date -Format 'HH:mm:ss.fff'
            Write-Output "[$ts] NEW  Status=$($d.Status) Class=$($d.Class) Problem=$prob Service=$svc  $($d.FriendlyName)  ::  $id"
        }
    }
    foreach ($id in $base) {
        if ($now -notcontains $id) {
            $key = "GONE:$id"
            if (-not $seen.ContainsKey($key)) {
                $seen[$key] = $true
                $ts = Get-Date -Format 'HH:mm:ss.fff'
                Write-Output "[$ts] GONE  $id"
            }
        }
    }
    Start-Sleep -Milliseconds 250
}
Write-Output "### polling done; new=$($seen.Count)"
