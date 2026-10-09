$ErrorActionPreference = 'Stop'
Set-Location "D:\DataFolder\ProjectIctu\DoAn\Scopus-Ictu"

$TargetSha = "e5a328fb867a1b42ecce4ac9c3021716ea2dec36"

for ($i = 1; $i -le 60; $i++) {
    Write-Host "=== Poll $i (UTC $(Get-Date -Format 'HH:mm:ss')) ==="
    $statusJson = gh pr view 8 --repo qhun22/Scopus-Ictu --json statusCheckRollup 2>$null
    $node = $statusJson | ConvertFrom-Json
    $rollup = $node.statusCheckRollup
    $checks = @()
    if ($rollup -and $rollup.PSObject.Properties['contexts']) {
        $checks = @($rollup.contexts)
    }
    Write-Host "Check count: $($checks.Count)"
    foreach ($c in $checks) {
        $name = $c.name
        $state = $c.state
        $conclusion = $c.conclusion
        $startedAt = $c.startedAt
        $completedAt = $c.completedAt
        Write-Host "  - $name | state=$state | conclusion=$conclusion | started=$startedAt | completed=$completedAt"
    }
    $nonTerm = $checks | Where-Object { $_.state -notin @('SUCCESS', 'FAILURE', 'ERROR', 'SKIPPED', 'CANCELLED', 'NEUTRAL') }
    $backendOk = $checks | Where-Object { $_.name -eq 'Backend (Python)' -and $_.conclusion -eq 'SUCCESS' }
    $frontendOk = $checks | Where-Object { $_.name -eq 'Frontend (Node)' -and $_.conclusion -eq 'SUCCESS' }
    $backendFail = $checks | Where-Object { $_.name -eq 'Backend (Python)' -and $_.conclusion -in @('FAILURE', 'ERROR') }
    $frontendFail = $checks | Where-Object { $_.name -eq 'Frontend (Node)' -and $_.conclusion -in @('FAILURE', 'ERROR') }
    if ($backendFail -or $frontendFail) {
        Write-Host "Required job FAILED. Stopping."
        break
    }
    if ($backendOk -and $frontendOk) {
        Write-Host "Backend + Frontend both SUCCESS. Stopping."
        break
    }
    Start-Sleep -Seconds 10
}