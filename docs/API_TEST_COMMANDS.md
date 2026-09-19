# API 테스트 명령어 모음 (19개 전체)

터미널에서 Postman 없이 모든 API를 검증할 수 있는 명령어 모음입니다.
모든 명령어는 실제로 실행해 응답을 확인한 것입니다.

- 전체를 한 번에 자동 검증: [`bash scripts/smoke-test.sh`](../scripts/smoke-test.sh) (100개 검사)
- 아래는 엔드포인트별로 하나씩 실행해 보는 용도입니다.
- 필드 정의·오류 코드 전체 명세는 → [`API_SPEC.md`](API_SPEC.md)

---

## 0. 준비

### 0-1. 서버 2개 기동

```bash
# Git Bash
bash scripts/run-dev.sh
```

```powershell
# PowerShell
.\scripts\run-dev.ps1
```

- Backend: `http://127.0.0.1:8000` · Vision: `http://127.0.0.1:8100`
- Swagger UI: <http://127.0.0.1:8000/docs>
- DB는 항상 `.env`의 MySQL을 사용합니다(SQLite 아님). AWS/외부 키 없이도 나머지
  흐름은 동작합니다 (로컬 디스크 저장).

### 0-2. 환경변수 설정

```bash
# Git Bash
BACKEND=http://127.0.0.1:8000
VISION=http://127.0.0.1:8100
IMG="ai/models/yolo/01_experiment_augmentation/report/final_best/prediction_samples/12_X001_C185_0929_4.jpg"
```

```powershell
# PowerShell
$BACKEND = "http://127.0.0.1:8000"
$VISION  = "http://127.0.0.1:8100"
$IMG     = "ai\models\yolo\01_experiment_augmentation\report\final_best\prediction_samples\12_X001_C185_0929_4.jpg"
```

### 0-3. ⚠️ 셸별 함정 (실제로 겪은 것들)

| 상황                                          | 증상                                      | 해결                                                           |
| --------------------------------------------- | ----------------------------------------- | -------------------------------------------------------------- |
| **PowerShell**에서 `curl`                     | `Invoke-WebRequest` 별칭이라 문법이 다름  | 반드시 **`curl.exe`** 로 호출                                  |
| **Git Bash**에서 `-F "image=@/c/..."`         | `status 000` (연결 실패)                  | `C:/...` 형식 사용 → `$(cygpath -m "$IMG")` 또는 **상대 경로** |
| **Git Bash**에서 `-d '{"message":"한글"}'`    | `400 There was an error parsing the body` | 본문을 **파일로 저장**해 `--data-binary "@body.json"`          |
| **PowerShell**에서 `curl.exe -d "...한글..."` | `422` (필드 깨짐)                         | `Invoke-RestMethod -Body (@{...}\|ConvertTo-Json)` 사용        |
| **PowerShell**에서 응답 한글                  | `ë¶ìë í...` 로 깨져 보임                  | PS 5.1 버그. 아래 UTF-8 디코딩 스니펫 사용                     |

**PowerShell에서 한글 응답 올바르게 보기**

```powershell
function Invoke-Api($Method, $Url, $Headers = @{}, $Body = $null) {
    $p = @{ Uri = $Url; Method = $Method; Headers = $Headers; UseBasicParsing = $true }
    if ($Body) { $p.ContentType = "application/json; charset=utf-8"; $p.Body = $Body }
    $r = Invoke-WebRequest @p
    [Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray()) | ConvertFrom-Json
}
# 사용 예: Invoke-Api GET "$BACKEND/api/v1/users/me" @{Authorization="Bearer $TOKEN"}
```

---

## 1. `GET /health` — Backend liveness (인증 불필요)

```bash
curl -i "$BACKEND/health"
```

```powershell
curl.exe -i "$BACKEND/health"
```

**실제 응답** `200 OK`

```json
{ "status": "ok", "service": "backend" }
```

> 모든 응답에는 `X-Request-ID` 헤더가 항상 포함됩니다 (`-i` 로 확인).

---

## 2. `GET /ready` — Backend/DB readiness (인증 불필요)

```bash
curl -s "$BACKEND/ready"
```

**실제 응답** `200 OK`

```json
{ "status": "ready", "database": true }
```

> DB 연결 실패 시 → `503 SERVICE_NOT_READY`

---

## 3. `POST /api/v1/auth/signup` — 회원가입 (인증 불필요)

```bash
curl -s -X POST "$BACKEND/api/v1/auth/signup" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json" \
  -d '{"email":"test@example.com","password":"Example123!"}'
```

```powershell
$body = @{ email = "test@example.com"; password = "Example123!" } | ConvertTo-Json
Invoke-RestMethod "$BACKEND/api/v1/auth/signup" -Method Post -ContentType "application/json" -Body $body
```

**실제 응답** `201 Created`

```json
{
  "user_id": 1,
  "email": "test@example.com",
  "region": null,
  "created_at": "2026-09-12T14:18:42Z"
}
```

> `region` 은 **회원가입 시 받지 않으므로 항상 null** 입니다 (명세 6.1).

**오류 케이스**

```bash
# 409 AUTH_EMAIL_EXISTS — 같은 요청을 두 번
curl -s -X POST "$BACKEND/api/v1/auth/signup" -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Example123!"}'

# 422 REQUEST_VALIDATION_ERROR — 이메일 형식 오류 + 비밀번호 8자 미만
curl -s -X POST "$BACKEND/api/v1/auth/signup" -H "Content-Type: application/json" \
  -d '{"email":"not-an-email","password":"short"}'
```

```json
{
  "success": false,
  "code": "REQUEST_VALIDATION_ERROR",
  "message": "요청 값이 올바르지 않습니다.",
  "details": [
    {
      "field": "email",
      "message": "value is not a valid email address: An email address must have an @-sign."
    },
    {
      "field": "password",
      "message": "String should have at least 8 characters"
    }
  ],
  "request_id": "0c76a039-f005-43bb-9cdd-3d116e167471"
}
```

---

## 4. `POST /api/v1/auth/login` — 로그인 (인증 불필요)

```bash
curl -s -X POST "$BACKEND/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Example123!"}'

# 토큰을 변수에 저장 (이후 모든 요청에 사용)
TOKEN=$(curl -s -X POST "$BACKEND/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"Example123!"}' \
  | .venv/Scripts/python.exe -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
echo "$TOKEN"
```

```powershell
$body  = @{ email = "test@example.com"; password = "Example123!" } | ConvertTo-Json
$login = Invoke-RestMethod "$BACKEND/api/v1/auth/login" -Method Post -ContentType "application/json" -Body $body
$TOKEN = $login.access_token
$H     = @{ Authorization = "Bearer $TOKEN" }
```

