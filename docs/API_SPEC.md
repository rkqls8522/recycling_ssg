# recycling_ssg API 명세서

**버전** v6.1 · **기준일** 2026-09-14 · **작성 기준** 구현 코드(`backend/`, `vision/`)에서 직접 추출

> 이 문서는 `recycling_ssg_API_상세명세서_v6.0.pdf`(설계 명세)를 **실제 구현 기준으로 갱신**한 것입니다.
> 설계 명세와 구현이 다른 부분은 [21. v6.0 설계 명세와의 차이](#21-v60-설계-명세와의-차이)에 모두 정리했습니다.
> 실행 가능한 요청 예시는 [`API_TEST_COMMANDS.md`](API_TEST_COMMANDS.md)를 참고하세요.

---

## 1. 시스템 구성

| 서버 | 역할 | 기본 주소 | 노출 대상 |
| --- | --- | --- | --- |
| **Backend** | 인증·비즈니스 로직·DB·외부 연동 | `http://127.0.0.1:8000` | Frontend |
| **Vision** | YOLO 중앙 객체 탐지 + Top-K 후보 | `http://127.0.0.1:8100` | **Backend 전용** (운영에서는 사설망) |

외부 의존성 3종은 모두 **선택적**입니다. 없어도 서비스는 동작하며, 실패는 해당 기능에 국한됩니다.

| 외부 | 용도 | 없을 때 |
| --- | --- | --- |
| AWS S3 | 분석 이미지 원본 저장 | `STORAGE_BACKEND=local` 로 로컬 디스크 사용 |
| 행정안전부 생활쓰레기배출정보 API | 지역별 배출요일 | `/analyze` 는 성공 + `warnings`, `/disposal/schedule` 은 5xx |
| Google Gemini | not-in-list 재분석 · Chat 자연어 생성 | not-in-list 는 503, Chat 은 결정적(RAG) 답변으로 대체 |

---

## 2. 공통 규약

### 2.1 Base URL / 버전

- Backend 공개 API: `/api/v1/*`
- Backend 헬스체크: `/health`, `/ready` (버전 접두사 없음)
- Vision 내부 API: `/internal/v1/*`

### 2.2 인증

JWT Bearer 토큰. `POST /api/v1/auth/login` 이 발급합니다.

```http
Authorization: Bearer <access_token>
```

| 항목 | 값 |
| --- | --- |
| 알고리즘 | `HS256` (`JWT_ALGORITHM`) |
| 만료 | 기본 1440분 = 24시간 (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`) |
| Payload | `sub`(user_id 문자열), `iat`, `exp` |
| 로그아웃 | Stateless — 서버는 무효화하지 않고 **Frontend 가 토큰을 폐기**합니다 |

인증 실패는 3가지로 구분됩니다.

| 상황 | HTTP | code |
| --- | --- | --- |
| `Authorization` 헤더 자체가 없음 | 401 | `AUTH_REQUIRED` |
| `Bearer ` 스킴이 아니거나 토큰이 깨짐 | 401 | `AUTH_TOKEN_INVALID` |
| 서명은 맞지만 `exp` 경과 | 401 | `AUTH_TOKEN_EXPIRED` |
| 토큰은 유효하지만 사용자 행이 없음 | 404 | `USER_NOT_FOUND` |

### 2.3 X-Request-ID

**모든 응답(성공·실패 무관)** 에 `X-Request-ID` 헤더가 붙습니다.
Frontend 가 요청에 넣어 보내면 그 값이 그대로 되돌아오고, 생략하면 Backend 가 UUIDv4 를 생성합니다.
오류 Body 의 `request_id` 는 항상 이 헤더와 같은 값이며, Backend → Vision 호출에도 전달됩니다.

### 2.4 날짜·시간 형식

모든 Datetime 응답은 **UTC 고정 + `Z` 접미사**: `2026-09-11T09:00:00Z`

### 2.5 오류 응답 (공통)

모든 오류는 예외 없이 아래 5개 필드를 갖습니다. `details` 는 값이 없어도 **키가 생략되지 않고 `null`** 로 나갑니다.

```json
{
  "success": false,
  "code": "USER_REGION_REQUIRED",
  "message": "분석 전에 거주 지역을 선택해주세요.",
  "details": null,
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

| 필드 | 타입 | Nullable | 설명 |
| --- | --- | --- | --- |
| `success` | Boolean | No | 오류 응답에서는 항상 `false` |
| `code` | String | No | 안정적인 오류 코드. **Frontend 분기는 이 값으로** |
| `message` | String | No | 사용자에게 그대로 보여줄 수 있는 한국어 문구 |
| `details` | Array \| null | Yes | `REQUEST_VALIDATION_ERROR` 일 때만 `[{field, message}]` |
| `request_id` | UUID String | No | `X-Request-ID` 헤더와 동일 |

`422 REQUEST_VALIDATION_ERROR` 의 `details` 예시:

```json
{
  "success": false,
  "code": "REQUEST_VALIDATION_ERROR",
  "message": "요청 값이 올바르지 않습니다.",
  "details": [
    { "field": "email", "message": "value is not a valid email address: An email address must have an @-sign." },
    { "field": "password", "message": "String should have at least 8 characters" }
  ],
  "request_id": "0c76a039-f005-43bb-9cdd-3d116e167471"
}
```

### 2.6 CORS

`CORS_ALLOW_ORIGINS` (기본 `http://localhost:5173,http://localhost:3000`) 에 나열된 Origin 만 허용하며,
`X-Request-ID` 를 `expose_headers` 로 공개하므로 브라우저 JS 에서 읽을 수 있습니다.

### 2.7 공통 객체

**Region**

| 필드 | 타입 | Nullable | 예시 |
| --- | --- | --- | --- |
| `region_id` | Integer | No | `23` (1~56) |
| `sido_name` | String | No | `서울특별시` \| `경기도` |
| `sgg_name` | String | No | `강남구` |

**CandidateScore**

| 필드 | 타입 | Nullable | 예시 |
| --- | --- | --- | --- |
| `class_id` | Integer | No | `1` (0~16) |
| `category` | String | No | `고철류_비철금속` (`대분류_소분류`) |
| `score` | Number | No | `0.0003` (0~1) |

---

## 3. 엔드포인트 요약 (19개)

| # | Method | Endpoint | 인증 | 성공 | 기능 |
| --- | --- | --- | --- | --- | --- |
| 1 | GET | `/health` | ✗ | 200 | Backend liveness |
| 2 | GET | `/ready` | ✗ | 200 | DB 포함 readiness |
| 3 | POST | `/api/v1/auth/signup` | ✗ | 201 | 회원가입 (지역은 받지 않음) |
| 4 | POST | `/api/v1/auth/login` | ✗ | 200 | 로그인 → JWT 발급 |
| 5 | POST | `/api/v1/auth/logout` | ✓ | 204 | 로그아웃 |
| 6 | GET | `/api/v1/users/me` | ✓ | 200 | 내 프로필 |
| 7 | GET | `/api/v1/regions` | **✗** | 200 | 지원 지역 56개 |
| 8 | PATCH | `/api/v1/users/me/region` | ✓ | 200 | 지역 선택/변경 |
| 9 | POST | `/api/v1/analyze` | ✓ | 200 | 이미지 분석 |
| 10 | POST | `/api/v1/feedback/{feedback_id}/confirm` | ✓ | 200 | "예, 맞아요" |
| 11 | POST | `/api/v1/feedback/{feedback_id}/select-candidate` | ✓ | 200 | 다른 후보 선택 |
| 12 | POST | `/api/v1/feedback/{feedback_id}/not-in-list` | ✓ | 200 | Gemini 재분석 |
| 13 | GET | `/api/v1/disposal/schedule` | ✓ | 200 | 지역별 분리배출 정보 |
| 14 | POST | `/api/v1/chat` | ✓ | 200 | AI 후속 질문 (Stateless) |
| 15 | GET | `/api/v1/favorites` | ✓ | 200 | 즐겨찾기 목록 |
| 16 | POST | `/api/v1/favorites` | ✓ | 201 | 즐겨찾기 등록 |
| 17 | DELETE | `/api/v1/favorites/{favorite_id}` | ✓ | 204 | 즐겨찾기 삭제 |
| 18 | POST | `/internal/v1/predict` | ✗(내부) | 200 | YOLO 분석 — **Backend 전용** |
| 19 | GET | `/internal/v1/classes` | ✗(내부) | 200 | 모델 taxonomy — **Backend 전용** |

> **7번만 인증이 없습니다.** 지역 Master 는 공개 데이터이고 로그인 전 지역 선택 UI 에서도 필요하기 때문입니다.
> `Authorization` 헤더를 붙여 보내도 무시되므로, 만료된 토큰을 그대로 보내도 200 입니다.

---

## 4. GET /health — Backend liveness (인증 불필요)

DB 를 건드리지 않는 프로세스 생존 확인용. 외부 연동 장애와 무관하게 항상 200 입니다.

**응답 200**

| 필드 | 타입 | Nullable | 값 |
| --- | --- | --- | --- |
| `status` | String | No | `ok` |
| `service` | String | No | `backend` |

```json
{ "status": "ok", "service": "backend" }
```

---

## 5. GET /ready — Backend/DB readiness (인증 불필요)

DB 연결까지 확인합니다. 로드밸런서/오케스트레이터의 readiness probe 용도입니다.

**응답 200**

| 필드 | 타입 | Nullable | 값 |
| --- | --- | --- | --- |
| `status` | String | No | `ready` |
| `database` | Boolean | No | `true` |

**오류**

| HTTP | code | message | 조건 |
| --- | --- | --- | --- |
| 503 | `SERVICE_NOT_READY` | 서비스 준비가 완료되지 않았습니다. | DB 연결 실패 |

---

## 6. POST /api/v1/auth/signup — 회원가입 (인증 불필요)

**요청 Body** (`application/json`)

| 필드 | 타입 | 필수 | 제약 | 설명 |
| --- | --- | --- | --- | --- |
| `email` | String | 필수 | 이메일 형식, 최대 255자 | 중복 불가 |
| `password` | String | 필수 | 8자 이상, **UTF-8 기준 72바이트 이하** | bcrypt 해시로 저장 |

> 72바이트 제한은 bcrypt 가 그 이상을 **조용히 잘라내기** 때문에, 잘라내는 대신 거절하도록 만든 제약입니다.

**응답 201**

| 필드 | 타입 | Nullable | 설명 |
| --- | --- | --- | --- |
| `user_id` | Integer | No | `users.user_id` |
| `email` | String | No | 가입 이메일 |
| `region` | Region \| null | Yes | **항상 `null`** — 회원가입에서 지역을 받지 않음 |
| `created_at` | Datetime | No | `2026-09-12T14:18:42Z` |

```json
{ "user_id": 1, "email": "test@example.com", "region": null, "created_at": "2026-09-12T14:18:42Z" }
```

**오류**

| HTTP | code | message | 조건 |
| --- | --- | --- | --- |
| 409 | `AUTH_EMAIL_EXISTS` | 이미 가입된 이메일입니다. | 이메일 중복 (사전 조회 + UNIQUE 제약 양쪽에서) |
| 422 | `REQUEST_VALIDATION_ERROR` | 요청 값이 올바르지 않습니다. | 이메일 형식 오류, 비밀번호 길이 미달/초과 |
| 503 | `DATABASE_ERROR` | 데이터베이스 처리 중 오류가 발생했습니다. | DB 연결/INSERT 실패 |

**Side Effect** — `users` 1건 INSERT (`region_id` 는 NULL). 평문 비밀번호는 저장하지 않습니다.

---

## 7. POST /api/v1/auth/login — 로그인 (인증 불필요)

**요청 Body**

| 필드 | 타입 | 필수 | 제약 |
| --- | --- | --- | --- |
| `email` | String | 필수 | 이메일 형식 |
| `password` | String | 필수 | 1~72자 |

**응답 200**

| 필드 | 타입 | Nullable | 설명 |
| --- | --- | --- | --- |
| `access_token` | String | No | JWT |
| `token_type` | String | No | `bearer` |
| `user` | UserProfile | No | `user_id`, `email`, `region`, `created_at`, `updated_at` |

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

> **로그인 직후 분기 기준**: `user.region` 이 `null` 이면 지역 선택 화면으로, 아니면 홈으로 보냅니다.

**오류**

| HTTP | code | message | 조건 |
| --- | --- | --- | --- |
| 401 | `AUTH_INVALID_CREDENTIALS` | 이메일 또는 비밀번호가 올바르지 않습니다. | 계정 없음 **또는** 비밀번호 불일치 |
| 422 | `REQUEST_VALIDATION_ERROR` | 요청 값이 올바르지 않습니다. | 형식 오류 |
| 503 | `DATABASE_ERROR` | 데이터베이스 처리 중 오류가 발생했습니다. | DB 조회 실패 |

> 계정이 없을 때와 비밀번호가 틀릴 때 **동일한 코드·문구**를 반환합니다(계정 존재 여부 노출 방지).

---

## 8. POST /api/v1/auth/logout — 로그아웃 (인증 필요)

Stateless JWT 이므로 서버 상태 변경이 없습니다. 토큰 유효성만 검증하고 `204 No Content` (Body 없음)를 반환합니다.

**오류**: `401 AUTH_REQUIRED` / `401 AUTH_TOKEN_INVALID` / `401 AUTH_TOKEN_EXPIRED` / `404 USER_NOT_FOUND`

---

## 9. GET /api/v1/users/me — 내 프로필 (인증 필요)

**응답 200**

| 필드 | 타입 | Nullable | 설명 |
| --- | --- | --- | --- |
| `user_id` | Integer | No | |
| `email` | String | No | |
| `region` | Region \| null | Yes | `users.region_id` JOIN. **미선택이면 `null`** |
| `created_at` | Datetime | No | |
| `updated_at` | Datetime | No | |

`password_hash` 는 어떤 응답에도 포함되지 않습니다.

**오류**: `401 AUTH_REQUIRED` / `401 AUTH_TOKEN_INVALID` / `401 AUTH_TOKEN_EXPIRED` / `404 USER_NOT_FOUND` / `503 DATABASE_ERROR`

---

## 10. GET /api/v1/regions — 지역 목록 (**인증 불필요**)

지역 선택 UI 에 채울 지원 지역 Master 를 반환합니다. 서울특별시 25개 자치구 + 경기도 31개 시·군 = **56개**.

**Query Parameter**

| 필드 | 타입 | 필수 | 허용값 | 설명 |
| --- | --- | --- | --- | --- |
| `sido_name` | String | 선택 | `서울특별시` \| `경기도` | 생략하면 56개 전체. 한글이므로 URL 인코딩 권장 |

**응답 200**

| 필드 | 타입 | Nullable | 설명 |
| --- | --- | --- | --- |
| `items` | Array\<Region\> | No | `region_id` 오름차순. 최대 56개 |

```json
{
  "items": [
    { "region_id": 1, "sido_name": "서울특별시", "sgg_name": "종로구" },
    { "region_id": 38, "sido_name": "경기도", "sgg_name": "수원시" }
  ]
}
```

**오류**

| HTTP | code | message | 조건 |
| --- | --- | --- | --- |
| 422 | `REQUEST_VALIDATION_ERROR` | **지원하지 않는 시·도입니다. 서울특별시 또는 경기도를 선택해주세요.** | `sido_name` 이 허용값 밖 |
| 503 | `DATABASE_ERROR` | 데이터베이스 처리 중 오류가 발생했습니다. | `regions` 조회 실패 |

> 이 엔드포인트의 422 `message` 는 카탈로그 기본 문구("요청 값이 올바르지 않습니다.")가 **아닙니다**.
> 401 은 발생하지 않습니다 — 인증 자체를 하지 않습니다.

---

## 11. PATCH /api/v1/users/me/region — 지역 선택/변경 (인증 필요)

회원가입 이후 지역을 처음 고르거나 언제든 변경합니다. **`/analyze`, `/disposal/schedule`, `/chat` 을 쓰려면 반드시 선행되어야 합니다.**

**요청 Body**

| 필드 | 타입 | 필수 | 제약 |
| --- | --- | --- | --- |
| `region_id` | Integer | 필수 | `> 0`, `regions` 에 존재해야 함 (1~56) |

**응답 200**

| 필드 | 타입 | Nullable | 설명 |
| --- | --- | --- | --- |
| `user_id` | Integer | No | |
| `region` | Region | No | 변경된 지역 전체 객체 |

```json
{ "user_id": 1, "region": { "region_id": 23, "sido_name": "서울특별시", "sgg_name": "강남구" } }
```

**오류**

| HTTP | code | message | 조건 |
| --- | --- | --- | --- |
| 404 | `REGION_NOT_FOUND` | 지원하지 않는 지역입니다. | `region_id` 가 56개 밖 |
| 422 | `REQUEST_VALIDATION_ERROR` | 요청 값이 올바르지 않습니다. | 누락 / 0 이하 / 타입 오류 |
| 503 | `DATABASE_ERROR` | 데이터베이스 처리 중 오류가 발생했습니다. | UPDATE 실패 |

**Side Effect** — `users.region_id` UPDATE. `feedback` 에는 지역을 저장하지 않습니다.

---

## 12. POST /api/v1/analyze — 이미지 분석 (인증 필요)

서비스의 핵심. **이미지 파일 하나만 받습니다.** 지역은 요청에 넣지 않고, JWT 의 사용자로 `users.region_id` 를 조회해 사용합니다.

**요청** — `multipart/form-data`

| 필드 | 타입 | 필수 | 제약 |
| --- | --- | --- | --- |
| `image` | File | 필수 | MIME `image/jpeg` · `image/jpg` · `image/png` · `image/webp`, 10MB 이하(`MAX_IMAGE_SIZE_MB`) |

> `Content-Type` 헤더를 직접 지정하지 말고 클라이언트가 boundary 를 생성하게 두세요.

**처리 순서** (실패 지점에 따라 저장 결과가 달라집니다)

1. JWT 검증
2. `users.region_id` 확인 → NULL 이면 **409**
3. 업로드 원본 검증 (MIME / 0바이트 / 용량)
4. 디코드 → EXIF 회전 보정 → 긴 변 1920px 이하로 축소(비율 유지) → JPEG 품질 85 재인코딩
   → **Vision 과 S3 는 이 동일한 바이트를 받습니다** (저장된 이미지 = 분석된 이미지)
5. Vision `POST /internal/v1/predict` 호출
6. 게이트 판정
   - 중앙 객체 없음 → **200 `RETAKE_REQUIRED` / `AI_NO_MAIN_OBJECT`**, 저장 없음
   - Top-1 score < 0.5(`VISION_CONFIDENCE_THRESHOLD`) → **200 `RETAKE_REQUIRED` / `AI_LOW_CONFIDENCE`**, 저장 없음
7. S3(또는 로컬) 업로드
8. DB 트랜잭션: `images` → `feedback` → `feedback_candidates`(Top-K) 를 한 번에 커밋
   실패 시 rollback + **업로드한 S3 객체를 보상 삭제**
9. 배출요일 조회 (best-effort) — 실패해도 분석은 성공 처리하고 `warnings` 로만 알림

### 12.1 성공 응답 200 (`status = "SUCCESS"`)

| 필드 | 타입 | Nullable | 설명 |
| --- | --- | --- | --- |
| `status` | String | No | `SUCCESS` 고정 |
| `major_category` | String | No | Top-1 대분류 (예: `고철류`) |
| `minor_category` | String | No | Top-1 소분류 (예: `고철`) |
| `class_id` | Integer | No | Top-1 class_id (`major_category`/`minor_category`와 같은 대상) |
| `score` | Number | No | Top-1 신뢰도 (0~1) |
| `candidate_scores` | Array\<CandidateScore\> | No | **Top-1을 제외한** 다른 후보 목록(모델이 틀렸을 때 사용자가 고를 대안). score 내림차순, 최대 `VISION_TOP_K - 1`개(기본 4개) |
| `user_region` | Region | No | `users.region_id` 로 조회한 지역 |
| `disposal_day` | String \| null | Yes | 예 `화, 목`. 외부 API 실패 시 `null` |
| `image_id` | Integer | No | `images.image_id` |
| `feedback_id` | Integer | No | **후속 피드백/채팅에 사용하는 키** |
| `warnings` | Array\<String\> | No | 비어 있을 수 있음. 예 `["PUBLIC_WASTE_UNAVAILABLE"]` |

```json
{
  "status": "SUCCESS",
  "major_category": "고철류",
  "minor_category": "고철",
  "class_id": 0,
  "score": 0.9962,
  "candidate_scores": [
    { "class_id": 11, "category": "종이류_종이", "score": 0.0014 },
    { "class_id": 1, "category": "고철류_비철금속", "score": 0.0003 }
  ],
  "user_region": { "region_id": 23, "sido_name": "서울특별시", "sgg_name": "강남구" },
  "disposal_day": null,
  "image_id": 1,
  "feedback_id": 1,
  "warnings": ["PUBLIC_WASTE_UNAVAILABLE"]
}
```

> `s3_key` 는 **응답에 포함하지 않습니다**(DB 에만 저장).

### 12.2 재촬영 응답 200 (`status = "RETAKE_REQUIRED"`)

오류가 아니라 **정상 200** 입니다. Frontend 는 `status` 로 분기하세요.

| 필드 | 타입 | Nullable | 설명 |
| --- | --- | --- | --- |
| `status` | String | No | `RETAKE_REQUIRED` 고정 |
| `code` | String | No | `AI_LOW_CONFIDENCE` \| `AI_NO_MAIN_OBJECT` |
| `message` | String | No | 사용자 안내 문구 |
| `threshold` | Number \| null | Yes | `AI_LOW_CONFIDENCE` 일 때 `0.5`. `AI_NO_MAIN_OBJECT` 는 `null` |
| `score` | Number \| null | Yes | `AI_LOW_CONFIDENCE` 일 때 실제 Top-1 신뢰도(`threshold` 미만이라 재촬영을 요구한 바로 그 값). `AI_NO_MAIN_OBJECT` 는 점수를 낼 대상 자체가 없으므로 `null` |
| `request_id` | UUID String | No | 재촬영 요청도 추적 가능하도록 포함 |

| code | message | S3/DB 저장 |
| --- | --- | --- |
| `AI_LOW_CONFIDENCE` | 분석 신뢰도가 낮습니다. 물체를 중앙에 선명하게 두고 다시 촬영해주세요. | 안 함 |
| `AI_NO_MAIN_OBJECT` | 분류할 물체를 화면 중앙에 위치시킨 뒤 다시 촬영해주세요. | 안 함 |

### 12.3 오류

| HTTP | code | message | 조건 |
| --- | --- | --- | --- |
| 400 | `IMAGE_EMPTY` | 업로드된 이미지가 비어 있습니다. | 0바이트 |
| 400 | `IMAGE_DECODE_FAILED` | 이미지를 읽을 수 없습니다. 다른 이미지를 사용해주세요. | 디코딩 실패 |
| 401 | `AUTH_REQUIRED` / `AUTH_TOKEN_INVALID` / `AUTH_TOKEN_EXPIRED` | — | 인증 실패 |
| **409** | **`USER_REGION_REQUIRED`** | **분석 전에 거주 지역을 선택해주세요.** | **`users.region_id` IS NULL** |
| 413 | `IMAGE_TOO_LARGE` | 업로드 가능한 이미지 크기를 초과했습니다. | `MAX_IMAGE_SIZE_MB` 초과 |
| 415 | `IMAGE_TYPE_UNSUPPORTED` | 지원하지 않는 이미지 형식입니다. JPG, PNG 또는 WEBP 이미지를 사용해주세요. | 허용 MIME 아님 |
| 422 | `REQUEST_VALIDATION_ERROR` | 요청 값이 올바르지 않습니다. | `image` 필드 누락 |
| 502 | `VISION_UNAVAILABLE` | 이미지 분석 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요. | Vision 연결 실패 |
| 502 | `VISION_BAD_RESPONSE` | 이미지 분석 결과를 처리할 수 없습니다. | Vision 응답 스키마 불일치 / 후보 0개 |
| 502 | `S3_UPLOAD_FAILED` | 이미지 저장 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요. | 업로드 실패 |
| 503 | `VISION_MODEL_NOT_READY` | 이미지 분석 모델이 준비되지 않았습니다. | 체크포인트 미로드 |
| 503 | `DATABASE_ERROR` | 데이터베이스 처리 중 오류가 발생했습니다. | 트랜잭션 실패 (S3 보상 삭제 수행) |
| 504 | `VISION_TIMEOUT` | 이미지 분석 시간이 초과되었습니다. 다시 시도해주세요. | `VISION_REQUEST_TIMEOUT_SECONDS` 초과 |
| 504 | `S3_TIMEOUT` | 이미지 저장 시간이 초과되었습니다. 다시 시도해주세요. | S3 연결 타임아웃 |

---

## 13. 피드백 3종 (섹션 13.1~13.3)

세 엔드포인트 모두 `POST /api/v1/feedback/{feedback_id}/...` 형태이며, **공통 선행 검증**을 거칩니다.

| 순서 | 검증 | 실패 시 |
| --- | --- | --- |
| 1 | `feedback_id` 존재 | 404 `FEEDBACK_NOT_FOUND` — 피드백 정보를 찾을 수 없습니다. |
| 2 | 소유자 == 요청자 | 403 `FEEDBACK_FORBIDDEN` — 해당 피드백에 접근할 권한이 없습니다. |
| 3 | 아직 미처리 (`is_correct IS NULL`) | 409 `FEEDBACK_ALREADY_COMPLETED` — 이미 처리된 피드백입니다. |

**Path Parameter**: `feedback_id` Integer, `> 0`

### 13.1 POST /api/v1/feedback/{feedback_id}/confirm — "예, 맞아요"

요청 Body 없음.

**응답 200**

| 필드 | 타입 | 값 |
| --- | --- | --- |
| `feedback_id` | Integer | |
| `is_correct` | Boolean | `true` 고정 |
| `final_class_id` | Integer | `predicted_class_id` 와 동일 |
| `correction_source` | null | `null` 고정 |
| `message` | String | 분석 결과가 맞는 것으로 저장되었습니다. |

**Side Effect** — `feedback.final_class_id = predicted_class_id`, `is_correct = true`, `correction_source = NULL`

### 13.2 POST /api/v1/feedback/{feedback_id}/select-candidate — 다른 후보 선택

**요청 Body**

| 필드 | 타입 | 필수 | 제약 |
| --- | --- | --- | --- |
| `class_id` | Integer | 필수 | `> 0`, **해당 분석의 Top-K 후보에 존재**해야 하며 Top-1 과 달라야 함 |

**응답 200**

| 필드 | 타입 | 값 |
| --- | --- | --- |
| `feedback_id` | Integer | |
| `is_correct` | Boolean | `false` 고정 |
| `final_class_id` | Integer | 선택한 `class_id` |
| `correction_source` | String | `USER` 고정 |
| `message` | String | 선택한 객체 후보로 수정되었습니다. |

**추가 오류**

| HTTP | code | message |
| --- | --- | --- |
| 400 | `FEEDBACK_SAME_AS_PREDICTION` | 최초 분석 결과와 같은 후보입니다. 맞다고 확인해주세요. |
| 400 | `FEEDBACK_INVALID_CANDIDATE` | 선택한 객체 후보가 해당 분석 결과에 존재하지 않습니다. |
| 422 | `REQUEST_VALIDATION_ERROR` | 요청 값이 올바르지 않습니다. |

### 13.3 POST /api/v1/feedback/{feedback_id}/not-in-list — Gemini 재분석

요청 Body 없음. 저장된 원본 이미지를 내려받아 Gemini 에 재분석을 요청하고, 결과를 **`waste_classes` 17개 class_id 안으로 제한**합니다.

**응답 200**

| 필드 | 타입 | 값 |
| --- | --- | --- |
| `feedback_id` | Integer | |
| `is_correct` | Boolean | `false` 고정 |
| `final_class_id` | Integer | Gemini 가 고른 class_id |
| `correction_source` | String | `GEMINI` 고정 |
| `major_category` | String | 재분석 대분류 |
| `minor_category` | String | 재분석 소분류 |
| `message` | String | 추가 이미지 분석 결과로 수정되었습니다. |

**추가 오류**

| HTTP | code | message |
| --- | --- | --- |
| 502 | `S3_DOWNLOAD_FAILED` | 원본 이미지를 불러오지 못했습니다. 잠시 후 다시 시도해주세요. |
| 502 | `GEMINI_UNAVAILABLE` | 추가 이미지 분석 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해주세요. |
| 502 | `GEMINI_BAD_RESPONSE` | 추가 이미지 분석 결과를 처리할 수 없습니다. |
| 503 | `GEMINI_NOT_CONFIGURED` | 추가 이미지 분석 서비스가 설정되지 않았습니다. |
| 504 | `GEMINI_TIMEOUT` | 추가 이미지 분석 시간이 초과되었습니다. 다시 시도해주세요. |

---

## 14. GET /api/v1/disposal/schedule — 지역별 분리배출 정보 (인증 필요)

`users.region_id` 의 지역 기준으로 행정안전부 API 를 조회합니다. **지역은 요청에 넣지 않습니다.**

**Query Parameter**

| 필드 | 타입 | 필수 | 제약 |
| --- | --- | --- | --- |
| `class_id` | Integer | 필수 | `> 0`, `waste_classes` 에 존재 |

**응답 200**

| 필드 | 타입 | Nullable | 설명 |
| --- | --- | --- | --- |
| `class_id` | Integer | No | |
| `major_category` | String | No | |
| `minor_category` | String | No | |
| `region` | Region | No | 사용자의 현재 지역 |
| `disposal_day` | String \| null | Yes | 예 `화, 목` |
| `start_time` | String \| null | Yes | 예 `18:00` |
| `end_time` | String \| null | Yes | 예 `24:00` |
| `disposal_method` | String \| null | Yes | 배출 방법 안내 |
| `source` | String | No | `행정안전부 생활쓰레기배출정보` 고정 |

**검증 순서 주의** — `class_id` 존재 확인이 **먼저**입니다. 지역 미선택 + 잘못된 `class_id` 면 409 가 아니라 404 가 납니다.

**오류**

| HTTP | code | message | 조건 |
| --- | --- | --- | --- |
| 404 | `CLASS_NOT_FOUND` | 폐기물 분류 정보를 찾을 수 없습니다. | `class_id` 없음 |
| 404 | `PUBLIC_WASTE_NOT_FOUND` | 해당 지역의 분리배출 정보를 찾을 수 없습니다. | 외부 API 에 해당 지역 데이터 없음 |
| **409** | **`USER_REGION_REQUIRED`** | **먼저 거주 지역을 선택해주세요.** | `users.region_id` IS NULL |
| 422 | `REQUEST_VALIDATION_ERROR` | 요청 값이 올바르지 않습니다. | `class_id` 누락/0 이하 |
| 502 | `PUBLIC_WASTE_UNAVAILABLE` | 분리배출 정보 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해주세요. | 키 미설정 / 연결 실패 / 응답 파싱 실패 |
| 502 | `PUBLIC_WASTE_AUTH_ERROR` | 분리배출 정보 서비스 인증에 실패했습니다. | 잘못된 서비스 키 |
| 503 | `PUBLIC_WASTE_RATE_LIMITED` | 분리배출 정보 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요. | 일일 호출 한도 초과 |
| 504 | `PUBLIC_WASTE_TIMEOUT` | 분리배출 정보 조회 시간이 초과되었습니다. 다시 시도해주세요. | 타임아웃 |

> `/analyze` 의 배출요일 조회는 같은 로직을 쓰지만 **실패를 오류로 올리지 않고** `warnings` 에 코드만 담습니다.
> 이 엔드포인트는 직접 조회용이므로 그대로 HTTP 오류로 전달합니다.

---

## 15. POST /api/v1/chat — AI 후속 질문 (인증 필요)

분석 결과에 대한 추가 질문에 답합니다. **Stateless — 대화 내용은 DB 에 저장하지 않습니다.** `session_id` / `message_id` 도 없습니다.

**요청 Body**

| 필드 | 타입 | 필수 | 제약 |
| --- | --- | --- | --- |
| `feedback_id` | Integer | 필수 | `> 0`, 본인 소유 |
| `message` | String | 필수 | 1~1000자 (`CHAT_MESSAGE_MAX_LENGTH`) |

**응답 200**

| 필드 | 타입 | Nullable | 설명 |
| --- | --- | --- | --- |
| `feedback_id` | Integer | No | 요청과 동일 |
| `answer` | String | No | 한국어 답변 |
| `warnings` | Array\<String\> | No | 예 `["PUBLIC_WASTE_UNAVAILABLE"]` |

> `GEMINI_API_KEY` 가 없으면 분석 컨텍스트 + RAG 지식으로 구성한 **결정적 답변**을 반환합니다(오류 아님).
> 키가 있으면 Gemini 가 자연어로 생성합니다.

**검증 순서** — `feedback` 존재 → 소유권 → 지역. 피드백 처리 완료 여부는 보지 않습니다(처리 후에도 질문 가능).

**오류**

| HTTP | code | message | 조건 |
| --- | --- | --- | --- |
| 403 | `FEEDBACK_FORBIDDEN` | **해당 분석 정보에 접근할 권한이 없습니다.** | 타인의 `feedback_id` |
| 404 | `FEEDBACK_NOT_FOUND` | **분석 정보를 찾을 수 없습니다.** | 없는 `feedback_id` |
| 404 | `CLASS_NOT_FOUND` | 폐기물 분류 정보를 찾을 수 없습니다. | 분류 정보 조회 실패 |
| 409 | `USER_REGION_REQUIRED` | 먼저 거주 지역을 선택해주세요. | `users.region_id` IS NULL |
| 422 | `REQUEST_VALIDATION_ERROR` | 요청 값이 올바르지 않습니다. | 빈 메시지 / 1000자 초과 |
| 502 | `AGENT_UNAVAILABLE` | AI 안내 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해주세요. | LLM 장애 |
| 504 | `AGENT_TIMEOUT` | AI 안내 응답 시간이 초과되었습니다. 다시 시도해주세요. | `GEMINI_CHAT_TIMEOUT_SECONDS` 초과 |

> **403/404 문구가 피드백 API 와 다릅니다.** 피드백 API 는 "피드백", Chat 은 "분석 정보"라고 표현합니다.

---

## 16. 즐겨찾기 3종

### 16.1 GET /api/v1/favorites — 목록 (인증 필요)

요청 파라미터 없음. 본인 것만 조회되며 **최신 등록순**(`created_at DESC`)입니다.

| 필드 | 타입 | Nullable | 설명 |
| --- | --- | --- | --- |
| `items` | Array\<FavoriteItem\> | No | 비어 있을 수 있음 |
| `items[].favorite_id` | Integer | No | 삭제에 사용 |
| `items[].class_id` | Integer | No | |
| `items[].major_category` | String | No | |
| `items[].minor_category` | String | No | |
| `items[].created_at` | Datetime | No | |

### 16.2 POST /api/v1/favorites — 등록 (인증 필요)

**요청 Body**

| 필드 | 타입 | 필수 | 제약 |
| --- | --- | --- | --- |
| `class_id` | Integer | 필수 | `> 0`, `waste_classes` 에 존재 |

**응답 201**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `favorite_id` | Integer | 생성된 ID |
| `class_id` | Integer | |
| `major_category` | String | |
| `minor_category` | String | |
| `message` | String | 즐겨찾기에 등록되었습니다. |

**오류**

| HTTP | code | message |
| --- | --- | --- |
| 404 | `CLASS_NOT_FOUND` | 폐기물 분류 정보를 찾을 수 없습니다. |
| 409 | `FAVORITE_ALREADY_EXISTS` | 이미 즐겨찾기에 등록된 품목입니다. |
| 422 | `REQUEST_VALIDATION_ERROR` | 요청 값이 올바르지 않습니다. |
| 503 | `DATABASE_ERROR` | 데이터베이스 처리 중 오류가 발생했습니다. |

> 중복은 `favorites(user_id, class_id)` UNIQUE 제약으로 막습니다.

### 16.3 DELETE /api/v1/favorites/{favorite_id} — 삭제 (인증 필요)

**Path Parameter**: `favorite_id` Integer, `> 0`. 성공 시 `204 No Content` (Body 없음).

| HTTP | code | message | 조건 |
| --- | --- | --- | --- |
| 404 | `FAVORITE_NOT_FOUND` | 즐겨찾기 정보를 찾을 수 없습니다. | 없는 ID **또는 타인 소유** |
| 422 | `REQUEST_VALIDATION_ERROR` | 요청 값이 올바르지 않습니다. | 0 이하 |
| 503 | `DATABASE_ERROR` | 데이터베이스 처리 중 오류가 발생했습니다. | DELETE 실패 |

> 타인 소유일 때 403 이 아니라 **404** 를 돌려줍니다 — 리소스 존재 자체를 숨기기 위함입니다.

---

## 17. Vision 내부 API (Backend 전용)

Frontend 에서 직접 호출하지 않습니다. 운영에서는 사설망/접근제어로 보호하며, 인증 대신 네트워크 경계로 차단합니다.

### 17.1 POST /internal/v1/predict

**요청** — `multipart/form-data`, 필드 `image` (MIME/용량 제약은 Backend 와 동일)

**응답 200**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `major_category` | String | Top-1 대분류 |
| `minor_category` | String | Top-1 소분류 |
| `class_id` | Integer | Top-1 class_id |
| `score` | Number | Top-1 신뢰도 (0~1) |
| `candidate_scores` | Array\<CandidateScore\> | **Top-1 제외**, 나머지 후보. score 내림차순, 최대 `TOP_K - 1`개(기본 4) |
| `internal_meta.bbox` | Object | `x1,y1,x2,y2` — **0~1 정규화 XYXY** |
| `internal_meta.model_version` | String | 추론 모델 식별자 |
| `internal_meta.inference_ms` | Number | 추론 소요 시간(ms) |

**오류**

| HTTP | code | message |
| --- | --- | --- |
| 400 | `IMAGE_EMPTY` | 업로드된 이미지가 비어 있습니다. |
| 400 | `IMAGE_DECODE_FAILED` | 이미지를 읽을 수 없습니다. |
| 413 | `IMAGE_TOO_LARGE` | 업로드 가능한 이미지 크기를 초과했습니다. |
| 415 | `IMAGE_TYPE_UNSUPPORTED` | 지원하지 않는 이미지 형식입니다. |
| **422** | **`VISION_NO_MAIN_OBJECT`** | 화면 중앙에서 메인 객체를 찾지 못했습니다. → **Backend 가 200 `RETAKE_REQUIRED` 로 변환** |
| 503 | `VISION_MODEL_NOT_READY` | 이미지 분석 모델이 준비되지 않았습니다. |
| 500 | `VISION_INFERENCE_ERROR` | 이미지 분석 중 오류가 발생했습니다. (안전망) |

### 17.2 GET /internal/v1/classes

**응답 200**

| 필드 | 타입 | 설명 |
| --- | --- | --- |
| `model_version` | String | 로드된 모델 식별자 |
| `classes` | Array | `{class_id, major_category, minor_category}` × **17** |

**오류**: `503 VISION_MODEL_NOT_READY`

### 17.3 GET /health (Vision)

```json
{ "status": "ok", "model_loaded": true, "model_version": "B00_no_aug_control_seed42" }
```

모델 로드 실패 시 `{"status":"ok","model_loaded":false,"model_version":null}` — **200 은 유지**됩니다.

---

## 18. 오류 코드 카탈로그 (전체)

`code` 는 안정적인 계약입니다. Frontend 분기는 HTTP status 가 아니라 **`code` 로** 하세요.

| HTTP | code | message |
| --- | --- | --- |
| 400 | `IMAGE_EMPTY` | 업로드된 이미지가 비어 있습니다. |
| 400 | `IMAGE_DECODE_FAILED` | 이미지를 읽을 수 없습니다. 다른 이미지를 사용해주세요. |
| 400 | `FEEDBACK_SAME_AS_PREDICTION` | 최초 분석 결과와 같은 후보입니다. 맞다고 확인해주세요. |
| 400 | `FEEDBACK_INVALID_CANDIDATE` | 선택한 객체 후보가 해당 분석 결과에 존재하지 않습니다. |
| 401 | `AUTH_REQUIRED` | 로그인이 필요합니다. |
| 401 | `AUTH_TOKEN_INVALID` | 유효하지 않은 로그인 정보입니다. |
| 401 | `AUTH_TOKEN_EXPIRED` | 로그인이 만료되었습니다. 다시 로그인해주세요. |
| 401 | `AUTH_INVALID_CREDENTIALS` | 이메일 또는 비밀번호가 올바르지 않습니다. |
| 403 | `FEEDBACK_FORBIDDEN` | 해당 피드백에 접근할 권한이 없습니다. / (Chat) 해당 분석 정보에 접근할 권한이 없습니다. |
| 404 | `USER_NOT_FOUND` | 사용자 정보를 찾을 수 없습니다. |
| 404 | `REGION_NOT_FOUND` | 지원하지 않는 지역입니다. |
| 404 | `CLASS_NOT_FOUND` | 폐기물 분류 정보를 찾을 수 없습니다. |
| 404 | `FEEDBACK_NOT_FOUND` | 피드백 정보를 찾을 수 없습니다. / (Chat) 분석 정보를 찾을 수 없습니다. |
| 404 | `FAVORITE_NOT_FOUND` | 즐겨찾기 정보를 찾을 수 없습니다. |
| 404 | `PUBLIC_WASTE_NOT_FOUND` | 해당 지역의 분리배출 정보를 찾을 수 없습니다. |
| 409 | `AUTH_EMAIL_EXISTS` | 이미 가입된 이메일입니다. |
| 409 | `USER_REGION_REQUIRED` | 먼저 거주 지역을 선택해주세요. / (analyze) 분석 전에 거주 지역을 선택해주세요. |
| 409 | `FEEDBACK_ALREADY_COMPLETED` | 이미 처리된 피드백입니다. |
| 409 | `FAVORITE_ALREADY_EXISTS` | 이미 즐겨찾기에 등록된 품목입니다. |
| 413 | `IMAGE_TOO_LARGE` | 업로드 가능한 이미지 크기를 초과했습니다. |
| 415 | `IMAGE_TYPE_UNSUPPORTED` | 지원하지 않는 이미지 형식입니다. JPG, PNG 또는 WEBP 이미지를 사용해주세요. |
| 422 | `REQUEST_VALIDATION_ERROR` | 요청 값이 올바르지 않습니다. (regions 의 `sido_name` 만 별도 문구) |
| 422 | `VISION_NO_MAIN_OBJECT` | (Vision) 화면 중앙에서 메인 객체를 찾지 못했습니다. |
| 500 | `INTERNAL_SERVER_ERROR` | 서버 내부 오류가 발생했습니다. |
| 500 | `VISION_INFERENCE_ERROR` | (Vision) 이미지 분석 중 오류가 발생했습니다. |
| 502 | `VISION_UNAVAILABLE` | 이미지 분석 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요. |
| 502 | `VISION_BAD_RESPONSE` | 이미지 분석 결과를 처리할 수 없습니다. |
| 502 | `S3_UPLOAD_FAILED` | 이미지 저장 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요. |
| 502 | `S3_DOWNLOAD_FAILED` | 원본 이미지를 불러오지 못했습니다. 잠시 후 다시 시도해주세요. |
| 502 | `PUBLIC_WASTE_UNAVAILABLE` | 분리배출 정보 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해주세요. |
| 502 | `PUBLIC_WASTE_AUTH_ERROR` | 분리배출 정보 서비스 인증에 실패했습니다. |
| 502 | `GEMINI_UNAVAILABLE` | 추가 이미지 분석 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해주세요. |
| 502 | `GEMINI_BAD_RESPONSE` | 추가 이미지 분석 결과를 처리할 수 없습니다. |
| 502 | `AGENT_UNAVAILABLE` | AI 안내 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해주세요. |
| 503 | `SERVICE_NOT_READY` | 서비스 준비가 완료되지 않았습니다. |
| 503 | `DATABASE_ERROR` | 데이터베이스 처리 중 오류가 발생했습니다. |
| 503 | `VISION_MODEL_NOT_READY` | 이미지 분석 모델이 준비되지 않았습니다. |
| 503 | `GEMINI_NOT_CONFIGURED` | 추가 이미지 분석 서비스가 설정되지 않았습니다. |
| 503 | `PUBLIC_WASTE_RATE_LIMITED` | 분리배출 정보 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요. |
| 504 | `VISION_TIMEOUT` | 이미지 분석 시간이 초과되었습니다. 다시 시도해주세요. |
| 504 | `S3_TIMEOUT` | 이미지 저장 시간이 초과되었습니다. 다시 시도해주세요. |
| 504 | `PUBLIC_WASTE_TIMEOUT` | 분리배출 정보 조회 시간이 초과되었습니다. 다시 시도해주세요. |
| 504 | `GEMINI_TIMEOUT` | 추가 이미지 분석 시간이 초과되었습니다. 다시 시도해주세요. |
| 504 | `AGENT_TIMEOUT` | AI 안내 응답 시간이 초과되었습니다. 다시 시도해주세요. |

> `AI_LOW_CONFIDENCE` / `AI_NO_MAIN_OBJECT` 는 **오류가 아니라 200 응답의 `code`** 입니다.

---

## 19. Frontend 연동 가이드

### 19.1 필수 화면 흐름

```
회원가입 ──▶ 로그인 ──▶ [지역 선택] ──▶ 촬영/업로드 ──▶ 분석 결과 ──▶ 피드백 ──▶ 후속 질문/즐겨찾기
                          ▲
                          └── 생략하면 analyze / disposal / chat 이 전부 409
```

**지역 선택 단계를 빠뜨리는 것이 가장 흔한 연동 실수입니다.** 회원가입은 지역을 받지 않으므로 `users.region_id` 는 NULL 로 시작합니다.

1. `GET /api/v1/users/me` 의 `region` 이 `null` 인지 확인 (로그인 응답의 `user.region` 으로도 판단 가능)
2. `null` 이면 `GET /api/v1/regions` 로 56개 목록을 받아 선택 UI 표시 — **토큰 불필요**
3. `PATCH /api/v1/users/me/region` 으로 저장
4. 이후 분석 가능

### 19.2 전역 오류 처리 권장

| 수신 코드 | 권장 동작 |
| --- | --- |
| `AUTH_REQUIRED`, `AUTH_TOKEN_INVALID`, `AUTH_TOKEN_EXPIRED` | 토큰 폐기 후 로그인 화면 |
| `USER_REGION_REQUIRED` | 지역 선택 화면으로 이동 (어느 API 에서 왔든) |
| `REQUEST_VALIDATION_ERROR` | `details[].field` 로 폼 필드별 에러 표시 |
| 그 외 | `message` 를 그대로 노출 |

### 19.3 `/analyze` 응답 분기

HTTP 200 이어도 두 가지입니다. 반드시 `status` 로 먼저 분기하세요.

```
200 + status="SUCCESS"          → 결과 화면 (feedback_id 보관)
200 + status="RETAKE_REQUIRED"  → 재촬영 안내 (message 노출, 저장된 것 없음)
4xx/5xx                          → 공통 오류 처리
```

### 19.4 주의사항

- `Content-Type` 을 직접 지정하지 말고 `multipart/form-data` boundary 는 브라우저에 맡기세요.
- 분석 성공 응답의 `warnings` 가 비어 있지 않아도 **분석은 성공**입니다. 배출요일만 못 받은 상태이므로 결과 화면은 정상 표시하고 배출요일 영역만 대체 문구를 띄우세요.
- `feedback_id` 는 confirm / select-candidate / not-in-list / chat 에 모두 필요하므로 분석 결과와 함께 보관하세요.
- 피드백 3종은 각 `feedback_id` 당 **한 번만** 성공합니다(두 번째는 409).

---

## 20. 도메인 데이터 / 저장 정책

### 20.1 DB 테이블

| 테이블 | 용도 | 비고 |
| --- | --- | --- |
| `users` | 계정 | `region_id` FK → `regions`, NULL 허용 |
| `regions` | 지역 Master | 56행 고정 (시드) |
| `waste_classes` | 폐기물 분류 Master | 86행 고정 (시드), `class_id` 는 YOLO 인덱스와 공유 |
| `images` | 분석 이미지 | `s3_key`, `content_type` |
| `feedback` | 분석 1건 = 1행 | bbox, `predicted_*`, `final_class_id`, `is_correct`, `correction_source`, `model_version` |
| `feedback_candidates` | Top-K 후보 | PK `(feedback_id, candidate_rank)` |
| `favorites` | 즐겨찾기 | `(user_id, class_id)` UNIQUE |

### 20.2 저장하지 않는 것

- 평문 비밀번호 (bcrypt 해시만)
- 채팅 메시지·응답 (Stateless)
- `request_id` (로그에만)
- 배출요일 등 행정안전부 API 응답 (조회 시마다 호출)
- `feedback` 에 지역 정보 (사용자 현재 지역을 그때그때 조회)

### 20.3 주요 설정값

| 환경변수 | 기본값 | 설명 |
| --- | --- | --- |
| `MAX_IMAGE_SIZE_MB` | `10` | 업로드 최대 크기 |
| `ALLOWED_IMAGE_CONTENT_TYPES` | `image/jpeg,image/jpg,image/png,image/webp` | 허용 MIME |
| `IMAGE_MAX_DIMENSION` | `1920` | 긴 변 축소 상한(비율 유지, 확대 안 함) |
| `IMAGE_OUTPUT_FORMAT` / `IMAGE_OUTPUT_QUALITY` | `jpeg` / `85` | 재인코딩 포맷·품질 |
| `VISION_CONFIDENCE_THRESHOLD` | `0.5` | 이 미만이면 재촬영 |
| `VISION_TOP_K` | `5` | 후보 개수 |
| `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | 토큰 만료(24시간) |
| `CHAT_MESSAGE_MAX_LENGTH` | `1000` | 채팅 메시지 최대 길이 |
| `STORAGE_BACKEND` | `s3` | `local` 로 두면 AWS 없이 동작 |

### 20.4 장애 격리 정책

Vision / Gemini / 행정안전부 API 장애는 **Backend 전체 장애로 번지지 않습니다.**

- `/health` 는 계속 200
- 행정안전부 API 장애 시 `/analyze` 는 **성공(200)** 하고 `disposal_day: null` + `warnings` 로만 알림
- Gemini 미설정 시 `/chat` 은 결정적 답변으로 대체 (오류 아님), `not-in-list` 만 503

---

## 21. v6.0 설계 명세와의 차이

| 항목 | v6.0 설계 명세 (PDF) | **구현 (v6.1)** | 사유 |
| --- | --- | --- | --- |
| `GET /api/v1/regions` 인증 | 인증 필요. 누락 시 `401 AUTH_REQUIRED`, 토큰 오류 시 `401 AUTH_TOKEN_INVALID` | **인증 불필요.** 401 자체가 발생하지 않으며 `Authorization` 헤더는 무시 | 지역 Master 는 공개 데이터이고, 로그인 전 지역 선택 UI 에서도 목록이 필요 |

그 외 19개 엔드포인트의 경로·인증·요청/응답 필드·오류 코드·메시지는 설계 명세와 일치합니다.

---

## 22. 검증

| 대상 | 명령 | 개수 |
| --- | --- | --- |
| Backend 단위/통합 | `cd backend && ../.venv/Scripts/python.exe -m pytest -q` | 104 |
| Vision | `.venv/Scripts/python.exe -m pytest vision/tests -q` | 24 |
| 실서버 스모크 | `bash scripts/smoke-test.sh` | 100 |

엔드포인트 목록과 인증 요구사항은 `backend/tests/test_error_contract.py` 가 OpenAPI 스키마와 대조해
**문서 밖에서도 자동 검증**합니다. 엔드포인트를 추가·변경하면 이 테스트가 먼저 깨집니다.
