# bat_tee.ps1 - Chay launcher Python, hien thi tung dong realtime va ghi file log dong thoi
param(
    [string]$Python,
    [string]$Launcher,
    [string]$LogFile,
    [string]$Action,
    [string[]]$LauncherArgs = @()
)

$enc = [System.Text.Encoding]::UTF8

function log_line([string]$line) {
    Write-Host $line
    [System.IO.File]::AppendAllText($LogFile, $line + "`r`n", $enc)
}

$ts = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
log_line "[${ts}] HANH VI: ${Action}"

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName               = $Python
# Dung array de tranh van de escape — truyen tung arg rieng
$psi.UseShellExecute        = $false
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError  = $true
$psi.StandardOutputEncoding = $enc
$psi.StandardErrorEncoding  = $enc

# ArgumentList phai la chuoi don — tung arg co the co khoang trang nen quote rieng
$parts = @("`"$Launcher`"")
foreach ($a in $LauncherArgs) { $parts += "`"$a`"" }
$psi.Arguments = $parts -join " "

$p = [System.Diagnostics.Process]::new()
$p.StartInfo = $psi
[void]$p.Start()

# Doc stdout tung dong realtime; stderr doc sau khi process ket thuc (tranh deadlock)
while (-not $p.StandardOutput.EndOfStream) {
    $line = $p.StandardOutput.ReadLine()
    if ($null -ne $line) { log_line $line }
}
$p.WaitForExit()
# Flush stderr
$errContent = $p.StandardError.ReadToEnd()
if ($errContent) {
    foreach ($line in ($errContent -split "`r?`n")) {
        if ($line) { log_line $line }
    }
}

$rc  = $p.ExitCode
$ts2 = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$status = if ($rc -eq 0) { "THANH CONG" } else { "THAT BAI (ma thoat $rc)" }
log_line "[${ts2}] KET QUA ${Action}: ${status}"

exit $rc