**실제 응답** `200 OK`

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "user": {
    "user_id": 1,
    "email": "test@example.com",
    "region": null,
    "created_at": "2026-09-12T14:18:42Z",
    "updated_at": "2026-09-12T14:18:42Z"
  }
}
```

**오류 케이스**

```bash
# 401 AUTH_INVALID_CREDENTIALS
curl -s -X POST "$BACKEND/api/v1/auth/login" -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"WrongPassword1!"}'
```

> 계정이 없을 때와 비밀번호가 틀릴 때 **동일한 메시지**를 반환합니다(계정 존재 여부 노출 방지).

---

## 5. `POST /api/v1/auth/logout` — 로그아웃 (인증 필요)

```bash
curl -i -X POST "$BACKEND/api/v1/auth/logout" -H "Authorization: Bearer $TOKEN"
```

```powershell
curl.exe -i -X POST "$BACKEND/api/v1/auth/logout" -H "Authorization: Bearer $TOKEN"
```

**실제 응답** `204 No Content` (Body 없음)

**오류 케이스**

```bash
curl -s -X POST "$BACKEND/api/v1/auth/logout"                                   # 401 AUTH_REQUIRED
curl -s -X POST "$BACKEND/api/v1/auth/logout" -H "Authorization: Bearer bad"    # 401 AUTH_TOKEN_INVALID
```

> Stateless JWT 이므로 서버 상태 변경은 없고, Frontend 가 토큰을 삭제합니다.

---

## 6. `GET /api/v1/users/me` — 내 프로필 (인증 필요)

```bash
curl -s "$BACKEND/api/v1/users/me" -H "Authorization: Bearer $TOKEN"
```

```powershell
Invoke-Api GET "$BACKEND/api/v1/users/me" $H
```

**실제 응답** `200 OK`

```json
{
  "user_id": 1,
  "email": "test@example.com",
  "region": {
    "region_id": 23,
    "sido_name": "서울특별시",
    "sgg_name": "강남구"
  },
  "created_at": "2026-09-12T14:18:42Z",
  "updated_at": "2026-09-12T14:19:03Z"
}
```

> 지역 미선택 시 `"region": null`. `password_hash` 는 절대 응답에 포함되지 않습니다.

**오류 케이스**

```bash
curl -s "$BACKEND/api/v1/users/me"                                     # 401 AUTH_REQUIRED
curl -s "$BACKEND/api/v1/users/me" -H "Authorization: Bearer not-a-jwt" # 401 AUTH_TOKEN_INVALID
# 만료 토큰 → 401 AUTH_TOKEN_EXPIRED
```

---

## 7. `GET /api/v1/regions` — 지역 목록 (인증 불필요)

> 지역 Master 는 공개 데이터이고 로그인 전 지역 선택 UI 에서도 필요하므로 토큰을 받지 않습니다.
> 명세 7.2 의 "인증 필요 / 401 AUTH_REQUIRED" 에서 **의도적으로 벗어난 부분**입니다.
> `Authorization` 헤더를 붙여 보내도 무시되므로, 프론트가 만료된 토큰을 그대로 보내도 200 입니다.

```bash
# 전체 56개 (서울 25 + 경기 31) — 토큰 없이
curl -s "$BACKEND/api/v1/regions"

# 시·도 필터 — 한글은 URL 인코딩 권장
curl -s -G "$BACKEND/api/v1/regions" --data-urlencode "sido_name=서울특별시"
curl -s -G "$BACKEND/api/v1/regions" --data-urlencode "sido_name=경기도"
```

```powershell
Invoke-Api GET "$BACKEND/api/v1/regions"
Invoke-Api GET "$BACKEND/api/v1/regions?sido_name=경기도"
```

**실제 응답** `200 OK` (items 56개)

```json
{
  "items": [
    { "region_id": 1, "sido_name": "서울특별시", "sgg_name": "종로구" },
    { "region_id": 23, "sido_name": "서울특별시", "sgg_name": "강남구" },
    { "region_id": 38, "sido_name": "경기도", "sgg_name": "수원시" }
  ]
}
```

**오류 케이스** — 지원하지 않는 시·도

```bash
curl -s -G "$BACKEND/api/v1/regions" --data-urlencode "sido_name=부산광역시"
```

```json
{
  "success": false,
  "code": "REQUEST_VALIDATION_ERROR",
  "message": "지원하지 않는 시·도입니다. 서울특별시 또는 경기도를 선택해주세요.",
  "details": [
    {
      "field": "sido_name",
      "message": "지원하지 않는 시·도입니다. 서울특별시 또는 경기도를 선택해주세요."
    }
  ],
  "request_id": "..."
}
```

---

## 8. `PATCH /api/v1/users/me/region` — 지역 선택/변경 (인증 필요)

```bash
curl -s -X PATCH "$BACKEND/api/v1/users/me/region" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"region_id":23}'
```

```powershell
Invoke-Api PATCH "$BACKEND/api/v1/users/me/region" $H (@{region_id=23}|ConvertTo-Json)
```

**실제 응답** `200 OK`

```json
{
  "user_id": 1,
  "region": { "region_id": 23, "sido_name": "서울특별시", "sgg_name": "강남구" }
}
```

**오류 케이스**

```bash
# 404 REGION_NOT_FOUND — "지원하지 않는 지역입니다."
curl -s -X PATCH "$BACKEND/api/v1/users/me/region" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"region_id":9999}'

# 422 REQUEST_VALIDATION_ERROR — 0 이하/타입 오류
curl -s -X PATCH "$BACKEND/api/v1/users/me/region" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"region_id":0}'
```

---

## 9. `POST /api/v1/analyze` — 이미지 분석 (인증 필요, multipart)

> **전제**: 지역을 먼저 선택해야 합니다(미선택 시 409). `Content-Type` 은 지정하지 말고
> curl/브라우저가 boundary 를 자동 생성하게 둡니다.

### 9-A. SUCCESS (Top-1 ≥ 0.5)

```bash
# Git Bash: 상대 경로 또는 cygpath -m 로 변환한 절대경로를 사용
curl -s -X POST "$BACKEND/api/v1/analyze" \
  -H "Authorization: Bearer $TOKEN" \
  -F "image=@$IMG;type=image/jpeg"
