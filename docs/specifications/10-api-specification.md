# API 명세서

**버전** v2.0 · **기준일** 2026-09-28 · **작성 기준** 구현 코드(`backend/`, `vision/`, `rag/`) 직접 추출

> v1.x([`docs/API_SPEC.md`](../API_SPEC.md), 2026-09-14) 대비 **RAG 서비스 연동**이 반영되었습니다:
> `/analyze` 성공 응답에 `national_rule`/`region_rule` 필드 추가, `/feedback/{id}/not-in-list`가
> Gemini 직접 호출 대신 RAG 서비스의 재분류 그래프를 경유하도록 변경, 새로운 재촬영 응답
> `AI_RECLASSIFY_FAILED` 추가. 오류 코드 전체 카탈로그는 [15-error-specification.md](15-error-specification.md),
> 데이터 모델은 [11-data-specification.md](11-data-specification.md)를 참고하세요(이 문서는 중복을
> 피하기 위해 필드 표에 집중합니다).

---

## 1. 시스템 구성 및 Base URL

| 서버 | 역할 | 기본 주소 | 노출 대상 |
|---|---|---|---|
| Backend | 인증·비즈니스 로직·DB·외부 연동 | `http://127.0.0.1:8000` | Frontend |
| Vision | YOLO 중앙 객체 탐지 + Top-K 후보 | `http://127.0.0.1:8100` | Backend 전용 |
| RAG | 배출방법 규정 조회·AI Agent 답변·재분류 | `http://127.0.0.1:8001` | Backend 전용 |

- Backend 공개 API: `/api/v1/*` · 헬스체크: `/health`, `/ready`(버전 접두사 없음)
- Vision 내부 API: `/internal/v1/*`
- RAG 내부 API: `/rule_node`, `/chat_node`, `/reclassify`, `/cache_info`

## 2. 공통 규약

### 2.1 인증

JWT Bearer 토큰. `POST /api/v1/auth/login`이 발급.

```http
Authorization: Bearer <access_token>
```

| 항목 | 값 |
|---|---|
| 알고리즘 | `HS256` |
| 만료 | 기본 1440분(24시간), `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` |
| Payload | `sub`(user_id), `iat`, `exp` |
| 로그아웃 | Stateless — Frontend가 토큰 폐기 |

### 2.2 X-Request-ID / 날짜 형식

모든 응답에 `X-Request-ID` 헤더. 모든 Datetime은 UTC `Z` 접미사(`2026-09-11T09:00:00Z`).

### 2.3 공통 오류 응답

```json
{ "success": false, "code": "USER_REGION_REQUIRED", "message": "...", "details": null, "request_id": "..." }
```

전체 카탈로그: [15-error-specification.md](15-error-specification.md).

### 2.4 공통 객체

| 객체 | 필드 |
|---|---|
| **Region** | `region_id`(1~56), `sido_name`(`서울특별시`\|`경기도`), `sgg_name` |
| **CandidateScore** | `class_id`(0~16), `category`(`대분류_소분류`), `score`(0~1) |
| **NationalRuleOut** | `source`, `method`(nullable) |
| **RegionRuleOut** | `region`, `source_url`, `exception_type`, `method` |

---

## 3. 엔드포인트 요약 (19개, Backend 17 + Vision 2)

