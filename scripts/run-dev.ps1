# recycling_ssg - 로컬 개발 서버 2개(Backend :8000, Vision :8100) 기동 (PowerShell)
#
# DB는 항상 저장소 루트 .env 의 DATABASE_URL(MySQL)을 그대로 사용한다 — 이 스크립트가
# 별도로 덮어쓰지 않는다. 그 외 개발 편의 설정만 기본값을 주입한다:
#   - 이미지 저장: 로컬 디스크 (.local_storage)  <- STORAGE_BACKEND=local
#   - Vision: 실제 YOLO 체크포인트
#
# 사용법:  .\scripts\run-dev.ps1
# 중지:    Ctrl+C  (또는 .\scripts\stop-dev.ps1)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

$Py = Join-Path $RepoRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
    Write-Host "ERROR: .venv 를 찾을 수 없습니다. 먼저 'uv sync --all-packages' 를 실행하세요." -ForegroundColor Red
    exit 1
}

# --- Vision 모델 체크포인트 자동 탐색 ---
function Find-Model {
    if ($env:MODEL_PATH -and (Test-Path $env:MODEL_PATH)) { return (Resolve-Path $env:MODEL_PATH).Path }
    foreach ($p in @("weights\best.pt")) {
        if (Test-Path $p) { return (Resolve-Path $p).Path }
    }
    foreach ($dir in @("ai\models\yolo", "weights", "vision", "runs")) {
        $found = Get-ChildItem -Path $dir -Filter "best.pt" -Recurse -ErrorAction SilentlyContinue |
                 Select-Object -First 1
        if ($found) { return $found.FullName }
    }
    return $null
}