```

```powershell
curl.exe -s -X POST "$BACKEND/api/v1/analyze" -H "Authorization: Bearer $TOKEN" -F "image=@$IMG;type=image/jpeg"
```

**실제 응답** `200 OK`

```json
{
  "status": "SUCCESS",
  "major_category": "고철류",
  "minor_category": "철옷걸이",
  "candidate_scores": [
    { "class_id": 6, "category": "고철류_철옷걸이", "score": 0.6439 },
    { "class_id": 2, "category": "고철류_기타", "score": 0.0521 }
  ],
  "user_region": {
    "region_id": 23,
    "sido_name": "서울특별시",
    "sgg_name": "강남구"
  },
  "disposal_day": null,
  "image_id": 1,
  "feedback_id": 1,
  "warnings": ["PUBLIC_WASTE_UNAVAILABLE"]
}
```

> 공공데이터 API 키가 없으면 **분석은 성공 처리**되고 `disposal_day: null` + `warnings` 에
> 경고 코드가 담깁니다 (명세 15.1). 키를 설정하면 `disposal_day: "화, 목"` 처럼 채워집니다.

**다음 단계에 쓸 값 저장**

```bash
FEEDBACK_ID=1   # 응답의 feedback_id
CLASS_ID=6      # candidate_scores[0].class_id
```

### 9-B. RETAKE_REQUIRED — 신뢰도 부족 (HTTP 200)

```bash
LOW="ai/models/yolo/01_experiment_augmentation/report/final_best/prediction_samples/12_X001_C015_0131_2.jpg"
curl -s -X POST "$BACKEND/api/v1/analyze" -H "Authorization: Bearer $TOKEN" \
  -F "image=@$LOW;type=image/jpeg"
```

**실제 응답** `200 OK` ← 오류가 아닌 정상 비즈니스 분기

```json
{
  "status": "RETAKE_REQUIRED",
  "code": "AI_LOW_CONFIDENCE",
  "message": "분석 신뢰도가 낮습니다. 물체를 중앙에 선명하게 두고 다시 촬영해주세요.",
  "threshold": 0.5,
  "request_id": "..."
}
```

> 이 경로에서는 **S3/DB 에 아무것도 저장하지 않습니다** (feedback_id 없음).

### 9-C. RETAKE_REQUIRED — 중앙 객체 없음 (HTTP 200)

```bash
NOOBJ="ai/models/yolo/01_experiment_augmentation/report/final_best/prediction_samples/12_X002_C973_0319_3.jpg"
curl -s -X POST "$BACKEND/api/v1/analyze" -H "Authorization: Bearer $TOKEN" \
  -F "image=@$NOOBJ;type=image/jpeg"
```

```json
{
  "status": "RETAKE_REQUIRED",
  "code": "AI_NO_MAIN_OBJECT",
  "message": "분류할 물체를 화면 중앙에 위치시킨 뒤 다시 촬영해주세요.",
  "threshold": null,
  "request_id": "..."
}
```

### 9-D. 오류 케이스

```bash
# 401 AUTH_REQUIRED
curl -s -X POST "$BACKEND/api/v1/analyze" -F "image=@$IMG;type=image/jpeg"

# 409 USER_REGION_REQUIRED — "분석 전에 거주 지역을 선택해주세요." (지역 미선택 계정)
# 415 IMAGE_TYPE_UNSUPPORTED
curl -s -X POST "$BACKEND/api/v1/analyze" -H "Authorization: Bearer $TOKEN" \
  -F "image=@$IMG;type=image/gif"

# 400 IMAGE_EMPTY — 0 byte 파일
: > empty.jpg
curl -s -X POST "$BACKEND/api/v1/analyze" -H "Authorization: Bearer $TOKEN" \
  -F "image=@empty.jpg;type=image/jpeg"

# 413 IMAGE_TOO_LARGE — MAX_IMAGE_SIZE_MB 초과
# 422 REQUEST_VALIDATION_ERROR — image 필드 누락
curl -s -X POST "$BACKEND/api/v1/analyze" -H "Authorization: Bearer $TOKEN"
```

> Vision 서버를 끄고 호출하면 `502 VISION_UNAVAILABLE`, 응답이 늦으면 `504 VISION_TIMEOUT` 입니다.

---

## 10. `POST /api/v1/feedback/{feedback_id}/confirm` — "예, 맞아요" (인증 필요)

```bash
curl -s -X POST "$BACKEND/api/v1/feedback/$FEEDBACK_ID/confirm" \
  -H "Authorization: Bearer $TOKEN"
```

```powershell
Invoke-Api POST "$BACKEND/api/v1/feedback/1/confirm" $H
```

**실제 응답** `200 OK`

```json
{
  "feedback_id": 1,
  "is_correct": true,
  "final_class_id": 6,
  "correction_source": null,
  "message": "분석 결과가 맞는 것으로 저장되었습니다."
}
```

**오류 케이스**

```bash
# 409 FEEDBACK_ALREADY_COMPLETED — 같은 요청 재시도
curl -s -X POST "$BACKEND/api/v1/feedback/$FEEDBACK_ID/confirm" -H "Authorization: Bearer $TOKEN"

# 404 FEEDBACK_NOT_FOUND
curl -s -X POST "$BACKEND/api/v1/feedback/99999999/confirm" -H "Authorization: Bearer $TOKEN"

# 403 FEEDBACK_FORBIDDEN — 다른 사용자의 feedback
```

---

## 11. `POST /api/v1/feedback/{feedback_id}/select-candidate` — 다른 후보 선택 (인증 필요)

> 미처리(`is_correct = NULL`) 상태의 feedback 이 필요합니다 → `/analyze` 를 다시 호출해 새 `feedback_id` 를 받으세요.

```bash
curl -s -X POST "$BACKEND/api/v1/feedback/3/select-candidate" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"class_id":2}'
```

```powershell
Invoke-Api POST "$BACKEND/api/v1/feedback/3/select-candidate" $H (@{class_id=2}|ConvertTo-Json)
```

**실제 응답** `200 OK`

```json
{
  "feedback_id": 3,
  "is_correct": false,
  "final_class_id": 2,
  "correction_source": "USER",
  "message": "선택한 객체 후보로 수정되었습니다."
}
```

**오류 케이스**

```bash
# 400 FEEDBACK_SAME_AS_PREDICTION — Top-1 과 같은 class_id
curl -s -X POST "$BACKEND/api/v1/feedback/4/select-candidate" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"class_id":6}'

# 400 FEEDBACK_INVALID_CANDIDATE — 해당 분석의 Top-K 후보에 없는 class_id
curl -s -X POST "$BACKEND/api/v1/feedback/4/select-candidate" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"class_id":16}'
```

---

## 12. `POST /api/v1/feedback/{feedback_id}/not-in-list` — Gemini Fallback (인증 필요)

```bash
curl -s -X POST "$BACKEND/api/v1/feedback/5/not-in-list" \
  -H "Authorization: Bearer $TOKEN"
