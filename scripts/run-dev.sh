#!/usr/bin/env bash
# recycling_ssg — 로컬 개발 서버 2개(Backend :8000, Vision :8100) 기동
#
# DB는 항상 저장소 루트 .env 의 DATABASE_URL(MySQL)을 그대로 사용한다 — 이 스크립트가
# 별도로 덮어쓰지 않는다. 그 외 개발 편의 설정만 기본값을 주입한다:
#   - 이미지 저장: AWS S3 (배포와 동일)  ← STORAGE_BACKEND=s3
#   - Vision: 실제 YOLO 체크포인트
# 사용법:  bash scripts/run-dev.sh
# 중지:    Ctrl+C

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PY="$REPO_ROOT/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$REPO_ROOT/.venv/bin/python"
[ -x "$PY" ] || { echo "ERROR: .venv 를 찾을 수 없습니다. 먼저 'uv sync --all-packages' 를 실행하세요."; exit 1; }

# --- Vision 모델 체크포인트 자동 탐색 -------------------------------------
find_model() {
  [ -n "${MODEL_PATH:-}" ] && [ -f "$MODEL_PATH" ] && { echo "$MODEL_PATH"; return; }
  [ -f "weights/best.pt" ] && { echo "weights/best.pt"; return; }
  local found
  found="$(ls -1 ai/models/yolo/*/runs/*/weights/best.pt 2>/dev/null | head -n1)"
  [ -n "$found" ] && { echo "$found"; return; }
  echo ""
}

MODEL_PATH="$(find_model)"
if [ -z "$MODEL_PATH" ]; then
  echo "WARNING: YOLO 체크포인트를 찾지 못했습니다."
  echo "         Vision 서버는 뜨지만 /internal/v1/predict 가 503 VISION_MODEL_NOT_READY 를 반환합니다."
  echo "         학습된 best.pt 를 weights/best.pt 로 복사하거나 MODEL_PATH 로 지정하세요."
  MODEL_PATH="weights/best.pt"
fi
# MODEL_VERSION은 vision/.env 안에서만 수동으로 관리하는 단일 소스다 (사용자가
# 모델을 바꿀 때마다 직접 수정). 여기서 자동 추론해서 OS 환경변수로 export하면
# pydantic-settings가 그 값을 vision/.env보다 우선시켜버려서 늘 덮어써진다 --
# 그래서 절대 export하지 않고, 배너 표시용으로만 vision/.env를 읽는다.
DISPLAY_MODEL_VERSION="$(grep -E '^MODEL_VERSION=' vision/.env 2>/dev/null | tail -n1 | cut -d= -f2-)"
DISPLAY_MODEL_VERSION="${DISPLAY_MODEL_VERSION:-(vision/.env 미설정 → 기본값 yolo-recycling-v1)}"

LOG_DIR="$REPO_ROOT/.dev-logs"
mkdir -p "$LOG_DIR"

echo "=============================================="
echo " recycling_ssg 개발 서버"
echo "  Vision  : http://127.0.0.1:8100  (model=$DISPLAY_MODEL_VERSION)"
echo "  Backend : http://127.0.0.1:8000"
echo "  API 문서: http://127.0.0.1:8000/docs"
echo "  로그     : $LOG_DIR/{vision,backend}.log"
echo "=============================================="

cleanup() {
  echo ""
  echo "서버를 종료합니다..."
  [ -n "${VISION_PID:-}" ] && kill "$VISION_PID" 2>/dev/null
  [ -n "${BACKEND_PID:-}" ] && kill "$BACKEND_PID" 2>/dev/null
  wait 2>/dev/null
}
trap cleanup EXIT INT TERM

# --- Vision (:8100) -------------------------------------------------------
# --reload-dir 없이 두면 uvicorn이 cwd(저장소 루트) 전체를 감시한다 -- data/,
# ai/models/ 등 10만 개+ 파일이 걸려 기동이 눈에 띄게 느려진다. vision 코드와
# taxonomy JSON만 감시하도록 좁힌다.
MODEL_PATH="$MODEL_PATH" \
  "$PY" -m uvicorn vision.main:app --host 127.0.0.1 --port 8100 --reload \
  --reload-dir vision --reload-dir data/taxonomy \
  > "$LOG_DIR/vision.log" 2>&1 &
VISION_PID=$!

# --- Backend (:8000) ------------------------------------------------------
(
  cd backend
  # DATABASE_URL은 이 스크립트가 설정하지 않고 core/config.py가 저장소 루트
  # .env의 MySQL DATABASE_URL을 읽도록 비워둔다. pydantic-settings는 OS
  # 환경변수를 .env보다 항상 우선시키므로, 부모 셸 환경에 남은 값이 있으면
  # 그게 이겨버린다 -- 명시적으로 지워서 항상 .env가 이기게 한다.
  unset DATABASE_URL
  # 이미지는 배포와 동일하게 실제 S3에 저장한다(.env 의 AWS_* 필요). AWS 자격증명
  # 없이 돌려야 하면 STORAGE_BACKEND=local bash scripts/run-dev.sh 로 로컬 디스크에
  # 저장할 수 있다 -- 다만 그러면 images.s3_key 가 가리키는 파일이 S3 에 없게 된다.
  JWT_SECRET_KEY="${JWT_SECRET_KEY:-dev-only-insecure-secret-please-change-me-32bytes+}" \
  STORAGE_BACKEND="${STORAGE_BACKEND:-s3}" \
  LOCAL_STORAGE_DIR="${LOCAL_STORAGE_DIR:-../.local_storage}" \
  VISION_SERVER_BASE_URL="${VISION_SERVER_BASE_URL:-http://127.0.0.1:8100/internal/v1}" \
  AUTO_CREATE_TABLES=true AUTO_SEED_MASTER_DATA=true \
  "$PY" -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload \
  > "$LOG_DIR/backend.log" 2>&1
) &
BACKEND_PID=$!

# --- 준비 대기 ------------------------------------------------------------
for i in $(seq 1 60); do
  v=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8100/health 2>/dev/null || echo 000)
  b=$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/health 2>/dev/null || echo 000)
  if [ "$v" = "200" ] && [ "$b" = "200" ]; then
    echo ""
    echo "두 서버가 준비되었습니다. (${i}초)"
    echo "  Vision  : $(curl -s http://127.0.0.1:8100/health)"
    echo "  Backend : $(curl -s http://127.0.0.1:8000/health)"
    echo ""
    echo "이제 다른 터미널에서 스모크 테스트를 실행할 수 있습니다:"
    echo "  bash scripts/smoke-test.sh"
    echo ""
    echo "종료하려면 Ctrl+C."
    break
  fi
  sleep 1
done

wait
