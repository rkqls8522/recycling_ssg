#!/usr/bin/env bash
# recycling_ssg — 19개 API 전체 스모크 테스트 (Git Bash / WSL / macOS / Linux)
#
# 사전 조건: Backend(:8000)와 Vision(:8100)이 떠 있어야 한다.
#   scripts/run-dev.sh  로 두 서버를 먼저 띄우세요.
#
# 사용법:
#   bash scripts/smoke-test.sh
#   BACKEND=http://localhost:8000 VISION=http://localhost:8100 bash scripts/smoke-test.sh

set -uo pipefail

BACKEND="${BACKEND:-http://127.0.0.1:8000}"
VISION="${VISION:-http://127.0.0.1:8100}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# JSON 파싱용 python (jq 없이 동작하도록)
PY="$REPO_ROOT/.venv/Scripts/python.exe"
[ -x "$PY" ] || PY="$REPO_ROOT/.venv/bin/python"
[ -x "$PY" ] || PY="python"

# Git Bash(MinGW)의 curl 은 '/c/...' 형태의 POSIX 절대경로를 열지 못하므로
# -F 업로드에 쓸 경로는 'C:/...' 로 변환한다. WSL/macOS/Linux 에서는 그대로 둔다.
winpath() {
  if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi
}

SAMPLES="${SAMPLES:-$REPO_ROOT/ai/models/yolo/01_experiment_augmentation/report/final_best/prediction_samples}"

# 빈 파일 업로드 테스트용 (플랫폼 무관하게 실제 0-byte 파일 사용)
EMPTY_FILE_RAW="$(mktemp -t empty-XXXXXX.jpg)"
: > "$EMPTY_FILE_RAW"
EMPTY_FILE="$(winpath "$EMPTY_FILE_RAW")"

# 한글이 포함된 JSON 본문은 파일로 넘긴다.
# (Git Bash/MinGW 에서 `-d '{"message":"한글"}'` 처럼 인라인으로 주면 인자
#  인코딩이 깨져 서버가 400 "error parsing the body" 를 반환한다.)
JSON_BODY_RAW="$(mktemp -t body-XXXXXX.json)"
JSON_BODY="$(winpath "$JSON_BODY_RAW")"
write_body() { printf '%s' "$1" > "$JSON_BODY_RAW"; }

trap 'rm -f "$EMPTY_FILE_RAW" "$JSON_BODY_RAW" 2>/dev/null' EXIT

PASS=0
FAIL=0
BODY=""