```

**실제 응답 (GEMINI_API_KEY 미설정)** `503`

```json
{
  "success": false,
  "code": "GEMINI_NOT_CONFIGURED",
  "message": "추가 이미지 분석 서비스가 설정되지 않았습니다.",
  "details": null,
  "request_id": "..."
}
```

**키 설정 시 응답** `200 OK`

```json
{
  "feedback_id": 5,
  "is_correct": false,
  "final_class_id": 0,
  "correction_source": "GEMINI",
  "major_category": "고철류",
  "minor_category": "고철",
  "message": "추가 이미지 분석 결과로 수정되었습니다."
}
```

> 키 설정: `.env` 에 `GEMINI_API_KEY=...` 추가 후 서버 재시작.
> Gemini 결과는 항상 `waste_classes` 의 17개 class_id 중 하나로 제한됩니다.
> 그 외 오류: `502 GEMINI_UNAVAILABLE` / `502 GEMINI_BAD_RESPONSE` / `504 GEMINI_TIMEOUT` / `502 S3_DOWNLOAD_FAILED`

---

## 13. `GET /api/v1/disposal/schedule` — 지역별 분리배출 정보 (인증 필요)

```bash
curl -s "$BACKEND/api/v1/disposal/schedule?class_id=$CLASS_ID" \
  -H "Authorization: Bearer $TOKEN"
```

```powershell
Invoke-Api GET "$BACKEND/api/v1/disposal/schedule?class_id=6" $H
```

**실제 응답 (공공데이터 키 미설정)** `502`

```json
{
  "success": false,
  "code": "PUBLIC_WASTE_UNAVAILABLE",
  "message": "분리배출 정보 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해주세요.",
  "details": null,
  "request_id": "..."
}
```

**키 설정 시 응답** `200 OK`

```json
{
  "class_id": 6,
  "major_category": "고철류",
  "minor_category": "철옷걸이",
  "region": {
    "region_id": 23,
    "sido_name": "서울특별시",
    "sgg_name": "강남구"
  },
  "disposal_day": "화, 목",
  "start_time": "18:00",
  "end_time": "24:00",
  "disposal_method": "지역 기준에 따라 배출합니다.",
  "source": "행정안전부 생활쓰레기배출정보"
}
```

> 키 설정: `.env` 에 `PUBLIC_WASTE_API_SERVICE_KEY=...` (인코딩/디코딩 키 모두 허용).

**오류 케이스**

```bash
curl -s "$BACKEND/api/v1/disposal/schedule?class_id=99999" -H "Authorization: Bearer $TOKEN"  # 404 CLASS_NOT_FOUND
curl -s "$BACKEND/api/v1/disposal/schedule" -H "Authorization: Bearer $TOKEN"                 # 422 REQUEST_VALIDATION_ERROR
# 409 USER_REGION_REQUIRED — "먼저 거주 지역을 선택해주세요." (지역 미선택 계정)
```

---

## 14. `POST /api/v1/chat` — AI Agent 후속 질문 (인증 필요)

> ⚠️ 본문에 한글이 있으므로 **파일로 전달**하세요 (Git Bash 인라인은 400 발생).

```bash
# 1) 본문을 파일로 저장
cat > chat.json <<'EOF'
{"feedback_id": 1, "message": "라벨이 안 떨어지면 어떻게 버려?"}
EOF

# 2) 파일로 전송  (Git Bash 는 cygpath 로 경로 변환)
curl -s -X POST "$BACKEND/api/v1/chat" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  --data-binary "@$(cygpath -m "$PWD/chat.json" 2>/dev/null || echo chat.json)"
```

```powershell
# PowerShell 은 Invoke-RestMethod 가 가장 안전
$body = @{ feedback_id = 1; message = "라벨이 안 떨어지면 어떻게 버려?" } | ConvertTo-Json
Invoke-Api POST "$BACKEND/api/v1/chat" $H $body
```

**실제 응답** `200 OK`

```json
{
  "feedback_id": 1,
  "answer": "분석된 품목은 고철류/철옷걸이입니다. 배출요일 정보를 확인할 수 없습니다. 다른 재질의 부속품(플라스틱 손잡이 등)은 가능한 범위에서 분리해 배출합니다. 자세한 사항은 지역 분리배출 안내를 함께 확인해주세요.",
  "warnings": ["PUBLIC_WASTE_UNAVAILABLE"]
}
```

> `GEMINI_API_KEY` 가 없으면 분석 컨텍스트 + RAG 지식으로 구성한 **결정적 답변**을 반환합니다
> (키가 있으면 Gemini 가 자연어로 생성). 대화 내용은 **DB에 저장하지 않습니다**(Stateless).

**오류 케이스**

```bash
# 404 FEEDBACK_NOT_FOUND — "분석 정보를 찾을 수 없습니다." (feedback API 와 문구가 다름)
echo '{"feedback_id":99999999,"message":"test"}' > c.json
curl -s -X POST "$BACKEND/api/v1/chat" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" --data-binary @c.json

# 422 REQUEST_VALIDATION_ERROR — 빈 메시지 / 1000자 초과
echo '{"feedback_id":1,"message":""}' > c.json
curl -s -X POST "$BACKEND/api/v1/chat" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" --data-binary @c.json

# 403 FEEDBACK_FORBIDDEN — "해당 분석 정보에 접근할 권한이 없습니다."
# 502 AGENT_UNAVAILABLE / 504 AGENT_TIMEOUT — LLM 장애 시
```

---

## 15. `GET /api/v1/favorites` — 즐겨찾기 조회 (인증 필요)

```bash
curl -s "$BACKEND/api/v1/favorites" -H "Authorization: Bearer $TOKEN"
```

**실제 응답** `200 OK`

```json
{
  "items": [
    {
      "favorite_id": 1,
      "class_id": 6,
      "major_category": "고철류",
      "minor_category": "철옷걸이",
      "created_at": "2026-09-12T14:22:10Z"
    }
  ]
}
```

> 다른 사용자의 즐겨찾기는 절대 조회되지 않습니다.

---

## 16. `POST /api/v1/favorites` — 즐겨찾기 등록 (인증 필요)

```bash
curl -s -X POST "$BACKEND/api/v1/favorites" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"class_id":6}'
```

```powershell
Invoke-Api POST "$BACKEND/api/v1/favorites" $H (@{class_id=6}|ConvertTo-Json)
```

**실제 응답** `201 Created`

```json
{
  "favorite_id": 1,
  "class_id": 6,
  "major_category": "고철류",
  "minor_category": "철옷걸이",
  "message": "즐겨찾기에 등록되었습니다."
}
```

**오류 케이스**

```bash
# 409 FAVORITE_ALREADY_EXISTS — 같은 class_id 재등록
curl -s -X POST "$BACKEND/api/v1/favorites" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"class_id":6}'

# 404 CLASS_NOT_FOUND
curl -s -X POST "$BACKEND/api/v1/favorites" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"class_id":99999}'
```

---

## 17. `DELETE /api/v1/favorites/{favorite_id}` — 즐겨찾기 삭제 (인증 필요)

```bash
curl -i -X DELETE "$BACKEND/api/v1/favorites/1" -H "Authorization: Bearer $TOKEN"
```

**실제 응답** `204 No Content` (Body 없음)

**오류 케이스**

```bash
# 404 FAVORITE_NOT_FOUND — 없는 ID 또는 타인 소유(존재 자체를 숨김)
curl -s -X DELETE "$BACKEND/api/v1/favorites/1" -H "Authorization: Bearer $TOKEN"
```

---

## 18. `POST /internal/v1/predict` — YOLO 분석 (Vision 서버, Backend 전용)

> ⚠️ Frontend 에서 직접 호출하지 않습니다. 운영에서는 사설망/접근제어로 보호됩니다.

```bash
curl -s -X POST "$VISION/internal/v1/predict" \
  -H "X-Request-ID: 550e8400-e29b-41d4-a716-446655440000" \
  -H "Accept: application/json" \
  -F "image=@$IMG;type=image/jpeg"