| # | Method | Endpoint | 인증 | 성공 | 기능 |
|---|---|---|---|---|---|
| 1 | GET | `/health` | ✗ | 200 | Backend liveness |
| 2 | GET | `/ready` | ✗ | 200 | DB 포함 readiness |
| 3 | POST | `/api/v1/auth/signup` | ✗ | 201 | 회원가입(지역 안 받음) |
| 4 | POST | `/api/v1/auth/login` | ✗ | 200 | 로그인 → JWT |
| 5 | POST | `/api/v1/auth/logout` | ✓ | 204 | 로그아웃 |
| 6 | GET | `/api/v1/users/me` | ✓ | 200 | 내 프로필 |
| 7 | GET | `/api/v1/regions` | **✗** | 200 | 지원 지역 56개 |
| 8 | PATCH | `/api/v1/users/me/region` | ✓ | 200 | 지역 선택/변경 |
| 9 | POST | `/api/v1/analyze` | ✓ | 200 | 이미지 분석 |
| 10 | POST | `/api/v1/feedback/{id}/confirm` | ✓ | 200 | "예, 맞아요" |
| 11 | POST | `/api/v1/feedback/{id}/select-candidate` | ✓ | 200 | 다른 후보 선택 |
| 12 | POST | `/api/v1/feedback/{id}/not-in-list` | ✓ | 200 | RAG 재분류 |
| 13 | GET | `/api/v1/disposal/schedule` | ✓ | 200 | 지역별 배출정보 |
| 14 | POST | `/api/v1/chat` | ✓ | 200 | AI 후속 질문(Stateless) |
| 15 | GET | `/api/v1/favorites` | ✓ | 200 | 즐겨찾기 목록 |
| 16 | POST | `/api/v1/favorites` | ✓ | 201 | 즐겨찾기 등록 |
| 17 | DELETE | `/api/v1/favorites/{id}` | ✓ | 204 | 즐겨찾기 삭제 |
| 18 | POST | `/internal/v1/predict` | 내부 | 200 | YOLO 예측 |
| 19 | GET | `/internal/v1/classes` | 내부 | 200 | Vision taxonomy |

> **7번만 인증이 없습니다.** 지역 Master는 공개 데이터라 로그인 전 선택 UI에도 필요합니다.

---

## 4. 인증 (§6~9)

### 4.1 `POST /api/v1/auth/signup`

요청(JSON): `email`(형식 검증, 255자↓), `password`(8~72바이트, UTF-8 기준)

응답 201: `user_id`, `email`, `region`(**항상 null**), `created_at`

### 4.2 `POST /api/v1/auth/login`

요청: `email`, `password`(1~72자)

응답 200: `access_token`, `token_type`(`bearer`), `user`(UserProfile)

> 로그인 직후 `user.region`이 `null`이면 지역 선택 화면, 아니면 홈으로 분기(Frontend 규약).
> 계정 없음/비밀번호 불일치는 **동일 코드**(`AUTH_INVALID_CREDENTIALS`)로 응답(계정 존재 노출 방지).

### 4.3 `POST /api/v1/auth/logout` — 204, Body 없음(Stateless)

### 4.4 `GET /api/v1/users/me`

응답 200: `user_id`, `email`, `region`(nullable), `created_at`, `updated_at`. `password_hash`는 어떤 응답에도 없음.

---

## 5. 지역 (§10~11)

### 5.1 `GET /api/v1/regions` (인증 불필요)

Query: `sido_name`(선택, `서울특별시`\|`경기도`)

응답 200: `items: Region[]` (최대 56개, `region_id` 오름차순)

### 5.2 `PATCH /api/v1/users/me/region`

요청: `region_id`(>0, 1~56)

응답 200: `user_id`, `region`

**Side Effect**: `users.region_id` UPDATE. `feedback`에는 지역을 저장하지 않음(항상 그때그때 조회).

---

## 6. 이미지 분석 — `POST /api/v1/analyze` (§12, 핵심)

요청(multipart/form-data): `image`(File, MIME `jpeg`/`jpg`/`png`/`webp`, 10MB 이하)

**처리 순서**: JWT 검증 → region 확인(409 게이트) → 업로드 검증 → 재인코딩 → Vision 예측 →
메인 객체 게이트 → S3 업로드 → DB 트랜잭션 → 신뢰도 게이트 → 배출요일/배출방법 best-effort 조회.
전체 분기는 [07-flowchart.md](07-flowchart.md) §1 참고.

### 6.1 성공 응답 200 (`status: "SUCCESS"`)

| 필드 | 타입 | Nullable | 설명 |
|---|---|---|---|
| `major_category` / `minor_category` | String | No | Top-1 대/소분류 |
| `class_id` | Integer | No | Top-1 class_id |
| `score` | Number | No | Top-1 신뢰도(0~1) |
| `candidate_scores` | CandidateScore[] | No | Top-1 제외 나머지(최대 `VISION_TOP_K-1`=4개) |
| `user_region` | Region | No | 사용자 현재 지역 |
| `disposal_day` | String\|null | Yes | 예 `화, 목`. 외부 API 실패 시 null |
| `national_rule` | NationalRuleOut\|null | Yes | **(v2.0 신규)** RAG 조회 전국 공통 배출방법. 조회 실패 시 null |
| `region_rule` | RegionRuleOut\|null | Yes | **(v2.0 신규)** RAG 조회 경기도 예외 규정. 서울/조회 실패/해당無 시 null |
| `image_id` / `feedback_id` | Integer | No | 후속 피드백·채팅에 `feedback_id` 사용 |
| `warnings` | String[] | No | 예 `["PUBLIC_WASTE_UNAVAILABLE"]`, `["RAG_SERVICE_UNAVAILABLE"]` |

