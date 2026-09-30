# 오류 명세서

**버전** v1.1 · **기준일** 2026-09-28 · **작성 기준** 구현 코드(`backend/`, `vision/`, `rag/`) 직접 추출

> v1.0([`docs/API_SPEC.md`](../API_SPEC.md) 기준, 2026-09-14) 대비 RAG 서비스 연동으로 추가된
> `RAG_*` 계열 오류 코드가 반영되어 있습니다.

---

## 1. 공통 오류 응답 형식

모든 HTTP 오류(4xx/5xx)는 예외 없이 아래 5개 필드를 가지며, 모든 응답(성공 포함)에
`X-Request-ID` 헤더가 붙습니다.

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
|---|---|---|---|
| `success` | Boolean | No | 오류 응답에서는 항상 `false` |
| `code` | String | No | 안정적인 오류 코드. **Frontend 분기는 HTTP status가 아니라 이 값으로** |
| `message` | String | No | 사용자에게 그대로 노출 가능한 한국어 문구 |
| `details` | Array \| null | Yes | `REQUEST_VALIDATION_ERROR`일 때만 `[{field, message}]` |
| `request_id` | UUID String | No | `X-Request-ID` 헤더와 동일 값 |

`422 REQUEST_VALIDATION_ERROR`의 `details` 예시:

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

> **주의**: `AI_LOW_CONFIDENCE` / `AI_NO_MAIN_OBJECT` / `AI_RECLASSIFY_FAILED`는 오류가
> **아니라** HTTP 200 응답 본문의 `code` 필드입니다(정상적인 "재촬영 필요" 분기).
> 이 문서의 표에서는 구분을 위해 별도 섹션(§4)에 정리했습니다.

---

## 2. 오류 코드 카탈로그 (HTTP status 순)

### 400 Bad Request

| code | message | 발생 API | 조건 |
|---|---|---|---|
| `IMAGE_EMPTY` | 업로드된 이미지가 비어 있습니다. | `/analyze`, `/internal/v1/predict` | 0바이트 업로드 |
| `IMAGE_DECODE_FAILED` | 이미지를 읽을 수 없습니다. 다른 이미지를 사용해주세요. | 〃 | 디코딩 실패(손상된 파일 등) |
| `FEEDBACK_SAME_AS_PREDICTION` | 최초 분석 결과와 같은 후보입니다. 맞다고 확인해주세요. | `/feedback/{id}/select-candidate` | 선택한 `class_id`가 Top-1과 동일 |
| `FEEDBACK_INVALID_CANDIDATE` | 선택한 객체 후보가 해당 분석 결과에 존재하지 않습니다. | 〃 | 선택한 `class_id`가 해당 분석의 Top-K 후보 목록 밖 |

### 401 Unauthorized

| code | message | 조건 |
|---|---|---|
| `AUTH_REQUIRED` | 로그인이 필요합니다. | `Authorization` 헤더 자체가 없음 |
| `AUTH_TOKEN_INVALID` | 유효하지 않은 로그인 정보입니다. | `Bearer` 스킴이 아니거나 토큰이 깨짐 |
| `AUTH_TOKEN_EXPIRED` | 로그인이 만료되었습니다. 다시 로그인해주세요. | 서명은 맞지만 `exp` 경과 |
| `AUTH_INVALID_CREDENTIALS` | 이메일 또는 비밀번호가 올바르지 않습니다. | 로그인 시 계정 없음 **또는** 비밀번호 불일치(구분하지 않음 — 계정 존재 노출 방지) |

### 403 Forbidden

| code | message | 발생 API | 조건 |
|---|---|---|---|
| `FEEDBACK_FORBIDDEN` | 해당 피드백에 접근할 권한이 없습니다. | 피드백 3종 | 타인의 `feedback_id` |
| `FEEDBACK_FORBIDDEN` | (Chat) 해당 분석 정보에 접근할 권한이 없습니다. | `/chat` | 타인의 `feedback_id` — **문구가 다름에 주의** |

### 404 Not Found