```

```powershell
curl.exe -s -X POST "$VISION/internal/v1/predict" -H "X-Request-ID: 550e8400-e29b-41d4-a716-446655440000" -F "image=@$IMG;type=image/jpeg"
```

**실제 응답** `200 OK`

```json
{
  "major_category": "고철류",
  "minor_category": "철옷걸이",
  "candidate_scores": [
    { "class_id": 6, "category": "고철류_철옷걸이", "score": 0.6439 },
    { "class_id": 2, "category": "고철류_기타", "score": 0.0521 }
  ],
  "internal_meta": {
    "bbox": { "x1": 0.2485, "y1": 0.2534, "x2": 0.8284, "y2": 0.624 },
    "model_version": "B01_yolo_default_baseline_seed42",
    "inference_ms": 42.18
  }
}
```

> `bbox` 는 0~1 정규화 XYXY, `candidate_scores` 는 score 내림차순입니다.

**오류 케이스**

```bash
# 422 VISION_NO_MAIN_OBJECT — Backend 가 200 RETAKE_REQUIRED 로 변환
curl -s -X POST "$VISION/internal/v1/predict" -F "image=@$NOOBJ;type=image/jpeg"

# 400 IMAGE_EMPTY / 400 IMAGE_DECODE_FAILED / 413 IMAGE_TOO_LARGE / 415 IMAGE_TYPE_UNSUPPORTED
: > empty.jpg
curl -s -X POST "$VISION/internal/v1/predict" -F "image=@empty.jpg;type=image/jpeg"

# 503 VISION_MODEL_NOT_READY — 체크포인트 미존재/로드 실패
# 500 VISION_INFERENCE_ERROR — 추론 중 예외
```

---

## 19. `GET /internal/v1/classes` — Vision taxonomy (Backend 전용)

```bash
curl -s "$VISION/internal/v1/classes"

# 개수만 확인 (17개여야 함)
curl -s "$VISION/internal/v1/classes" \
  | .venv/Scripts/python.exe -c "import json,sys;print(len(json.load(sys.stdin)['classes']))"
```

**실제 응답** `200 OK` (classes 17개)

```json
{
  "model_version": "B01_yolo_default_baseline_seed42",
  "classes": [
    { "class_id": 0, "major_category": "고철류", "minor_category": "고철" },
    { "class_id": 1, "major_category": "고철류", "minor_category": "비철금속" },
    { "class_id": 16, "major_category": "형광등", "minor_category": "형광등" }
  ]
}
```

> `class_id` 는 YOLO 클래스 인덱스와 `waste_classes` 테이블이 공유하는 값입니다.

**오류 케이스**: `503 VISION_MODEL_NOT_READY`

---

## 부록 A. Vision 서버 Health

```bash
curl -s "$VISION/health"
```

```json
{
  "status": "ok",
  "model_loaded": true,
  "model_version": "B01_yolo_default_baseline_seed42"
}
```

> 모델 로드 실패 시 `{"status":"ok","model_loaded":false,"model_version":null}`

## 부록 B. 전체 플로우 한 번에 (복사해서 실행)

```bash
BACKEND=http://127.0.0.1:8000
PY=.venv/Scripts/python.exe
EMAIL="flow-$(date +%s)@example.com"
IMG="ai/models/yolo/01_experiment_augmentation/report/final_best/prediction_samples/12_X001_C185_0929_4.jpg"

# 1) 회원가입 + 로그인
curl -s -o /dev/null -X POST "$BACKEND/api/v1/auth/signup" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"Example123!\"}"
TOKEN=$(curl -s -X POST "$BACKEND/api/v1/auth/login" -H "Content-Type: application/json" \
  -d "{\"email\":\"$EMAIL\",\"password\":\"Example123!\"}" \
  | $PY -c "import json,sys;print(json.load(sys.stdin)['access_token'])")

# 2) 지역 선택 (강남구)
curl -s -X PATCH "$BACKEND/api/v1/users/me/region" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"region_id":23}'; echo

# 3) 이미지 분석
RESULT=$(curl -s -X POST "$BACKEND/api/v1/analyze" -H "Authorization: Bearer $TOKEN" \
  -F "image=@$IMG;type=image/jpeg")
echo "$RESULT"
FEEDBACK_ID=$(echo "$RESULT" | $PY -c "import json,sys;print(json.load(sys.stdin)['feedback_id'])")
CLASS_ID=$(echo "$RESULT" | $PY -c "import json,sys;print(json.load(sys.stdin)['candidate_scores'][0]['class_id'])")

# 4) "예, 맞아요" 확정
curl -s -X POST "$BACKEND/api/v1/feedback/$FEEDBACK_ID/confirm" -H "Authorization: Bearer $TOKEN"; echo

# 5) 후속 질문
printf '{"feedback_id":%s,"message":"라벨이 안 떨어지면 어떻게 버려?"}' "$FEEDBACK_ID" > chat.json
curl -s -X POST "$BACKEND/api/v1/chat" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" --data-binary @chat.json; echo

# 6) 즐겨찾기 등록 → 조회 → 삭제
FAV=$(curl -s -X POST "$BACKEND/api/v1/favorites" -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d "{\"class_id\":$CLASS_ID}" \
  | $PY -c "import json,sys;print(json.load(sys.stdin)['favorite_id'])")
curl -s "$BACKEND/api/v1/favorites" -H "Authorization: Bearer $TOKEN"; echo
curl -s -o /dev/null -w "delete -> %{http_code}\n" -X DELETE "$BACKEND/api/v1/favorites/$FAV" \
  -H "Authorization: Bearer $TOKEN"

rm -f chat.json
```

## 부록 C. 오류 상황 재현 가이드 (전체 오류 코드)

모든 오류 응답은 동일한 형태입니다. **모든 응답(성공 포함)에 `X-Request-ID` 헤더**가 붙고,
오류 Body 의 `request_id` 는 그 헤더와 같은 값입니다.

```json
{
  "success": false,
  "code": "<안정적인 오류 코드>",
  "message": "<한국어 메시지>",
  "details": null,
  "request_id": "<X-Request-ID 헤더와 동일>"
}
```

아래 재현 방법은 **모두 실제로 실행해 응답 코드를 확인한 것**입니다.

### C-1. 서버 재시작 없이 재현 (일반 실행 상태에서 바로)

준비: `$BACKEND`, `$TOKEN`, `$IMG` 가 설정되어 있다고 가정합니다 (0번 항목 참고).

```bash
# ── 401 AUTH_REQUIRED ── Authorization 헤더 없음
curl -s $BACKEND/api/v1/users/me