`s3_key`는 응답에 포함하지 않습니다(DB에만 저장).

### 6.2 재촬영 응답 200 (`status: "RETAKE_REQUIRED"`)

정상 200입니다 — Frontend는 `status`로 먼저 분기해야 합니다.

| 필드 | 타입 | Nullable | 설명 |
|---|---|---|---|
| `code` | String | No | `AI_LOW_CONFIDENCE` \| `AI_NO_MAIN_OBJECT` |
| `threshold` | Number\|null | Yes | 항상 채워짐(`VISION_CONFIDENCE_THRESHOLD`) |
| `score` / `class_id` / `major_category` / `minor_category` | — | Yes | `AI_LOW_CONFIDENCE`만 채워짐, `AI_NO_MAIN_OBJECT`는 전부 null |
| `feedback_id` | Integer\|null | Yes | `AI_LOW_CONFIDENCE`만 값 있음(이미 저장됨) |

### 6.3 주요 오류

| HTTP | code | 조건 |
|---|---|---|
| 409 | `USER_REGION_REQUIRED` | `users.region_id IS NULL` |
| 400/413/415 | `IMAGE_EMPTY`/`IMAGE_TOO_LARGE`/`IMAGE_TYPE_UNSUPPORTED` | 업로드 검증 실패 |
| 502 | `VISION_UNAVAILABLE`/`VISION_BAD_RESPONSE` | Vision 연동 실패 |
| 503 | `VISION_MODEL_NOT_READY`/`DATABASE_ERROR` | 모델 미로드 / 트랜잭션 실패(S3 보상 삭제 수행) |

전체 오류 목록: [15-error-specification.md](15-error-specification.md) §3.

---

## 7. 피드백 3종 (§13)

공통 선행 검증: `feedback_id` 존재(404) → 소유자 일치(403) → 미처리 상태(409, `is_correct IS NULL`).

### 7.1 `POST /feedback/{id}/confirm` — "예, 맞아요"

Body 없음. 응답 200: `feedback_id`, `is_correct:true`, `final_class_id=predicted_class_id`, `correction_source:null`, `message`

**Side Effect**: `final_class_id=predicted_class_id`, `is_correct=true`, `correction_source=NULL`

### 7.2 `POST /feedback/{id}/select-candidate` — 다른 후보 선택

요청: `class_id`(>0, 해당 분석의 Top-K 후보 중 하나, Top-1과 달라야 함)

응답 200: `final_class_id=선택값`, `is_correct:false`, `correction_source:"USER"`

추가 오류: `400 FEEDBACK_SAME_AS_PREDICTION`, `400 FEEDBACK_INVALID_CANDIDATE`

### 7.3 `POST /feedback/{id}/not-in-list` — RAG 재분류 **(v2.0 변경)**

Body 없음. **(구) Gemini 단독 재분류 → (신) RAG 서비스의 재분류 그래프**(`classify → disposal_lookup`)로
대체되었습니다. 저장된 원본 이미지를 S3에서 재다운로드해 base64 data URL로 RAG `/reclassify`에 전달합니다.

**응답 200 (성공, `NotInListResponse`)**

| 필드 | 타입 | 설명 |
|---|---|---|
| `feedback_id` | Integer | |
| `is_correct` | false 고정 | |
| `final_class_id` | Integer | RAG가 고른 class_id(waste_classes 역조회) |
| `correction_source` | `"GEMINI"` 고정 | 내부적으로 RAG 서비스 경유지만 값은 하위호환 유지 |
| `major_category` / `minor_category` | String | 재분류 결과 |
| `disposal_day` | String\|null | 재조회된 배출요일 |
| `national_rule` / `region_rule` | NationalRuleOut\|null / RegionRuleOut\|null | RAG가 함께 반환한 배출방법 규정 |
| `message` | String | 추가 이미지 분석 결과로 수정되었습니다. |