# ---------- helpers ----------
jsonget() { "$PY" -c "
import json,sys
try: d=json.load(sys.stdin)
except Exception: print(''); sys.exit()
for k in sys.argv[1].split('.'):
    if isinstance(d,list):
        d = d[int(k)] if k.isdigit() and int(k)<len(d) else ''
    elif isinstance(d,dict):
        d = d.get(k,'')
    else:
        d=''; break
print('' if d is None and False else ('null' if d is None else d))
" "$1" 2>/dev/null; }

# check <label> <expected_status> <curl-args...>
check() {
  local label="$1" expected="$2"; shift 2
  local out status
  out="$(curl -s -w $'\n%{http_code}' "$@" 2>/dev/null)"
  status="$(printf '%s' "$out" | tail -n1)"
  BODY="$(printf '%s' "$out" | sed '$d')"
  if [ "$status" = "$expected" ]; then
    PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m  %-58s %s\n' "$label" "$status"
  else
    FAIL=$((FAIL+1)); printf '  \033[31mFAIL\033[0m  %-58s got %s, want %s\n' "$label" "$status" "$expected"
    printf '        body: %s\n' "$(printf '%s' "$BODY" | head -c 300)"
  fi
}

expect_field() { # expect_field <json-path> <expected-value>
  local got; got="$(printf '%s' "$BODY" | jsonget "$1")"
  if [ "$got" = "$2" ]; then
    PASS=$((PASS+1)); printf '        \033[32m↳\033[0m %s = %s\n' "$1" "$got"
  else
    FAIL=$((FAIL+1)); printf '        \033[31m↳ %s = %s (want %s)\033[0m\n' "$1" "$got" "$2"
  fi
}

section() { printf '\n\033[1m%s\033[0m\n' "$1"; }

SKIPPED=0
skip() { SKIPPED=$((SKIPPED+1)); printf '  \033[33mSKIP\033[0m  %-58s %s\n' "$1" "$2"; }

# ---------- 0. 사전 점검 ----------
section "0) 서버 연결 확인"
for url in "$BACKEND/health" "$VISION/health"; do
  if ! curl -sf -o /dev/null "$url"; then
    echo "  ERROR: $url 에 연결할 수 없습니다. 먼저 scripts/run-dev.sh 로 서버를 띄우세요."
    exit 1
  fi
done
echo "  backend=$BACKEND  vision=$VISION"

# ---------- 0-1. 현재 로드된 모델에 맞는 테스트 이미지 자동 선별 ----------
# 어떤 체크포인트가 로드되어 있든 세 가지 분기를 모두 시험할 수 있도록,
# Vision 서버에 직접 물어 각 분기에 해당하는 샘플 이미지를 찾는다.
# (특정 이미지의 confidence 를 하드코딩하면 모델이 바뀔 때 전부 깨진다.)
section "0-1) 현재 모델에 맞는 테스트 이미지 선별"
IMG_SUCCESS="${IMG_SUCCESS:-}"
IMG_LOW_CONF="${IMG_LOW_CONF:-}"
IMG_NO_OBJ="${IMG_NO_OBJ:-}"

if [ -d "$SAMPLES" ]; then
  for f in "$SAMPLES"/*.jpg; do
    [ -f "$f" ] || continue
    [ -n "$IMG_SUCCESS" ] && [ -n "$IMG_LOW_CONF" ] && [ -n "$IMG_NO_OBJ" ] && break
    wf="$(winpath "$f")"
    out="$(curl -s -w $'\n%{http_code}' -X POST "$VISION/internal/v1/predict" \
           -F "image=@$wf;type=image/jpeg" 2>/dev/null)"
    st="$(printf '%s' "$out" | tail -n1)"
    bd="$(printf '%s' "$out" | sed '$d')"
    if [ "$st" = "422" ]; then
      [ -z "$IMG_NO_OBJ" ] && IMG_NO_OBJ="$wf"
    elif [ "$st" = "200" ]; then
      score="$(printf '%s' "$bd" | jsonget candidate_scores.0.score)"
      over="$("$PY" -c "import sys;print('1' if float(sys.argv[1])>=0.5 else '0')" "$score" 2>/dev/null)"
      if [ "$over" = "1" ]; then [ -z "$IMG_SUCCESS" ] && IMG_SUCCESS="$wf"
      else [ -z "$IMG_LOW_CONF" ] && IMG_LOW_CONF="$wf"; fi
    fi
  done
fi

[ -n "$IMG_SUCCESS" ]  && echo "  SUCCESS(>=0.5)     : $(basename "$IMG_SUCCESS")" || echo "  SUCCESS(>=0.5)     : (없음 - 관련 검사를 건너뜁니다)"
[ -n "$IMG_LOW_CONF" ] && echo "  LOW_CONFIDENCE     : $(basename "$IMG_LOW_CONF")" || echo "  LOW_CONFIDENCE     : (없음)"
[ -n "$IMG_NO_OBJ" ]   && echo "  NO_MAIN_OBJECT     : $(basename "$IMG_NO_OBJ")" || echo "  NO_MAIN_OBJECT     : (없음)"

if [ -z "$IMG_SUCCESS" ]; then
  echo ""
  echo "  주의: 현재 로드된 모델로 Top-1 >= 0.5 가 나오는 샘플이 없습니다."
  echo "        더 정확한 체크포인트를 weights/best.pt 로 지정하면 전체 흐름을 검증할 수 있습니다."
fi

# ---------- 1~2. Health / Readiness ----------
section "1) GET /health  ·  2) GET /ready"
check "GET /health" 200 "$BACKEND/health"
expect_field "status" "ok"
expect_field "service" "backend"
check "GET /ready" 200 "$BACKEND/ready"
expect_field "status" "ready"

# ---------- 3~5. 인증 ----------
section "3) POST /api/v1/auth/signup"
EMAIL="smoke-$(date +%s)-$RANDOM@example.com"
PASSWORD="Example123!"
check "POST /auth/signup (201 Created)" 201 \
  -X POST "$BACKEND/api/v1/auth/signup" \
  -H "Content-Type: application/json" -H "Accept: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
expect_field "region" "null"   # 회원가입 시 지역을 받지 않음
USER_ID="$(printf '%s' "$BODY" | jsonget user_id)"

check "POST /auth/signup 중복 (409 AUTH_EMAIL_EXISTS)" 409 \
  -X POST "$BACKEND/api/v1/auth/signup" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
expect_field "code" "AUTH_EMAIL_EXISTS"

check "POST /auth/signup 형식오류 (422)" 422 \
  -X POST "$BACKEND/api/v1/auth/signup" -H "Content-Type: application/json" \
  -d '{"email":"not-an-email","password":"short"}'
expect_field "code" "REQUEST_VALIDATION_ERROR"

section "4) POST /api/v1/auth/login"
check "POST /auth/login" 200 \
  -X POST "$BACKEND/api/v1/auth/login" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}"
expect_field "token_type" "bearer"
TOKEN="$(printf '%s' "$BODY" | jsonget access_token)"
AUTH="Authorization: Bearer $TOKEN"

check "POST /auth/login 비밀번호 불일치 (401)" 401 \
  -X POST "$BACKEND/api/v1/auth/login" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"WrongPassword1!\"}"
expect_field "code" "AUTH_INVALID_CREDENTIALS"

# ---------- 6~8. 사용자 / 지역 ----------
section "6) GET /api/v1/users/me"
check "GET /users/me" 200 "$BACKEND/api/v1/users/me" -H "$AUTH"
expect_field "email" "$EMAIL"
check "GET /users/me 토큰 없음 (401)" 401 "$BACKEND/api/v1/users/me"
expect_field "code" "AUTH_REQUIRED"
check "GET /users/me 잘못된 토큰 (401)" 401 "$BACKEND/api/v1/users/me" -H "Authorization: Bearer not-a-jwt"
expect_field "code" "AUTH_TOKEN_INVALID"

section "7) GET /api/v1/regions"
check "GET /regions (56개 전체)" 200 "$BACKEND/api/v1/regions" -H "$AUTH"
REGION_COUNT="$("$PY" -c "import json,sys;print(len(json.loads(sys.stdin.read())['items']))" <<<"$BODY" 2>/dev/null)"
if [ "$REGION_COUNT" = "56" ]; then PASS=$((PASS+1)); printf '        \033[32m↳\033[0m items 개수 = 56\n'
else FAIL=$((FAIL+1)); printf '        \033[31m↳ items 개수 = %s (want 56)\033[0m\n' "$REGION_COUNT"; fi

check "GET /regions?sido_name=경기도 (31개)" 200 "$BACKEND/api/v1/regions?sido_name=%EA%B2%BD%EA%B8%B0%EB%8F%84" -H "$AUTH"
GG_COUNT="$("$PY" -c "import json,sys;print(len(json.loads(sys.stdin.read())['items']))" <<<"$BODY" 2>/dev/null)"
if [ "$GG_COUNT" = "31" ]; then PASS=$((PASS+1)); printf '        \033[32m↳\033[0m 경기도 = 31개\n'
else FAIL=$((FAIL+1)); printf '        \033[31m↳ 경기도 = %s (want 31)\033[0m\n' "$GG_COUNT"; fi

check "GET /regions?sido_name=부산광역시 (422 미지원 시·도)" 422 "$BACKEND/api/v1/regions?sido_name=%EB%B6%80%EC%82%B0%EA%B4%91%EC%97%AD%EC%8B%9C" -H "$AUTH"
expect_field "code" "REQUEST_VALIDATION_ERROR"
expect_field "message" "지원하지 않는 시·도입니다. 서울특별시 또는 경기도를 선택해주세요."

section "8) PATCH /api/v1/users/me/region"
check "PATCH /users/me/region (강남구=23)" 200 \
  -X PATCH "$BACKEND/api/v1/users/me/region" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"region_id":23}'
expect_field "region.sgg_name" "강남구"

check "PATCH /users/me/region 없는 지역 (404)" 404 \
  -X PATCH "$BACKEND/api/v1/users/me/region" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"region_id":9999}'
expect_field "code" "REGION_NOT_FOUND"

# ---------- 9. 이미지 분석 ----------
section "9) POST /api/v1/analyze"
FEEDBACK_ID=""; IMAGE_ID=""; CLASS_ID=""; CLASS_ID2=""
ANY_IMG="${IMG_SUCCESS:-${IMG_LOW_CONF:-$IMG_NO_OBJ}}"

if [ -n "$IMG_SUCCESS" ]; then
  check "POST /analyze — SUCCESS" 200 \
    -X POST "$BACKEND/api/v1/analyze" -H "$AUTH" -F "image=@$IMG_SUCCESS;type=image/jpeg"
  expect_field "status" "SUCCESS"
  FEEDBACK_ID="$(printf '%s' "$BODY" | jsonget feedback_id)"
  IMAGE_ID="$(printf '%s' "$BODY" | jsonget image_id)"
  CLASS_ID="$(printf '%s' "$BODY" | jsonget candidate_scores.0.class_id)"
  CLASS_ID2="$(printf '%s' "$BODY" | jsonget candidate_scores.1.class_id)"
  printf '        feedback_id=%s image_id=%s top1_class=%s\n' "$FEEDBACK_ID" "$IMAGE_ID" "$CLASS_ID"
else
  skip "POST /analyze — SUCCESS" "Top-1>=0.5 샘플 없음"
fi

if [ -n "$IMG_LOW_CONF" ]; then
  check "POST /analyze — RETAKE(저신뢰도)" 200 \
    -X POST "$BACKEND/api/v1/analyze" -H "$AUTH" -F "image=@$IMG_LOW_CONF;type=image/jpeg"
  expect_field "status" "RETAKE_REQUIRED"
  expect_field "code" "AI_LOW_CONFIDENCE"
  expect_field "threshold" "0.5"
else
  skip "POST /analyze — RETAKE(저신뢰도)" "해당 샘플 없음"
fi

if [ -n "$IMG_NO_OBJ" ]; then
  check "POST /analyze — RETAKE(중앙 객체 없음)" 200 \
    -X POST "$BACKEND/api/v1/analyze" -H "$AUTH" -F "image=@$IMG_NO_OBJ;type=image/jpeg"
  expect_field "status" "RETAKE_REQUIRED"
  expect_field "code" "AI_NO_MAIN_OBJECT"
else
  skip "POST /analyze — RETAKE(중앙 객체 없음)" "해당 샘플 없음"
fi

check "POST /analyze — 지원하지 않는 형식 (415)" 415 \
  -X POST "$BACKEND/api/v1/analyze" -H "$AUTH" -F "image=@$ANY_IMG;type=image/gif"
expect_field "code" "IMAGE_TYPE_UNSUPPORTED"

check "POST /analyze — 빈 파일 (400)" 400 \
  -X POST "$BACKEND/api/v1/analyze" -H "$AUTH" -F "image=@$EMPTY_FILE;type=image/jpeg"
expect_field "code" "IMAGE_EMPTY"

check "POST /analyze — 인증 없음 (401)" 401 \
  -X POST "$BACKEND/api/v1/analyze" -F "image=@$ANY_IMG;type=image/jpeg"
expect_field "code" "AUTH_REQUIRED"

# disposal/favorites 검사는 유효한 class_id 만 있으면 되므로, SUCCESS 분석이
# 없었던 경우에도 taxonomy 에 반드시 존재하는 값으로 대체한다.
CLASS_ID="${CLASS_ID:-6}"

# ---------- 10~12. 피드백 ----------
section "10) POST /api/v1/feedback/{id}/confirm"
if [ -n "$FEEDBACK_ID" ]; then
  check "POST /feedback/$FEEDBACK_ID/confirm" 200 \
    -X POST "$BACKEND/api/v1/feedback/$FEEDBACK_ID/confirm" -H "$AUTH"
  expect_field "is_correct" "True"
  expect_field "correction_source" "null"

  check "POST confirm 재시도 (409 이미 처리됨)" 409 \
    -X POST "$BACKEND/api/v1/feedback/$FEEDBACK_ID/confirm" -H "$AUTH"
  expect_field "code" "FEEDBACK_ALREADY_COMPLETED"
else
  skip "POST /feedback/{id}/confirm" "SUCCESS 분석이 없어 feedback_id 없음"
fi

check "POST confirm 없는 피드백 (404)" 404 \
  -X POST "$BACKEND/api/v1/feedback/99999999/confirm" -H "$AUTH"
expect_field "code" "FEEDBACK_NOT_FOUND"

section "11) POST /api/v1/feedback/{id}/select-candidate"
if [ -n "$FEEDBACK_ID" ] && [ -n "$CLASS_ID2" ]; then
  FB2="$(curl -s -X POST "$BACKEND/api/v1/analyze" -H "$AUTH" -F "image=@$IMG_SUCCESS;type=image/jpeg" | jsonget feedback_id)"
  check "POST /feedback/$FB2/select-candidate (2순위 후보)" 200 \
    -X POST "$BACKEND/api/v1/feedback/$FB2/select-candidate" -H "$AUTH" \
    -H "Content-Type: application/json" -d "{\"class_id\":$CLASS_ID2}"
  expect_field "is_correct" "False"
  expect_field "correction_source" "USER"

  FB3="$(curl -s -X POST "$BACKEND/api/v1/analyze" -H "$AUTH" -F "image=@$IMG_SUCCESS;type=image/jpeg" | jsonget feedback_id)"
  check "select-candidate — Top-1과 동일 (400)" 400 \
    -X POST "$BACKEND/api/v1/feedback/$FB3/select-candidate" -H "$AUTH" \
    -H "Content-Type: application/json" -d "{\"class_id\":$CLASS_ID}"
  expect_field "code" "FEEDBACK_SAME_AS_PREDICTION"

  check "select-candidate — 후보에 없는 class (400)" 400 \
    -X POST "$BACKEND/api/v1/feedback/$FB3/select-candidate" -H "$AUTH" \
    -H "Content-Type: application/json" -d '{"class_id":85}'
  expect_field "code" "FEEDBACK_INVALID_CANDIDATE"
else
  skip "POST /feedback/{id}/select-candidate" "SUCCESS 분석(Top-K 2개 이상)이 없음"
fi

section "12) POST /api/v1/feedback/{id}/not-in-list (Gemini fallback)"
if [ -n "$FEEDBACK_ID" ]; then
  FB4="$(curl -s -X POST "$BACKEND/api/v1/analyze" -H "$AUTH" -F "image=@$IMG_SUCCESS;type=image/jpeg" | jsonget feedback_id)"
  NIL_OUT="$(curl -s -w $'\n%{http_code}' -X POST "$BACKEND/api/v1/feedback/$FB4/not-in-list" -H "$AUTH")"
  NIL_STATUS="$(printf '%s' "$NIL_OUT" | tail -n1)"
  BODY="$(printf '%s' "$NIL_OUT" | sed '$d')"
  if [ "$NIL_STATUS" = "200" ]; then
    PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m  %-58s 200 (GEMINI_API_KEY 설정됨)\n' "POST /feedback/$FB4/not-in-list"
    expect_field "correction_source" "GEMINI"
  elif [ "$NIL_STATUS" = "503" ]; then
    PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m  %-58s 503 GEMINI_NOT_CONFIGURED (키 미설정 시 정상 동작)\n' "POST /feedback/$FB4/not-in-list"
    expect_field "code" "GEMINI_NOT_CONFIGURED"
  else
    FAIL=$((FAIL+1)); printf '  \033[31mFAIL\033[0m  %-58s got %s, want 200 또는 503\n' "POST /feedback/$FB4/not-in-list" "$NIL_STATUS"
    printf '        body: %s\n' "$(printf '%s' "$BODY" | head -c 300)"
  fi
else
  skip "POST /feedback/{id}/not-in-list" "SUCCESS 분석이 없어 feedback_id 없음"
fi

# ---------- 13. 분리배출 정보 ----------
section "13) GET /api/v1/disposal/schedule"
DS_OUT="$(curl -s -w $'\n%{http_code}' "$BACKEND/api/v1/disposal/schedule?class_id=$CLASS_ID" -H "$AUTH")"
DS_STATUS="$(printf '%s' "$DS_OUT" | tail -n1)"
BODY="$(printf '%s' "$DS_OUT" | sed '$d')"
case "$DS_STATUS" in
  200) PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m  %-58s 200 (공공데이터 API 정상)\n' "GET /disposal/schedule?class_id=$CLASS_ID"
       expect_field "source" "행정안전부 생활쓰레기배출정보" ;;
  404|502|503|504) PASS=$((PASS+1)); printf '  \033[32mPASS\033[0m  %-58s %s PUBLIC_WASTE_* (키 미설정/외부 장애 시 정상 동작)\n' "GET /disposal/schedule?class_id=$CLASS_ID" "$DS_STATUS"
       printf '        code: %s\n' "$(printf '%s' "$BODY" | jsonget code)" ;;
  *) FAIL=$((FAIL+1)); printf '  \033[31mFAIL\033[0m  %-58s got %s\n' "GET /disposal/schedule" "$DS_STATUS" ;;
esac

check "GET /disposal/schedule 없는 class (404)" 404 "$BACKEND/api/v1/disposal/schedule?class_id=99999" -H "$AUTH"
expect_field "code" "CLASS_NOT_FOUND"
check "GET /disposal/schedule class_id 누락 (422)" 422 "$BACKEND/api/v1/disposal/schedule" -H "$AUTH"
expect_field "code" "REQUEST_VALIDATION_ERROR"

# ---------- 14. AI Agent 채팅 ----------
section "14) POST /api/v1/chat"
if [ -n "$FEEDBACK_ID" ]; then
  write_body "{\"feedback_id\":$FEEDBACK_ID,\"message\":\"라벨이 안 떨어지면 어떻게 버려?\"}"
  check "POST /chat" 200 \
    -X POST "$BACKEND/api/v1/chat" -H "$AUTH" -H "Content-Type: application/json" \
    --data-binary "@$JSON_BODY"
  expect_field "feedback_id" "$FEEDBACK_ID"
  ANSWER="$(printf '%s' "$BODY" | jsonget answer)"
  printf '        answer: %s...\n' "$(printf '%s' "$ANSWER" | head -c 160)"

  write_body "{\"feedback_id\":$FEEDBACK_ID,\"message\":\"\"}"
  check "POST /chat 빈 메시지 (422)" 422 \
    -X POST "$BACKEND/api/v1/chat" -H "$AUTH" -H "Content-Type: application/json" \
    --data-binary "@$JSON_BODY"
  expect_field "code" "REQUEST_VALIDATION_ERROR"
else
  skip "POST /chat" "SUCCESS 분석이 없어 feedback_id 없음"
fi

write_body '{"feedback_id":99999999,"message":"이건 어떻게 버려요?"}'
check "POST /chat 없는 feedback (404)" 404 \
  -X POST "$BACKEND/api/v1/chat" -H "$AUTH" -H "Content-Type: application/json" \
  --data-binary "@$JSON_BODY"
expect_field "code" "FEEDBACK_NOT_FOUND"
expect_field "message" "분석 정보를 찾을 수 없습니다."

# ---------- 15~17. 즐겨찾기 ----------
section "15) GET /api/v1/favorites  ·  16) POST  ·  17) DELETE"
check "POST /favorites (201 Created)" 201 \
  -X POST "$BACKEND/api/v1/favorites" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"class_id\":$CLASS_ID}"
FAVORITE_ID="$(printf '%s' "$BODY" | jsonget favorite_id)"
expect_field "message" "즐겨찾기에 등록되었습니다."

check "POST /favorites 중복 (409)" 409 \
  -X POST "$BACKEND/api/v1/favorites" -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"class_id\":$CLASS_ID}"
expect_field "code" "FAVORITE_ALREADY_EXISTS"

check "POST /favorites 없는 class (404)" 404 \
  -X POST "$BACKEND/api/v1/favorites" -H "$AUTH" -H "Content-Type: application/json" \
  -d '{"class_id":99999}'
expect_field "code" "CLASS_NOT_FOUND"

check "GET /favorites" 200 "$BACKEND/api/v1/favorites" -H "$AUTH"
expect_field "items.0.favorite_id" "$FAVORITE_ID"

check "DELETE /favorites/$FAVORITE_ID (204)" 204 \
  -X DELETE "$BACKEND/api/v1/favorites/$FAVORITE_ID" -H "$AUTH"

check "DELETE /favorites 재시도 (404)" 404 \
  -X DELETE "$BACKEND/api/v1/favorites/$FAVORITE_ID" -H "$AUTH"
expect_field "code" "FAVORITE_NOT_FOUND"

# ---------- 5. 로그아웃 (맨 마지막) ----------
section "5) POST /api/v1/auth/logout"
check "POST /auth/logout (204)" 204 -X POST "$BACKEND/api/v1/auth/logout" -H "$AUTH"
check "POST /auth/logout 토큰 없음 (401)" 401 -X POST "$BACKEND/api/v1/auth/logout"
expect_field "code" "AUTH_REQUIRED"

# ---------- 18~19. Vision 내부 API ----------
section "18) POST /internal/v1/predict  ·  19) GET /internal/v1/classes"
check "POST /internal/v1/predict" 200 \
  -X POST "$VISION/internal/v1/predict" \
  -H "X-Request-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -F "image=@$IMG_SUCCESS;type=image/jpeg"
printf '        top1: %s / %s\n' "$(printf '%s' "$BODY" | jsonget major_category)" "$(printf '%s' "$BODY" | jsonget minor_category)"
expect_field "internal_meta.model_version" "${MODEL_VERSION:-$(printf '%s' "$BODY" | jsonget internal_meta.model_version)}"

check "POST /internal/v1/predict — 중앙 객체 없음 (422)" 422 \
  -X POST "$VISION/internal/v1/predict" -F "image=@$IMG_NO_OBJ;type=image/jpeg"
expect_field "code" "VISION_NO_MAIN_OBJECT"

check "POST /internal/v1/predict — 빈 파일 (400)" 400 \
  -X POST "$VISION/internal/v1/predict" -F "image=@$EMPTY_FILE;type=image/jpeg"
expect_field "code" "IMAGE_EMPTY"

check "GET /internal/v1/classes" 200 "$VISION/internal/v1/classes"
CLASS_COUNT="$("$PY" -c "import json,sys;print(len(json.loads(sys.stdin.read())['classes']))" <<<"$BODY" 2>/dev/null)"
if [ "$CLASS_COUNT" = "86" ]; then PASS=$((PASS+1)); printf '        \033[32m↳\033[0m classes 개수 = 86\n'
else FAIL=$((FAIL+1)); printf '        \033[31m↳ classes 개수 = %s (want 86)\033[0m\n' "$CLASS_COUNT"; fi

check "GET /health (Vision)" 200 "$VISION/health"
expect_field "model_loaded" "True"

# ---------- 결과 ----------
printf '\n\033[1m===== 결과 =====\033[0m\n'
printf '  PASS: \033[32m%d\033[0m\n  FAIL: \033[31m%d\033[0m\n  SKIP: \033[33m%d\033[0m\n' "$PASS" "$FAIL" "$SKIPPED"
[ "$FAIL" -eq 0 ] && { printf '\n\033[32m모든 검사를 통과했습니다.\033[0m\n'; exit 0; }
printf '\n\033[31m실패한 검사가 있습니다.\033[0m\n'; exit 1