# ── 401 AUTH_TOKEN_INVALID ── 형식이 깨진 토큰
curl -s $BACKEND/api/v1/users/me -H "Authorization: Bearer abc.def.ghi"
# ── 401 AUTH_TOKEN_INVALID ── Bearer 가 아닌 스킴
curl -s $BACKEND/api/v1/users/me -H "Authorization: Basic xyz"

# ── 401 AUTH_INVALID_CREDENTIALS ── 비밀번호 불일치
curl -s -X POST $BACKEND/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"email":"test@example.com","password":"WrongPassword1!"}'

# ── 409 AUTH_EMAIL_EXISTS ── 같은 이메일로 두 번 가입
curl -s -X POST $BACKEND/api/v1/auth/signup -H "Content-Type: application/json" \
  -d '{"email":"dup@example.com","password":"Example123!"}'
curl -s -X POST $BACKEND/api/v1/auth/signup -H "Content-Type: application/json" \
  -d '{"email":"dup@example.com","password":"Example123!"}'

# ── 422 REQUEST_VALIDATION_ERROR ── 형식/길이 위반 (details 배열 확인)
curl -s -X POST $BACKEND/api/v1/auth/signup -H "Content-Type: application/json" \
  -d '{"email":"not-an-email","password":"short"}'

# ── 404 REGION_NOT_FOUND ──
curl -s -X PATCH $BACKEND/api/v1/users/me/region -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"region_id":9999}'

# ── 422 REQUEST_VALIDATION_ERROR ── 지원하지 않는 시·도 (message 가 다름!)
curl -s -G $BACKEND/api/v1/regions --data-urlencode "sido_name=부산광역시"

# ── 404 CLASS_NOT_FOUND ──
curl -s "$BACKEND/api/v1/disposal/schedule?class_id=99999" -H "Authorization: Bearer $TOKEN"
curl -s -X POST $BACKEND/api/v1/favorites -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"class_id":99999}'

# ── 404 FEEDBACK_NOT_FOUND ──
curl -s -X POST $BACKEND/api/v1/feedback/99999999/confirm -H "Authorization: Bearer $TOKEN"

# ── 404 FAVORITE_NOT_FOUND ── 없는 ID 또는 타인 소유
curl -s -X DELETE $BACKEND/api/v1/favorites/99999999 -H "Authorization: Bearer $TOKEN"
```

#### 이미지 관련 오류 4종

```bash
# ── 415 IMAGE_TYPE_UNSUPPORTED ── 허용되지 않는 MIME
curl -s -X POST $BACKEND/api/v1/analyze -H "Authorization: Bearer $TOKEN" \
  -F "image=@$IMG;type=image/gif"

# ── 400 IMAGE_EMPTY ── 0 byte 파일
: > empty.jpg
curl -s -X POST $BACKEND/api/v1/analyze -H "Authorization: Bearer $TOKEN" \
  -F "image=@empty.jpg;type=image/jpeg"

# ── 400 IMAGE_DECODE_FAILED ── MIME 은 맞지만 내용이 이미지가 아님
echo "this is not an image at all" > fake.jpg
curl -s -X POST $BACKEND/api/v1/analyze -H "Authorization: Bearer $TOKEN" \
  -F "image=@fake.jpg;type=image/jpeg"

# ── 413 IMAGE_TOO_LARGE ── MAX_IMAGE_SIZE_MB(기본 10MB) 초과
head -c 11000000 /dev/urandom > big.jpg
curl -s -X POST $BACKEND/api/v1/analyze -H "Authorization: Bearer $TOKEN" \
  -F "image=@big.jpg;type=image/jpeg"

rm -f empty.jpg fake.jpg big.jpg
```

#### 지역 미선택 — 엔드포인트마다 message 가 다릅니다

지역을 선택하지 **않은** 새 계정으로 호출하세요.

```bash
NEW=$(curl -s -X POST $BACKEND/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"email":"no-region@example.com","password":"Example123!"}' \
  | .venv/Scripts/python.exe -c "import json,sys;print(json.load(sys.stdin)['access_token'])")

# 409 USER_REGION_REQUIRED — "분석 전에 거주 지역을 선택해주세요."
curl -s -X POST $BACKEND/api/v1/analyze -H "Authorization: Bearer $NEW" -F "image=@$IMG;type=image/jpeg"

# 409 USER_REGION_REQUIRED — "먼저 거주 지역을 선택해주세요."   ← 문구가 다름
curl -s "$BACKEND/api/v1/disposal/schedule?class_id=6" -H "Authorization: Bearer $NEW"
```

#### 피드백 상태/소유권 오류

```bash
# 409 FEEDBACK_ALREADY_COMPLETED ── confirm 을 두 번
curl -s -X POST $BACKEND/api/v1/feedback/$FEEDBACK_ID/confirm -H "Authorization: Bearer $TOKEN"
curl -s -X POST $BACKEND/api/v1/feedback/$FEEDBACK_ID/confirm -H "Authorization: Bearer $TOKEN"

# 400 FEEDBACK_SAME_AS_PREDICTION ── Top-1 과 같은 class_id 선택
curl -s -X POST $BACKEND/api/v1/feedback/$NEW_FB/select-candidate -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d "{\"class_id\":$CLASS_ID}"

# 400 FEEDBACK_INVALID_CANDIDATE ── 그 분석의 Top-K 에 없는 class_id
curl -s -X POST $BACKEND/api/v1/feedback/$NEW_FB/select-candidate -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" -d '{"class_id":16}'

# 403 FEEDBACK_FORBIDDEN ── 다른 계정의 feedback 에 접근
OTHER=$(curl -s -X POST $BACKEND/api/v1/auth/login -H "Content-Type: application/json" \
  -d '{"email":"other@example.com","password":"Example123!"}' \
  | .venv/Scripts/python.exe -c "import json,sys;print(json.load(sys.stdin)['access_token'])")
curl -s -X POST $BACKEND/api/v1/feedback/$FEEDBACK_ID/confirm -H "Authorization: Bearer $OTHER"
```

> `/api/v1/chat` 의 403/404 는 **문구가 다릅니다**
> (`"해당 분석 정보에 접근할 권한이 없습니다."` / `"분석 정보를 찾을 수 없습니다."`).

#### 데이터를 조작해 재현하는 2가지

```bash
# ── 502 S3_DOWNLOAD_FAILED ── 저장된 원본을 지운 뒤 not-in-list 호출
#    (개발 모드 STORAGE_BACKEND=local 기준)
find .local_storage -name "*.jpg" -delete
curl -s -X POST $BACKEND/api/v1/feedback/$FEEDBACK_ID/not-in-list -H "Authorization: Bearer $TOKEN"