**응답 200 (재분류 실패, `NotInListRetakeResponse` — v2.0 신규)**

| 필드 | 값 |
|---|---|
| `status` | `"RETAKE_REQUIRED"` |
| `code` | `"AI_RECLASSIFY_FAILED"` |
| `message` | 재분류에 실패했습니다. 사진을 다시 촬영해 업로드해주세요. |

RAG 그래프가 유효한 분류를 찾지 못하고 재시도 횟수를 소진했을 때(`needs_retake: true`) 반환됩니다.

**추가 오류**: `502 S3_DOWNLOAD_FAILED`, `502 RAG_SERVICE_UNAVAILABLE`(구 `GEMINI_UNAVAILABLE` 대체),
`502 RAG_BAD_RESPONSE`, `504 RAG_RECLASSIFY_TIMEOUT`(60초 — 재분류+검증 루프라 여유 있게 설정)

---

## 8. 배출정보 — `GET /api/v1/disposal/schedule` (§14)

Query: `class_id`(>0, 존재해야 함)

응답 200: `class_id`, `major_category`, `minor_category`, `region`, `disposal_day`, `start_time`,
`end_time`, `disposal_method`, `source`(`"행정안전부 생활쓰레기배출정보"` 고정)

> 검증 순서 주의: `class_id` 존재 확인이 지역 확인보다 **먼저**입니다 — 지역 미선택 + 잘못된
> `class_id`면 409가 아니라 404.

주요 오류: `404 CLASS_NOT_FOUND`, `404 PUBLIC_WASTE_NOT_FOUND`, `409 USER_REGION_REQUIRED`,
`502 PUBLIC_WASTE_UNAVAILABLE`/`PUBLIC_WASTE_AUTH_ERROR`, `503 PUBLIC_WASTE_RATE_LIMITED`,
`504 PUBLIC_WASTE_TIMEOUT`

> `/analyze`의 배출요일 조회는 같은 로직이지만 실패를 `warnings`로만 알리고, 이 엔드포인트는
> 직접 조회용이라 그대로 HTTP 오류로 전달합니다.

---

## 9. AI Agent 채팅 — `POST /api/v1/chat` (§15)

요청: `feedback_id`(>0, 본인 소유), `message`(1~1000자, `CHAT_MESSAGE_MAX_LENGTH`)

응답 200: `feedback_id`, `answer`(한국어), `warnings`

> **Stateless** — `session_id`/`message_id` 없음, 대화 내용 DB 미저장. 검증 순서: feedback 존재 →
> 소유권 → region. 피드백 처리 완료 여부는 보지 않음(정정 후에도 질문 가능).
>
> 답변 생성 경로: 지역이 있으면 RAG `/chat_node` 호출(규칙 조회 + Gemini 자연어 생성) → 실패하거나
> 지역이 없으면 `backend/agent/service.py`의 **결정적 템플릿 답변**으로 폴백(오류 아님). 자세한
> 흐름은 [08-sequence-diagram.md](08-sequence-diagram.md) §4.

