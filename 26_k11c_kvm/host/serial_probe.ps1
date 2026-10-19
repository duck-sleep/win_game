param(
    [string]$Port = 'COM14',
    [int]$Baud = 1500000,
    [string]$CommandFile = '',
    [int]$TimeoutSec = 25
)

$ErrorActionPreference = 'Stop'
$Par = [System.IO.Ports.Parity]::None
$Stop = [System.IO.Ports.StopBits]::One
$sp = New-Object System.IO.Ports.SerialPort -ArgumentList $Port,$Baud,$Par,8,$Stop
$sp.ReadTimeout = 100
$sp.WriteTimeout = 2000
$sp.DtrEnable = $true
$sp.RtsEnable = $false
$sp.Encoding = [System.Text.Encoding]::ASCII
$sp.Open()

function Clean([string]$s) { return ($s -replace "[^\x20-\x7e`r`n]", '') }

function Read-Until([string]$marker, [int]$limitSec) {
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $buf = New-Object System.Text.StringBuilder
    while ($sw.Elapsed.TotalSeconds -lt $limitSec) {
        try {
            while ($sp.BytesToRead -gt 0) {
                $b = $sp.ReadByte()
                [void]$buf.Append([char]$b)
                if ($buf.ToString().Contains($marker)) { return $buf.ToString() }
            }
        } catch [System.TimeoutException] { Start-Sleep -Milliseconds 20 }
          catch [System.InvalidOperationException] { Start-Sleep -Milliseconds 50 }
    }
    return $buf.ToString() + "`n<<TIMEOUT>>"
}

function Send([string]$s) { $sp.Write($s) }

Write-Host "### port $Port opened @ $Baud 8N1"
Send "`n"
$w = Read-Until 'KZQZKQQ' 2
Write-Host "### wake banner: $(Clean $w)"

if ($CommandFile -ne '') {
    $cmds = @(Get-Content -LiteralPath $CommandFile) | Where-Object { $_.Trim() -ne '' }
    $i = 0
    foreach ($c in $cmds) {
        $i++
        $tag = "C{0:D2}" -f $i
        if ($c -like 'RAW:*') {
            Send ($c.Substring(4))
            Start-Sleep -Milliseconds 600
            Write-Host "===== RAW $tag : $(Clean (Read-Until 'KZQZKQQ' 3))"
            continue
        }
        Write-Host "`n===== $tag CMD: $c"
        $m = "KZ${tag}ZK"
        # clear any half-typed line / continuation prompt left from a previous command
        Send ([char]3)
        Start-Sleep -Milliseconds 200
        Send ($c + "`n")
        Start-Sleep -Milliseconds 150
        # marker is rebuilt by printf's %s, so the echoed command text never contains it
        $q = [char]39
        $pcmd = 'q=' + $tag + '; printf ' + $q + '\nKZ%sZK\n' + $q + ' "$q"' + "`n"
        Send ($pcmd)
        Write-Host (Clean (Read-Until $m $TimeoutSec))
    }
}

$sp.Close()
Write-Host "`n### port closed"