# 체크포인트 경로에서 버전 라벨 추정: <version>\weights\best.pt 형태면 <version>,
# 아니면 상위 폴더명. 버전 정보가 없으면 기본값.
function Get-ModelVersion([string]$Path) {
    if ($env:MODEL_VERSION) { return $env:MODEL_VERSION }
    $parent = Split-Path -Parent $Path
    if ($parent -and (Split-Path -Leaf $parent) -eq "weights") {
        $grandParent = Split-Path -Parent $parent
        # <RepoRoot>\weights\best.pt 는 버전 폴더가 없는 경우이므로 기본값으로 둔다.
        if ($grandParent -and $grandParent.TrimEnd('\') -ne $RepoRoot.TrimEnd('\')) {
            return (Split-Path -Leaf $grandParent)
        }
        return "yolo-recycling-v1"
    }
    if ($parent) {
        $leaf = Split-Path -Leaf $parent
        if ($leaf -and $leaf -notmatch '^(weight|weights)$') { return $leaf }
    }
    return "yolo-recycling-v1"
}

$ModelPath = Find-Model
if (-not $ModelPath) {
    Write-Host "WARNING: YOLO 체크포인트를 찾지 못했습니다." -ForegroundColor Yellow
    Write-Host "         Vision 서버는 뜨지만 /internal/v1/predict 가 503 VISION_MODEL_NOT_READY 를 반환합니다."
    Write-Host "         학습된 best.pt 를 weights\best.pt 로 복사하거나 MODEL_PATH 로 지정하세요."
    $ModelPath = Join-Path $RepoRoot "weights\best.pt"
}
$ModelVersion = Get-ModelVersion $ModelPath

$LogDir = Join-Path $RepoRoot ".dev-logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

Write-Host "=============================================="
Write-Host " recycling_ssg 개발 서버"
Write-Host "  Vision  : http://127.0.0.1:8100  (model=$ModelVersion)"
Write-Host "  Backend : http://127.0.0.1:8000"
Write-Host "  API 문서: http://127.0.0.1:8000/docs"
Write-Host "  로그     : $LogDir\{vision,backend}.log"
Write-Host "=============================================="

# --- 이전 세션의 잔여 프로세스 정리 ---
# 이전에는 Start-Process 로 wrapper powershell 을 띄우고 그 안에서 `& python`
# 으로 uvicorn 을 실행했다. wrapper 를 Stop-Process 로 죽여도 자식인 uvicorn
# 프로세스는 안 죽고 남아 포트를 계속 점유하는 경우가 있었다. 그 상태로 다시
# run-dev.ps1 을 실행하면: 새 uvicorn 은 바인딩 실패로 즉시 종료되지만, 헬스체크는
# 죽지 않은 이전 프로세스에 응답해버려 "준비 완료"로 오판하고, 다음 순간 새
# 프로세스가 죽은 걸 감지해 곧바로 "서버 프로세스가 종료되었습니다"가 뜨는
# 문제가 있었다. 시작 전에 포트 점유 프로세스를 정리해서 이를 막는다.
function Stop-StaleListener {
    param([int]$Port)
    $conns = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    $found = $false
    foreach ($c in $conns) {
        $proc = Get-Process -Id $c.OwningProcess -ErrorAction SilentlyContinue
        Write-Host "WARNING: 포트 $Port 를 이전 세션의 잔여 프로세스(PID $($c.OwningProcess), $($proc.ProcessName))가 점유하고 있어 종료합니다." -ForegroundColor Yellow
        Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        $found = $true
    }
    return $found
}
$hadStale = (Stop-StaleListener -Port 8100) -or (Stop-StaleListener -Port 8000)
if ($hadStale) { Start-Sleep -Milliseconds 500 }

# --- Vision (:8100) ---
# wrapper powershell 없이 python.exe 를 직접 기동한다: $visionProc.Id 가 곧
# uvicorn 프로세스 자신이므로, 나중에 Stop-Process 로 확실하게 종료된다(고아 프로세스 방지).
$env:MODEL_PATH    = $ModelPath
$env:MODEL_VERSION = $ModelVersion
$visionProc = Start-Process -FilePath $Py `
    -ArgumentList @("-m", "uvicorn", "vision.main:app", "--host", "127.0.0.1", "--port", "8100") `
    -WorkingDirectory $RepoRoot `
    -RedirectStandardOutput "$LogDir\vision.log" `
    -RedirectStandardError "$LogDir\vision.err.log" `
    -PassThru -WindowStyle Hidden

# --- Backend (:8000) ---
# DATABASE_URL은 일부러 설정하지 않는다: 비워두면 core/config.py가 저장소 루트
# .env의 MySQL DATABASE_URL을 그대로 읽는다.
$jwtSecret    = if ($env:JWT_SECRET_KEY) { $env:JWT_SECRET_KEY } else { "dev-only-insecure-secret-please-change-me-32bytes+" }
$storage      = if ($env:STORAGE_BACKEND) { $env:STORAGE_BACKEND } else { "local" }
$storageDir   = if ($env:LOCAL_STORAGE_DIR) { $env:LOCAL_STORAGE_DIR } else { "../.local_storage" }
$visionUrl    = if ($env:VISION_SERVER_BASE_URL) { $env:VISION_SERVER_BASE_URL } else { "http://127.0.0.1:8100/internal/v1" }

$env:JWT_SECRET_KEY         = $jwtSecret
$env:STORAGE_BACKEND        = $storage
$env:LOCAL_STORAGE_DIR      = $storageDir
$env:VISION_SERVER_BASE_URL = $visionUrl
$env:AUTO_CREATE_TABLES     = "true"
$env:AUTO_SEED_MASTER_DATA  = "true"
$backendProc = Start-Process -FilePath $Py `
    -ArgumentList @("-m", "uvicorn", "main:app", "--host", "127.0.0.1", "--port", "8000") `
    -WorkingDirectory (Join-Path $RepoRoot "backend") `
    -RedirectStandardOutput "$LogDir\backend.log" `
    -RedirectStandardError "$LogDir\backend.err.log" `
    -PassThru -WindowStyle Hidden

$visionProc.Id  | Out-File "$LogDir\vision.pid"  -Encoding ascii
$backendProc.Id | Out-File "$LogDir\backend.pid" -Encoding ascii

# --- 준비 대기 ---
$ready = $false
foreach ($i in 1..60) {
    try {
        $v = (Invoke-WebRequest "http://127.0.0.1:8100/health" -UseBasicParsing -TimeoutSec 2).StatusCode
        $b = (Invoke-WebRequest "http://127.0.0.1:8000/health" -UseBasicParsing -TimeoutSec 2).StatusCode
        if ($v -eq 200 -and $b -eq 200) {
            Write-Host ""
            Write-Host "두 서버가 준비되었습니다. ($i 초)" -ForegroundColor Green
            Write-Host ("  Vision  : " + (Invoke-RestMethod "http://127.0.0.1:8100/health" | ConvertTo-Json -Compress))
            Write-Host ("  Backend : " + (Invoke-RestMethod "http://127.0.0.1:8000/health" | ConvertTo-Json -Compress))
            $ready = $true
            break
        }
    } catch { Start-Sleep -Seconds 1 }
}

if (-not $ready) {
    Write-Host "서버가 준비되지 않았습니다. 로그를 확인하세요: $LogDir" -ForegroundColor Red
    Get-Content "$LogDir\vision.err.log", "$LogDir\backend.err.log" -Tail 20 -ErrorAction SilentlyContinue
    exit 1
}

Write-Host ""
Write-Host "이제 다른 터미널에서 스모크 테스트를 실행할 수 있습니다:" -ForegroundColor Cyan
Write-Host "  bash scripts/smoke-test.sh"
Write-Host ""
Write-Host "종료: .\scripts\stop-dev.ps1  (또는 이 창에서 Ctrl+C)"
Write-Host ""

try {
    while ($true) {
        Start-Sleep -Seconds 2
        if ($visionProc.HasExited -or $backendProc.HasExited) {
            Write-Host "서버 프로세스가 종료되었습니다. 로그를 확인하세요: $LogDir" -ForegroundColor Red
            break
        }
    }
} finally {
    Write-Host "서버를 종료합니다..."
    foreach ($p in @($visionProc, $backendProc)) {
        if (-not $p.HasExited) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue }
    }
}
