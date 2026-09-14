#!/usr/bin/env bash
# recycling_ssg — 로컬 개발 서버 2개(Backend :8000, Vision :8100) 기동
#
# AWS/MySQL/외부 API 키 없이도 전체 흐름이 동작하도록 개발용 설정을 사용한다:
#   - DB: SQLite 파일 (backend/dev.sqlite3)
#   - 이미지 저장: 로컬 디스크 (.local_storage)  ← STORAGE_BACKEND=local
#   - Vision: 실제 YOLO 체크포인트
#
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
MODEL_VERSION="${MODEL_VERSION:-$(basename "$(dirname "$(dirname "$MODEL_PATH")")")}"

LOG_DIR="$REPO_ROOT/.dev-logs"
mkdir -p "$LOG_DIR"

echo "=============================================="
echo " recycling_ssg 개발 서버"
echo "  Vision  : http://127.0.0.1:8100  (model=$MODEL_VERSION)"
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
MODEL_PATH="$MODEL_PATH" MODEL_VERSION="$MODEL_VERSION" \
  "$PY" -m uvicorn vision.main:app --host 127.0.0.1 --port 8100 \
  > "$LOG_DIR/vision.log" 2>&1 &
VISION_PID=$!

# --- Backend (:8000) ------------------------------------------------------
(
  cd backend
  DATABASE_URL="${DATABASE_URL:-sqlite:///./dev.sqlite3}" \
  JWT_SECRET_KEY="${JWT_SECRET_KEY:-dev-only-insecure-secret-please-change-me-32bytes+}" \
  STORAGE_BACKEND="${STORAGE_BACKEND:-local}" \
  LOCAL_STORAGE_DIR="${LOCAL_STORAGE_DIR:-../.local_storage}" \
  VISION_SERVER_BASE_URL="${VISION_SERVER_BASE_URL:-http://127.0.0.1:8100/internal/v1}" \
  AUTO_CREATE_TABLES=true AUTO_SEED_MASTER_DATA=true \
  "$PY" -m uvicorn main:app --host 127.0.0.1 --port 8000 \
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