# ── 404 USER_NOT_FOUND ── 토큰은 유효하지만 사용자 행이 사라진 경우
.venv/Scripts/python.exe -c "
import sqlite3; c=sqlite3.connect('backend/dev.sqlite3')
c.execute(\"DELETE FROM users WHERE email='test@example.com'\"); c.commit()"
curl -s $BACKEND/api/v1/users/me -H "Authorization: Bearer $TOKEN"
```

### C-2. 서버 설정을 바꿔 재현 (외부 연동 장애 시뮬레이션)

각 항목은 **해당 환경변수로 Backend 를 재기동**한 뒤 요청하면 재현됩니다.
`backend/` 디렉터리에서 실행하세요.

> 아래 `run_with`는 실제 MySQL(Railway)과 무관한 **일회용 SQLite 인스턴스**를
> 띄웁니다. 고의로 데이터를 지우거나(`DELETE FROM users`) `DATABASE_URL`을
> 깨뜨려 오류를 재현하는 용도라, 실제 공유 MySQL 데이터를 건드리지 않으려고
> 의도적으로 분리해 둔 것입니다. 앱의 일반 개발/운영 DB는 항상 MySQL만
> 사용합니다.

```bash
cd backend
run_with() {  # 예: run_with "VISION_REQUEST_TIMEOUT_SECONDS=0.001"
  env DATABASE_URL="sqlite:///./dev.sqlite3" \
      JWT_SECRET_KEY="dev-only-insecure-secret-please-change-me-32bytes+" \
      STORAGE_BACKEND=local LOCAL_STORAGE_DIR="../.local_storage" \
      VISION_SERVER_BASE_URL="http://127.0.0.1:8100/internal/v1" \
      AUTO_CREATE_TABLES=true AUTO_SEED_MASTER_DATA=true \
      $1 ../.venv/Scripts/python.exe -m uvicorn main:app --port 8000
}
```

| 재현할 오류                      | 실행 환경변수                                                                                                     | 확인 요청                           |
| -------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------- |
| **401 AUTH_TOKEN_EXPIRED**       | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=-1`                                                                              | 로그인 후 그 토큰으로 아무 인증 API |
| **502 VISION_UNAVAILABLE**       | `VISION_SERVER_BASE_URL=http://127.0.0.1:9999/internal/v1`                                                        | `POST /analyze`                     |
| **504 VISION_TIMEOUT**           | `VISION_REQUEST_TIMEOUT_SECONDS=0.001`                                                                            | `POST /analyze`                     |
| **502 VISION_BAD_RESPONSE**      | `VISION_SERVER_BASE_URL=http://127.0.0.1:8000` (스키마가 다른 서버)                                               | `POST /analyze`                     |
| **502 S3_UPLOAD_FAILED**         | `STORAGE_BACKEND=s3 AWS_ACCESS_KEY_ID=AKIAINVALID AWS_SECRET_ACCESS_KEY=invalid AWS_S3_BUCKET=no-such-bucket-xyz` | `POST /analyze`                     |
| **502 GEMINI_UNAVAILABLE**       | `GEMINI_API_KEY=invalid-key-for-testing`                                                                          | `POST /feedback/{id}/not-in-list`   |
| **503 GEMINI_NOT_CONFIGURED**    | `GEMINI_API_KEY=` (비움)                                                                                          | `POST /feedback/{id}/not-in-list`   |
| **504 GEMINI_TIMEOUT**           | 유효한 키 + `GEMINI_VISION_TIMEOUT_SECONDS=0.001`                                                                 | `POST /feedback/{id}/not-in-list`   |
| **502 PUBLIC_WASTE_AUTH_ERROR**  | `PUBLIC_WASTE_API_SERVICE_KEY=invalid-service-key`                                                                | `GET /disposal/schedule?class_id=6` |
| **502 PUBLIC_WASTE_UNAVAILABLE** | `PUBLIC_WASTE_API_SERVICE_KEY=` (비움)                                                                            | `GET /disposal/schedule?class_id=6` |
| **504 PUBLIC_WASTE_TIMEOUT**     | 유효한 키 + `PUBLIC_WASTE_API_TIMEOUT_SECONDS=0.001`                                                              | `GET /disposal/schedule?class_id=6` |
| **503 DATABASE_ERROR**           | `DATABASE_URL=mysql+pymysql://bad:bad@127.0.0.1:3399/nope AUTO_CREATE_TABLES=false AUTO_SEED_MASTER_DATA=false`   | 아무 DB 사용 API (`signup` 등)      |
| **503 SERVICE_NOT_READY**        | 위와 동일                                                                                                         | `GET /ready`                        |
| **502 AGENT_UNAVAILABLE**        | `GEMINI_API_KEY=invalid-key-for-testing`                                                                          | `POST /chat`                        |
| **504 AGENT_TIMEOUT**            | 유효한 키 + `GEMINI_CHAT_TIMEOUT_SECONDS=0.001`                                                                   | `POST /chat`                        |

실행 예시 — Vision 서버 장애:

```bash
# 터미널 1: Vision 을 끈 채로 Backend 만 기동
cd backend
env DATABASE_URL="sqlite:///./dev.sqlite3" JWT_SECRET_KEY="dev-only-insecure-secret-32bytes+" \
    STORAGE_BACKEND=local VISION_SERVER_BASE_URL="http://127.0.0.1:9999/internal/v1" \
    AUTO_CREATE_TABLES=true AUTO_SEED_MASTER_DATA=true \
    ../.venv/Scripts/python.exe -m uvicorn main:app --port 8000

# 터미널 2
curl -s -X POST $BACKEND/api/v1/analyze -H "Authorization: Bearer $TOKEN" -F "image=@$IMG;type=image/jpeg"
```

```json
{
  "success": false,
  "code": "VISION_UNAVAILABLE",
  "message": "이미지 분석 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요.",
  "details": null,
  "request_id": "..."
}
```

> **중요**: Vision/Gemini/공공데이터 장애는 **Backend 전체 장애로 번지지 않습니다**(SR-27).
> `/health` 는 계속 200 이고, 공공데이터 장애 시 `/analyze` 는 **성공(200)** 하면서
> `disposal_day: null` + `warnings: ["PUBLIC_WASTE_UNAVAILABLE"]` 로만 알려줍니다.

### C-3. Vision 서버 오류 재현

```bash
# ── 422 VISION_NO_MAIN_OBJECT ── 중앙에 뚜렷한 객체가 없는 이미지
curl -s -X POST $VISION/internal/v1/predict \
  -F "image=@ai/models/yolo/01_experiment_augmentation/report/final_best/prediction_samples/12_X002_C973_0319_3.jpg;type=image/jpeg"

# ── 400 IMAGE_EMPTY / 400 IMAGE_DECODE_FAILED / 413 / 415 ── Backend 와 동일
: > empty.jpg
curl -s -X POST $VISION/internal/v1/predict -F "image=@empty.jpg;type=image/jpeg"

# ── 503 VISION_MODEL_NOT_READY ── 존재하지 않는 체크포인트로 기동
MODEL_PATH=weights/does-not-exist.pt \
  .venv/Scripts/python.exe -m uvicorn vision.main:app --port 8101
curl -s -X POST http://127.0.0.1:8101/internal/v1/predict -F "image=@$IMG;type=image/jpeg"
curl -s http://127.0.0.1:8101/internal/v1/classes
curl -s http://127.0.0.1:8101/health   # {"status":"ok","model_loaded":false,"model_version":null}
```

> `500 VISION_INFERENCE_ERROR` 는 추론 중 예기치 못한 예외에 대한 안전망이라 정상 상태에서는
> 인위적으로 만들기 어렵습니다. 동작은 `vision/tests/test_api.py` 에서 검증합니다.

### C-4. 오류 코드 ↔ 재현 방법 요약

| HTTP | code                          | 재현 방법                                                               |
| ---- | ----------------------------- | ----------------------------------------------------------------------- |
| 400  | `IMAGE_EMPTY`                 | 0 byte 파일 업로드                                                      |
| 400  | `IMAGE_DECODE_FAILED`         | 이미지가 아닌 내용을 `type=image/jpeg` 로 업로드                        |
| 400  | `FEEDBACK_INVALID_CANDIDATE`  | Top-K 에 없는 `class_id` 로 select-candidate                            |
| 400  | `FEEDBACK_SAME_AS_PREDICTION` | Top-1 과 같은 `class_id` 로 select-candidate                            |
| 401  | `AUTH_REQUIRED`               | Authorization 헤더 생략                                                 |
| 401  | `AUTH_INVALID_CREDENTIALS`    | 잘못된 비밀번호로 로그인                                                |
| 401  | `AUTH_TOKEN_INVALID`          | 깨진 토큰 / Bearer 아닌 스킴                                            |
| 401  | `AUTH_TOKEN_EXPIRED`          | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES=-1` 로 기동 후 로그인                  |
| 403  | `FEEDBACK_FORBIDDEN`          | 다른 계정의 feedback_id 로 요청                                         |
| 404  | `USER_NOT_FOUND`              | 토큰 유효 + DB 에서 사용자 행 삭제                                      |
| 404  | `REGION_NOT_FOUND`            | `region_id: 9999`                                                       |
| 404  | `CLASS_NOT_FOUND`             | `class_id: 99999`                                                       |
| 404  | `FEEDBACK_NOT_FOUND`          | 없는 feedback_id                                                        |
| 404  | `FAVORITE_NOT_FOUND`          | 없는/타인 소유 favorite_id                                              |
| 404  | `PUBLIC_WASTE_NOT_FOUND`      | 유효한 키 + 데이터 없는 지역 조회                                       |
| 409  | `AUTH_EMAIL_EXISTS`           | 같은 이메일 재가입                                                      |
| 409  | `USER_REGION_REQUIRED`        | 지역 미선택 계정으로 analyze/disposal                                   |
| 409  | `FEEDBACK_ALREADY_COMPLETED`  | 이미 확정된 feedback 재처리                                             |
| 409  | `FAVORITE_ALREADY_EXISTS`     | 같은 class_id 재등록                                                    |
| 413  | `IMAGE_TOO_LARGE`             | `MAX_IMAGE_SIZE_MB` 초과 파일                                           |
| 415  | `IMAGE_TYPE_UNSUPPORTED`      | `type=image/gif` 등                                                     |
| 422  | `REQUEST_VALIDATION_ERROR`    | 필드 누락/형식 오류/길이 초과/미지원 시·도                              |
| 502  | `VISION_UNAVAILABLE`          | Vision 서버 중지 또는 잘못된 URL                                        |
| 502  | `VISION_BAD_RESPONSE`         | Vision URL 을 스키마가 다른 서버로                                      |
| 502  | `S3_UPLOAD_FAILED`            | 잘못된 AWS 자격증명                                                     |
| 502  | `S3_DOWNLOAD_FAILED`          | 저장된 원본 파일 삭제 후 not-in-list                                    |
| 502  | `PUBLIC_WASTE_UNAVAILABLE`    | 공공데이터 키 비움                                                      |
| 502  | `PUBLIC_WASTE_AUTH_ERROR`     | 잘못된 공공데이터 키                                                    |
| 502  | `GEMINI_UNAVAILABLE`          | 잘못된 Gemini 키                                                        |
| 502  | `GEMINI_BAD_RESPONSE`         | Gemini 가 허용 class 밖의 값 반환 (테스트로 검증)                       |
| 502  | `AGENT_UNAVAILABLE`           | 잘못된 Gemini 키 + `/chat`                                              |
| 503  | `DATABASE_ERROR`              | DB 주소를 없는 곳으로                                                   |
| 503  | `SERVICE_NOT_READY`           | DB 다운 상태에서 `/ready`                                               |
| 503  | `GEMINI_NOT_CONFIGURED`       | `GEMINI_API_KEY` 비움                                                   |
| 503  | `VISION_MODEL_NOT_READY`      | 없는 체크포인트 경로로 Vision 기동                                      |
| 503  | `PUBLIC_WASTE_RATE_LIMITED`   | 공공데이터 일일 호출 한도 초과 시                                       |
| 504  | `VISION_TIMEOUT`              | `VISION_REQUEST_TIMEOUT_SECONDS=0.001`                                  |
| 504  | `S3_TIMEOUT`                  | S3 연결 타임아웃                                                        |
| 504  | `PUBLIC_WASTE_TIMEOUT`        | `PUBLIC_WASTE_API_TIMEOUT_SECONDS=0.001`                                |
| 504  | `GEMINI_TIMEOUT`              | `GEMINI_VISION_TIMEOUT_SECONDS=0.001`                                   |
| 504  | `AGENT_TIMEOUT`               | `GEMINI_CHAT_TIMEOUT_SECONDS=0.001`                                     |
| 500  | `INTERNAL_SERVER_ERROR`       | 예상치 못한 예외 (안전망)                                               |
| 422  | `VISION_NO_MAIN_OBJECT`       | (Vision) 중앙 객체 없는 이미지 → Backend 는 200 RETAKE_REQUIRED 로 변환 |
| 500  | `VISION_INFERENCE_ERROR`      | (Vision) 추론 중 예외 (안전망)                                          |

### C-5. 자동 검증

위 오류 동작은 자동 테스트로도 검증됩니다.

```bash
cd backend && ../.venv/Scripts/python.exe -m pytest tests/ -q   # 104개
.venv/Scripts/python.exe -m pytest vision/tests -q              # 24개
bash scripts/smoke-test.sh                                      # 실서버 100개 검사
```