| code | message | 조건 |
|---|---|---|
| `USER_NOT_FOUND` | 사용자 정보를 찾을 수 없습니다. | 토큰은 유효하지만 사용자 행이 없음(탈퇴 등) |
| `REGION_NOT_FOUND` | 지원하지 않는 지역입니다. | `region_id`가 56개 밖 |
| `CLASS_NOT_FOUND` | 폐기물 분류 정보를 찾을 수 없습니다. | `class_id`가 17개 밖 |
| `FEEDBACK_NOT_FOUND` | 피드백 정보를 찾을 수 없습니다. / (Chat) 분석 정보를 찾을 수 없습니다. | 없는 `feedback_id` |
| `FAVORITE_NOT_FOUND` | 즐겨찾기 정보를 찾을 수 없습니다. | 없는 `favorite_id` **또는 타인 소유**(403 아님 — 존재 자체를 숨김) |
| `PUBLIC_WASTE_NOT_FOUND` | 해당 지역의 분리배출 정보를 찾을 수 없습니다. | 외부 API에 해당 지역 데이터가 없음 |

### 409 Conflict

| code | message | 조건 |
|---|---|---|
| `AUTH_EMAIL_EXISTS` | 이미 가입된 이메일입니다. | 이메일 중복 |
| `USER_REGION_REQUIRED` | 먼저 거주 지역을 선택해주세요. / (analyze) 분석 전에 거주 지역을 선택해주세요. | `users.region_id IS NULL`인 채로 지역이 필요한 API 호출 |
| `FEEDBACK_ALREADY_COMPLETED` | 이미 처리된 피드백입니다. | `is_correct`가 이미 NULL이 아님(피드백 3종은 각 1회만 성공) |
| `FAVORITE_ALREADY_EXISTS` | 이미 즐겨찾기에 등록된 품목입니다. | `(user_id, class_id)` 중복 |

### 413 / 415

| HTTP | code | message | 조건 |
|---|---|---|---|
| 413 | `IMAGE_TOO_LARGE` | 업로드 가능한 이미지 크기를 초과했습니다. | `MAX_IMAGE_SIZE_MB`(기본 10MB) 초과 |
| 415 | `IMAGE_TYPE_UNSUPPORTED` | 지원하지 않는 이미지 형식입니다. JPG, PNG 또는 WEBP 이미지를 사용해주세요. | 허용 MIME 밖 |

### 422 Unprocessable Entity

| code | message | 비고 |
|---|---|---|
| `REQUEST_VALIDATION_ERROR` | 요청 값이 올바르지 않습니다. (단, `/regions`의 `sido_name`만 "지원하지 않는 시·도입니다..." 별도 문구) | Pydantic 검증 실패 전반 |
| `VISION_NO_MAIN_OBJECT` | (Vision 내부) 화면 중앙에서 메인 객체를 찾지 못했습니다. | **Backend가 200 `AI_NO_MAIN_OBJECT`로 변환**하므로 Frontend에는 노출되지 않음 |

### 500 Internal Server Error

| code | message |
|---|---|
| `INTERNAL_SERVER_ERROR` | 서버 내부 오류가 발생했습니다. |
| `VISION_INFERENCE_ERROR` | (Vision) 이미지 분석 중 오류가 발생했습니다. (안전망) |

### 502 Bad Gateway (외부/내부 연동 실패)

| code | message | 실패한 대상 |
|---|---|---|
| `VISION_UNAVAILABLE` | 이미지 분석 서버에 연결할 수 없습니다. 잠시 후 다시 시도해주세요. | Vision 서버 연결 실패 |
| `VISION_BAD_RESPONSE` | 이미지 분석 결과를 처리할 수 없습니다. | Vision 응답 스키마 불일치 / 후보 0개 |
| `S3_UPLOAD_FAILED` | 이미지 저장 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요. | S3 업로드 실패 |
| `S3_DOWNLOAD_FAILED` | 원본 이미지를 불러오지 못했습니다. 잠시 후 다시 시도해주세요. | not-in-list 시 원본 재다운로드 실패 |
| `PUBLIC_WASTE_UNAVAILABLE` | 분리배출 정보 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해주세요. | 행정안전부 API 키 미설정/연결 실패/파싱 실패 |
| `PUBLIC_WASTE_AUTH_ERROR` | 분리배출 정보 서비스 인증에 실패했습니다. | 잘못된 서비스 키 |
| `RAG_SERVICE_UNAVAILABLE` | 추가 이미지 분석 서비스에 연결할 수 없습니다. 잠시 후 다시 시도해주세요. | RAG 서비스(:8001) 연결 실패 — `not-in-list` 경로 |
| `RAG_BAD_RESPONSE` | 추가 이미지 분석 결과를 처리할 수 없습니다. | RAG 응답의 `class_id`가 `waste_classes` 17개 밖 등 |
| `AGENT_UNAVAILABLE` | AI 안내 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해주세요. | Chat 응답 생성 실패 |