주요 오류: `403 FEEDBACK_FORBIDDEN`(문구가 피드백 API와 다름 — "해당 분석 정보에 접근할 권한이
없습니다"), `404 FEEDBACK_NOT_FOUND`(문구: "분석 정보를 찾을 수 없습니다"), `409 USER_REGION_REQUIRED`,
`502 AGENT_UNAVAILABLE`, `504 AGENT_TIMEOUT`

---

## 10. 즐겨찾기 3종 (§16)

### 10.1 `GET /api/v1/favorites` — 본인 것만, 최신 등록순(`created_at DESC`)

응답: `items[]` — `favorite_id`, `class_id`, `major_category`, `minor_category`, `created_at`

### 10.2 `POST /api/v1/favorites`

요청: `class_id`(>0, 존재해야 함)

응답 201: `favorite_id`, `class_id`, `major_category`, `minor_category`, `message`

오류: `404 CLASS_NOT_FOUND`, `409 FAVORITE_ALREADY_EXISTS`(UNIQUE `(user_id,class_id)`)

### 10.3 `DELETE /api/v1/favorites/{favorite_id}` — 204

오류: `404 FAVORITE_NOT_FOUND`(없는 ID **또는 타인 소유** — 403이 아니라 404로 존재 자체를 숨김)

---

## 11. Vision 내부 API (§17, Backend 전용)

### 11.1 `POST /internal/v1/predict`

요청(multipart): `image`(제약은 Backend와 동일)

응답 200: `major_category`, `minor_category`, `class_id`, `score`, `candidate_scores[]`,
`internal_meta.bbox{x1,y1,x2,y2}`(0~1 정규화 XYXY), `internal_meta.model_version`, `internal_meta.inference_ms`

주요 오류: `422 VISION_NO_MAIN_OBJECT`(**Backend가 200 AI_NO_MAIN_OBJECT로 변환**), `503 VISION_MODEL_NOT_READY`

### 11.2 `GET /internal/v1/classes`

응답 200: `model_version`, `classes[]`(`{class_id, major_category, minor_category}` × 17)

### 11.3 `GET /health` (Vision)

```json
{ "status": "ok", "model_loaded": true, "model_version": "..." }
```

모델 로드 실패해도 `model_loaded:false`로 **200 유지**.

---

## 12. RAG 내부 API (신규, Backend 전용 — 이전 문서에 없던 항목)

Frontend가 직접 호출하지 않으며, Backend의 `services/disposal_service.py`만 호출합니다.

| Endpoint | 호출부 | 용도 |
|---|---|---|
| `POST /rule_node` | `get_rule_info_or_warn` | `/analyze` 성공 응답의 `national_rule`/`region_rule` |
| `POST /chat_node` | `get_chat_answer_or_warn` | `/chat` 자연어 답변 생성 |
| `POST /reclassify` | `reclassify_or_raise` | `/feedback/{id}/not-in-list` 핵심 로직 |
| `GET /cache_info` | (운영 확인용) | `rule_lookup.py`의 `lru_cache` 적중률 확인 |

내부 구조와 데이터 흐름은 [09-service-architecture.md](09-service-architecture.md) §4를 참고하세요.

---

## 13. Frontend 연동 가이드

### 13.1 필수 화면 흐름

```
회원가입 → 로그인 → [지역 선택] → 촬영/업로드 → 분석 결과 → 피드백 → 후속 질문/즐겨찾기
                     ▲
                     └── 생략하면 analyze/disposal/chat이 전부 409
```

### 13.2 `/analyze` 응답 분기

HTTP 200이어도 두 가지입니다. 반드시 `status`로 먼저 분기하세요.

```
200 + status="SUCCESS"          → 결과 화면 (feedback_id 보관)
200 + status="RETAKE_REQUIRED"  → 재촬영 안내
4xx/5xx                          → 공통 오류 처리
```

### 13.3 주의사항

- `Content-Type`을 직접 지정하지 말고 `multipart/form-data` boundary는 브라우저에 맡길 것.
- `warnings`가 비어 있지 않아도 분석 자체는 **성공**(배출요일/배출방법만 일부 누락).
- `feedback_id`는 confirm/select-candidate/not-in-list/chat에 모두 필요 — 분석 결과와 함께 보관.
- 피드백 3종은 각 `feedback_id`당 **한 번만** 성공(두 번째는 409).

---

## 14. 검증

| 대상 | 명령 | 개수 |
|---|---|---|
| Backend 단위/통합 | `cd backend && ../.venv/Scripts/python.exe -m pytest -q` | 104 |
| Vision | `.venv/Scripts/python.exe -m pytest vision/tests -q` | 24 |
| 실서버 스모크 | `bash scripts/smoke-test.sh` | 100건 검사(19개 API 그룹) |

엔드포인트 목록·인증 요구사항은 `backend/tests/test_error_contract.py`가 OpenAPI 스키마와 대조해
문서 밖에서도 자동 검증합니다.

---

## 15. 참고

- 전체 오류 코드 카탈로그: [15-error-specification.md](15-error-specification.md)
- 데이터 모델: [11-data-specification.md](11-data-specification.md) / [12-erd.md](12-erd.md)
- 서비스 아키텍처: [09-service-architecture.md](09-service-architecture.md)
- 원본 조사 문서: [`docs/API_SPEC.md`](../API_SPEC.md)(v1.x), [`docs/API_TEST_COMMANDS.md`](../API_TEST_COMMANDS.md)(curl 예시)
