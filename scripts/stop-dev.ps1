# recycling_ssg - run-dev.ps1 로 띄운 개발 서버 종료 (PowerShell)

$RepoRoot = Split-Path -Parent $PSScriptRoot
$LogDir = Join-Path $RepoRoot ".dev-logs"

$stopped = 0
foreach ($name in @("vision", "backend")) {
    $pidFile = Join-Path $LogDir "$name.pid"
    if (Test-Path $pidFile) {
        $processId = (Get-Content $pidFile -Raw).Trim()
        if ($processId) {
            try {
                Stop-Process -Id ([int]$processId) -Force -ErrorAction Stop
                Write-Host "$name 서버(PID $processId)를 종료했습니다." -ForegroundColor Green
                $stopped++
            } catch {
                Write-Host "$name 서버(PID $processId)는 이미 종료된 상태입니다."
            }
        }
        Remove-Item $pidFile -ErrorAction SilentlyContinue
    }
}

# PID 파일이 없을 때를 위한 포트 기반 정리
foreach ($port in @(8000, 8100)) {
    $conns = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        try {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction Stop
            Write-Host "포트 $port 를 점유한 프로세스(PID $($c.OwningProcess))를 종료했습니다." -ForegroundColor Green
            $stopped++
        } catch {}
    }
}

if ($stopped -eq 0) { Write-Host "종료할 개발 서버가 없습니다." }