### 503 Service Unavailable

| code | message | 조건 |
|---|---|---|
| `SERVICE_NOT_READY` | 서비스 준비가 완료되지 않았습니다. | `/ready`에서 DB 연결 실패 |
| `DATABASE_ERROR` | 데이터베이스 처리 중 오류가 발생했습니다. | 트랜잭션 실패(analyze는 S3 보상 삭제까지 수행) |
| `VISION_MODEL_NOT_READY` | 이미지 분석 모델이 준비되지 않았습니다. | YOLO 체크포인트 미로드 |
| `GEMINI_NOT_CONFIGURED` | 추가 이미지 분석 서비스가 설정되지 않았습니다. | (구) `GEMINI_API_KEY` 미설정 — 현재는 RAG 서비스 경유로 대체되어 발생 빈도가 낮음 |
| `PUBLIC_WASTE_RATE_LIMITED` | 분리배출 정보 요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요. | 일일 호출 한도 초과 |

### 504 Gateway Timeout

| code | message | 조건 |
|---|---|---|
| `VISION_TIMEOUT` | 이미지 분석 시간이 초과되었습니다. 다시 시도해주세요. | `VISION_REQUEST_TIMEOUT_SECONDS`(기본 15초) 초과 |
| `S3_TIMEOUT` | 이미지 저장 시간이 초과되었습니다. 다시 시도해주세요. | S3 연결 타임아웃 |
| `PUBLIC_WASTE_TIMEOUT` | 분리배출 정보 조회 시간이 초과되었습니다. 다시 시도해주세요. | 타임아웃(`PUBLIC_WASTE_API_TIMEOUT_SECONDS`, 기본 8초) |
| `RAG_RECLASSIFY_TIMEOUT` | 추가 이미지 분석 시간이 초과되었습니다. 다시 시도해주세요. | RAG `/reclassify` 60초 타임아웃 초과(LLM 재분류+judge 루프라 여유 있게 설정) |
| `AGENT_TIMEOUT` | AI 안내 응답 시간이 초과되었습니다. 다시 시도해주세요. | `GEMINI_CHAT_TIMEOUT_SECONDS`(기본 20초) 초과 |

---

## 3. API별 오류 발생 매트릭스

