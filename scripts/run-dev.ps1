# recycling_ssg - 로컬 개발 서버 2개(Backend :8000, Vision :8100) 기동 (PowerShell)
#
# AWS/MySQL/외부 API 키 없이도 전체 흐름이 동작하도록 개발용 설정을 사용한다:
#   - DB: SQLite 파일 (backend\dev.sqlite3)
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
    if ($env:MODEL_PATH -and (Test-Path $env:MODEL_PATH)) { return $env:MODEL_PATH }
    if (Test-Path "weights\best.pt") { return "weights\best.pt" }
    $found = Get-ChildItem -Path "ai\models\yolo" -Filter "best.pt" -Recurse -ErrorAction SilentlyContinue |
             Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

$ModelPath = Find-Model
if (-not $ModelPath) {
    Write-Host "WARNING: YOLO 체크포인트를 찾지 못했습니다." -ForegroundColor Yellow
    Write-Host "         Vision 서버는 뜨지만 /internal/v1/predict 가 503 VISION_MODEL_NOT_READY 를 반환합니다."
    Write-Host "         학습된 best.pt 를 weights\best.pt 로 복사하거나 MODEL_PATH 로 지정하세요."
    $ModelPath = "weights\best.pt"
}
$ModelVersion = if ($env:MODEL_VERSION) { $env:MODEL_VERSION } else { Split-Path -Leaf (Split-Path -Parent (Split-Path -Parent $ModelPath)) }

$LogDir = Join-Path $RepoRoot ".dev-logs"
if (-not (Test-Path $LogDir)) { New-Item -ItemType Directory -Path $LogDir | Out-Null }

Write-Host "=============================================="
Write-Host " recycling_ssg 개발 서버"
Write-Host "  Vision  : http://127.0.0.1:8100  (model=$ModelVersion)"
Write-Host "  Backend : http://127.0.0.1:8000"
Write-Host "  API 문서: http://127.0.0.1:8000/docs"
Write-Host "  로그     : $LogDir\{vision,backend}.log"
Write-Host "=============================================="

# --- Vision (:8100) ---
$visionEnv = @{
    MODEL_PATH    = $ModelPath
    MODEL_VERSION = $ModelVersion
}
$visionScript = @"
`$env:MODEL_PATH='$($visionEnv.MODEL_PATH)'
`$env:MODEL_VERSION='$($visionEnv.MODEL_VERSION)'
Set-Location '$RepoRoot'
& '$Py' -m uvicorn vision.main:app --host 127.0.0.1 --port 8100
"@
$visionProc = Start-Process powershell.exe `
    -ArgumentList "-NoProfile", "-Command", $visionScript `
    -RedirectStandardOutput "$LogDir\vision.log" `
    -RedirectStandardError "$LogDir\vision.err.log" `
    -PassThru -WindowStyle Hidden

# --- Backend (:8000) ---
$dbUrl        = if ($env:DATABASE_URL) { $env:DATABASE_URL } else { "sqlite:///./dev.sqlite3" }
$jwtSecret    = if ($env:JWT_SECRET_KEY) { $env:JWT_SECRET_KEY } else { "dev-only-insecure-secret-please-change-me-32bytes+" }
$storage      = if ($env:STORAGE_BACKEND) { $env:STORAGE_BACKEND } else { "local" }
$storageDir   = if ($env:LOCAL_STORAGE_DIR) { $env:LOCAL_STORAGE_DIR } else { "../.local_storage" }
$visionUrl    = if ($env:VISION_SERVER_BASE_URL) { $env:VISION_SERVER_BASE_URL } else { "http://127.0.0.1:8100/internal/v1" }

$backendScript = @"
`$env:DATABASE_URL='$dbUrl'
`$env:JWT_SECRET_KEY='$jwtSecret'
`$env:STORAGE_BACKEND='$storage'
`$env:LOCAL_STORAGE_DIR='$storageDir'
`$env:VISION_SERVER_BASE_URL='$visionUrl'
`$env:AUTO_CREATE_TABLES='true'
`$env:AUTO_SEED_MASTER_DATA='true'
Set-Location '$RepoRoot\backend'
& '$Py' -m uvicorn main:app --host 127.0.0.1 --port 8000
"@
$backendProc = Start-Process powershell.exe `
    -ArgumentList "-NoProfile", "-Command", $backendScript `
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