| API | 발생 가능 오류 코드 |
|---|---|
| `POST /auth/signup` | `AUTH_EMAIL_EXISTS`, `REQUEST_VALIDATION_ERROR`, `DATABASE_ERROR` |
| `POST /auth/login` | `AUTH_INVALID_CREDENTIALS`, `REQUEST_VALIDATION_ERROR`, `DATABASE_ERROR` |
| `POST /auth/logout`, `GET /users/me` | `AUTH_REQUIRED`, `AUTH_TOKEN_INVALID`, `AUTH_TOKEN_EXPIRED`, `USER_NOT_FOUND`, `DATABASE_ERROR` |
| `GET /regions` | `REQUEST_VALIDATION_ERROR`(전용 문구), `DATABASE_ERROR` — **인증 오류 없음** |
| `PATCH /users/me/region` | `REGION_NOT_FOUND`, `REQUEST_VALIDATION_ERROR`, `DATABASE_ERROR` + 인증 3종 |
| `POST /analyze` | `USER_REGION_REQUIRED`, `IMAGE_EMPTY`, `IMAGE_DECODE_FAILED`, `IMAGE_TOO_LARGE`, `IMAGE_TYPE_UNSUPPORTED`, `REQUEST_VALIDATION_ERROR`, `VISION_UNAVAILABLE`, `VISION_BAD_RESPONSE`, `VISION_MODEL_NOT_READY`, `VISION_TIMEOUT`, `S3_UPLOAD_FAILED`, `S3_TIMEOUT`, `DATABASE_ERROR` + 인증 3종 |
| `POST /feedback/{id}/confirm` | `FEEDBACK_NOT_FOUND`, `FEEDBACK_FORBIDDEN`, `FEEDBACK_ALREADY_COMPLETED`, `DATABASE_ERROR` + 인증 3종 |
| `POST /feedback/{id}/select-candidate` | 위 3종 + `FEEDBACK_SAME_AS_PREDICTION`, `FEEDBACK_INVALID_CANDIDATE`, `REQUEST_VALIDATION_ERROR` |
| `POST /feedback/{id}/not-in-list` | 위 3종 + `USER_REGION_REQUIRED`, `S3_DOWNLOAD_FAILED`, `RAG_SERVICE_UNAVAILABLE`, `RAG_BAD_RESPONSE`, `RAG_RECLASSIFY_TIMEOUT`, `DATABASE_ERROR` |
| `GET /disposal/schedule` | `CLASS_NOT_FOUND`, `PUBLIC_WASTE_NOT_FOUND`, `USER_REGION_REQUIRED`, `REQUEST_VALIDATION_ERROR`, `PUBLIC_WASTE_UNAVAILABLE`, `PUBLIC_WASTE_AUTH_ERROR`, `PUBLIC_WASTE_RATE_LIMITED`, `PUBLIC_WASTE_TIMEOUT` + 인증 3종 |
| `POST /chat` | `FEEDBACK_FORBIDDEN`, `FEEDBACK_NOT_FOUND`, `CLASS_NOT_FOUND`, `USER_REGION_REQUIRED`, `REQUEST_VALIDATION_ERROR`, `AGENT_UNAVAILABLE`, `AGENT_TIMEOUT` + 인증 3종 |
| `GET/POST/DELETE /favorites` | `CLASS_NOT_FOUND`, `FAVORITE_ALREADY_EXISTS`, `FAVORITE_NOT_FOUND`, `REQUEST_VALIDATION_ERROR`, `DATABASE_ERROR` + 인증 3종 |
| `POST /internal/v1/predict` | `IMAGE_EMPTY`, `IMAGE_DECODE_FAILED`, `IMAGE_TOO_LARGE`, `IMAGE_TYPE_UNSUPPORTED`, `VISION_NO_MAIN_OBJECT`, `VISION_MODEL_NOT_READY`, `VISION_INFERENCE_ERROR` |

---

## 4. 오류가 아닌 "재촬영 필요" 코드 (HTTP 200)

| code | 반환 API | message | S3/DB 저장 여부 |
|---|---|---|---|
| `AI_NO_MAIN_OBJECT` | `/analyze` | 분류할 물체를 화면 중앙에 위치시킨 뒤 다시 촬영해주세요. | 저장 안 함(예측값 자체가 없음) |
| `AI_LOW_CONFIDENCE` | `/analyze` | 분석 신뢰도가 낮습니다. 물체를 중앙에 선명하게 두고 다시 촬영해주세요. | **저장함**(재학습 데이터 수집 목적, 미응답 상태로) |
| `AI_RECLASSIFY_FAILED` | `/feedback/{id}/not-in-list` | 재분류에 실패했습니다. 사진을 다시 촬영해 업로드해주세요. | RAG judge 루프가 재시도 횟수(`MAX_CLASSIFY_RETRIES`) 내에 유효한 분류를 찾지 못함 |

Frontend는 이 세 코드를 **오류 토스트가 아니라 안내 화면**으로 처리해야 합니다(자세한 화면 분기는
[06-user-flow.md](06-user-flow.md), [07-flowchart.md](07-flowchart.md) 참고).

---

## 5. Frontend 처리 가이드

| 수신 코드 | 권장 동작 |
|---|---|
| `AUTH_REQUIRED`, `AUTH_TOKEN_INVALID`, `AUTH_TOKEN_EXPIRED` | 토큰 폐기 후 로그인 화면 이동 |
| `USER_REGION_REQUIRED` | 지역 선택 화면으로 이동(어느 API에서 왔든 동일 처리) |
| `REQUEST_VALIDATION_ERROR` | `details[].field` 기준으로 폼 필드별 에러 표시 |
| `AI_LOW_CONFIDENCE` / `AI_NO_MAIN_OBJECT` / `AI_RECLASSIFY_FAILED` | 재촬영 안내 화면(오류 아님) |
| 그 외 | `message`를 그대로 노출 |

---

## 6. 참고

- 전체 API 계약: [10-api-specification.md](10-api-specification.md)
- 서비스 간 오류 전파 경로: [09-service-architecture.md](09-service-architecture.md)
- 원본 조사 문서: [`docs/API_SPEC.md`](../API_SPEC.md) §18
