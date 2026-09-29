# 데이터 명세서

**버전** v1.0 · **기준일** 2026-09-28

이 문서는 recycling_ssg(분리쏙)가 다루는 데이터를 세 종류로 나눠 정의합니다.

1. **관계형 데이터** — MySQL 7개 테이블 (컬럼 단위 상세)
2. **마스터/참조 데이터** — JSON 파일로 관리되는 분류 체계·지역·규정 텍스트
3. **비정형/외부 데이터** — S3 객체, JWT 페이로드, 벡터 임베딩

ERD(관계도)는 [12-erd.md](12-erd.md), API 요청/응답 필드는 [10-api-specification.md](10-api-specification.md)를 참고하세요.

---

## 1. 관계형 데이터 (MySQL, 7 테이블)

DB 엔진 MySQL 8.0(Railway) / InnoDB / `utf8mb4` · `utf8mb4_unicode_ci`.
`created_at`/`updated_at`은 애플리케이션이 **KST(UTC+9)** 로 저장하고(`backend/models/timestamps.py::now_kst()`,
커넥션 단위 `SET time_zone='+09:00'`), API 응답 시점에 UTC `...Z` 형식으로 환산합니다(`backend/schemas/common.py`).

### 1.1 `users`

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|---|---|---|---|---|
| `user_id` | `BIGINT UNSIGNED` | NO | AUTO_INCREMENT | PK |
| `email` | `VARCHAR(255)` | NO | - | 로그인 이메일. UNIQUE |
| `password_hash` | `VARCHAR(255)` | NO | - | bcrypt 해시. 평문 저장 금지 |
| `region_id` | `INT UNSIGNED` | YES | NULL | 현재 선택 지역. 가입 직후 NULL |
| `created_at` / `updated_at` | `DATETIME` | NO | `CURRENT_TIMESTAMP` | KST 저장 |

제약: PK `user_id` · UNIQUE `email` · FK `region_id → regions.region_id` (`ON DELETE SET NULL`) · 인덱스 `region_id`

### 1.2 `regions` — 지원 지역 Master (56행 고정)

| 컬럼 | 타입 | NULL | 설명 |
|---|---|---|---|
| `region_id` | `INT UNSIGNED` | NO | PK, 1~56 |
| `sido_name` | `VARCHAR(50)` | NO | `서울특별시` \| `경기도`만 허용(CHECK) |
| `sgg_name` | `VARCHAR(50)` | NO | 시/군/구명 |
| `created_at` | `DATETIME` | NO | Master 등록 시각 |

제약: PK `region_id` · UNIQUE `(sido_name, sgg_name)` · CHECK `sido_name IN ('서울특별시','경기도')`

### 1.3 `waste_classes` — 폐기물 분류 Master (17행 고정, YOLO ↔ 서비스 공유 계약)

| class_id | 대분류 | 소분류 |
|---|---|---|
| 0 | 고철류 | 고철 |
| 1 | 고철류 | 비철금속 |
| 2 | 나무 | 나무 |
| 3 | 도기류 | 도기 |
| 4 | 비닐 | 비닐 |
| 5 | 스티로폼 | 스티로폼 |
| 6 | 유리병 | 유리병 |
| 7 | 의류 | 의류 |
| 8 | 종이류 | 책 |
| 9 | 종이류 | 박스류 |
| 10 | 종이류 | 신문지 |
| 11 | 종이류 | 종이 |
| 12 | 캔류 | 캔 |
| 13 | 페트병 | 페트병 |
| 14 | 플라스틱류 | 플라스틱 |
| 15 | 플라스틱류 | 장난감 |
| 16 | 형광등 | 형광등 |

제약: PK `class_id`(= YOLO class index) · UNIQUE `(major_category, minor_category)`

> **단일 소스 원칙**: 이 표는 `data/taxonomy/waste_classes.json`이 원본이며, Vision 서버(추론 출력),
> Backend DB(`waste_classes` 테이블), Frontend(`src/constants/wasteCategories.ts`, 수동 동기화) 세 곳이
> 모두 이 17개 값을 공유합니다. 하나라도 어긋나면 `class_id`가 가리키는 대상이 서로 달라집니다.

### 1.4 `images` — 업로드 이미지 Object Key

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|---|---|---|---|---|
| `image_id` | `BIGINT UNSIGNED` | NO | AUTO_INCREMENT | PK |
| `s3_key` | `VARCHAR(1024)` | NO | - | 영구 Object Key (Presigned URL 아님) |
| `content_type` | `VARCHAR(50)` | NO | `'image/jpeg'` | 재인코딩 후 실제 MIME |

제약: PK만 존재, FK 없음(다른 테이블이 참조하는 쪽)

### 1.5 `feedback` — AI 분석 결과 + 사용자 피드백 (분석 1건 = 1행)

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|---|---|---|---|---|
| `feedback_id` | `BIGINT UNSIGNED` | NO | AUTO_INCREMENT | PK |
| `user_id` | `BIGINT UNSIGNED` | NO | - | FK → `users` |
| `image_id` | `BIGINT UNSIGNED` | NO | - | FK → `images`, UNIQUE(1:1) |
| `predicted_class_id` | `INT UNSIGNED` | NO | - | YOLO Top-1 class_id |
| `predicted_score` | `DECIMAL(8,6)` | NO | - | Top-1 confidence (0~1) |
| `final_class_id` | `INT UNSIGNED` | YES | NULL | 최종 확정 class_id |
| `is_correct` | `TINYINT(1)` | YES | NULL | NULL(미응답) / TRUE / FALSE |
| `correction_source` | `ENUM('USER','GEMINI')` | YES | NULL | 정정 주체 |
| `bbox_x1`/`y1`/`x2`/`y2` | `DECIMAL(8,6)` | NO | - | 메인 객체 bbox, 0~1 정규화 XYXY |
| `model_version` | `VARCHAR(100)` | NO | - | 추론에 쓴 YOLO 체크포인트 식별자 |
| `review_status` | `ENUM('PENDING','APPROVED','REJECTED')` | NO | `'PENDING'` | 재학습 데이터 승인 상태 |
| `created_at` / `updated_at` | `DATETIME` | NO | `CURRENT_TIMESTAMP` | KST 저장 |

**CHECK 제약 (핵심 비즈니스 규칙)**

| 이름 | 내용 |
|---|---|
| `chk_feedback_predicted_score` | `0 <= predicted_score <= 1` |
| `chk_feedback_bbox` | 4개 좌표 0~1 범위 **및** `x1<x2`, `y1<y2` |
| `chk_feedback_result_state` | 아래 3가지 조합만 허용 |
| `chk_feedback_review_state` | `review_status='APPROVED'` ⇒ `final_class_id IS NOT NULL` |

`chk_feedback_result_state`의 3가지 허용 조합:

| 상태 | `is_correct` | `final_class_id` | `correction_source` |
|---|---|---|---|
| 미응답 | NULL | NULL | NULL |
| "맞아요" 확인 | TRUE | `predicted_class_id`와 동일 | NULL |
| 정정됨 | FALSE | NOT NULL | `USER` 또는 `GEMINI` |

FK: `user_id→users`(RESTRICT), `image_id→images`(RESTRICT), `predicted_class_id`/`final_class_id→waste_classes`(RESTRICT)
인덱스: `user_id`, `image_id`, `predicted_class_id`, `final_class_id`, `is_correct`, `correction_source`, `review_status`,
`created_at`, `(user_id,created_at)`, `(predicted_class_id,is_correct)`

### 1.6 `feedback_candidates` — 분석 시점 Top-K 후보 스냅샷

| 컬럼 | 타입 | NULL | 설명 |
|---|---|---|---|
| `feedback_id` | `BIGINT UNSIGNED` | NO | 복합 PK 일부, FK → `feedback` (CASCADE) |
| `candidate_rank` | `SMALLINT UNSIGNED` | NO | 복합 PK 일부, 1부터 시작 |
| `class_id` | `INT UNSIGNED` | NO | FK → `waste_classes` |
| `score` | `DECIMAL(8,6)` | NO | 0~1 |

제약: 복합 PK `(feedback_id, candidate_rank)` · UNIQUE `(feedback_id, class_id)` ·
CHECK `candidate_rank>=1`, `0<=score<=1` · **분석 시점 스냅샷이라 이후 불변**

### 1.7 `favorites` — 사용자 즐겨찾기

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|---|---|---|---|---|
| `favorite_id` | `BIGINT UNSIGNED` | NO | AUTO_INCREMENT | PK |
| `user_id` | `BIGINT UNSIGNED` | NO | - | FK → `users` (CASCADE) |
| `class_id` | `INT UNSIGNED` | NO | - | FK → `waste_classes` |
| `created_at` | `DATETIME` | NO | `CURRENT_TIMESTAMP` | 등록 시각 |

제약: PK `favorite_id` · UNIQUE `(user_id, class_id)`

### 1.8 삭제 정책(ON DELETE) 요약

| FK | 부모 삭제 시 |
|---|---|
| `users.region_id → regions` | `SET NULL` |
| `favorites.user_id → users` | `CASCADE` |
| `feedback.user_id → users` | `RESTRICT` |
| `feedback.image_id → images` | `RESTRICT` |
| `feedback_candidates.feedback_id → feedback` | `CASCADE` |
| `*.class_id → waste_classes` (전체) | `RESTRICT` |

---

## 2. 마스터/참조 데이터 (JSON 파일)

| 파일 | 용도 | 소비 주체 |
|---|---|---|
| `data/taxonomy/waste_classes.json` | 17개 폐기물 분류(class_id/대분류/소분류) 단일 소스 | Vision(추론 클래스), Backend(`waste_classes` 시드), Frontend(수동 미러링) |
| `data/taxonomy/regions.json` | 56개 지원 지역(서울 25구 + 경기 31시·군) | Backend(`regions` 시드) |
| `rag/data/metadata/waste_sorting_dictionary_classified.json` | 전국 공통 분리배출 품목/방법 사전(법령 별표 원문 기반) | RAG 서비스 벡터 임베딩 원본(`national_law` 문서) |
| `rag/data/metadata/gyeonggi_region_exceptions_processed.json` | 경기도 시·군별 배출 예외 규정 (이미 `{page_content, metadata}` Document 형태로 가공됨) | RAG 서비스 벡터 임베딩 원본(`region_exception` 문서) |
| `rag/data/raw/[별표 1] 분리수거대상 재활용가능자원의 품목 및 분리배출요령...pdf` | 위 두 JSON의 원본 근거 법령 PDF (사람이 읽는 용도) | 오프라인 전처리 입력. 런타임에는 사용되지 않음 |

> `waste_sorting_dictionary_classified.json` / `gyeonggi_region_exceptions_processed.json`은
> **오프라인 전처리 산출물**입니다 — 런타임에 PDF를 파싱하지 않고, 사전에 구조화된 이 JSON을
> `rag/src/ingestion/ingest.py`가 읽어 Pinecone에 업서트합니다. 자세한 흐름은
> [09-service-architecture.md](09-service-architecture.md)를 참고하세요.

---

## 3. 비정형·외부 데이터

### 3.1 S3 (또는 로컬 디스크) — 이미지 원본

- 저장 형식: 항상 재인코딩됨(`IMAGE_OUTPUT_FORMAT`, 기본 `jpeg`, 대안 `webp`), 긴 변 `IMAGE_MAX_DIMENSION`(기본 1920px) 이하로 축소(비율 유지, 확대 안 함), 품질 `IMAGE_OUTPUT_QUALITY`(기본 85)
- Object Key 예시: `feedback/2026/09/12/3-abc123.jpg` (연/월/일 파티셔닝 + `feedback_id` 또는 임시 식별자 + 랜덤 suffix)
- DB에는 **Key만 저장**(`images.s3_key`), Presigned URL은 만료되므로 저장하지 않음
- `STORAGE_BACKEND=local`일 때는 `LOCAL_STORAGE_DIR`(기본 `./.local_storage`) 아래 동일한 Key 구조로 저장 — API/DB 계약은 완전히 동일

### 3.2 JWT 페이로드

| 필드 | 의미 |
|---|---|
| `sub` | `user_id` (문자열) |
| `iat` | 발급 시각 |
| `exp` | 만료 시각 (`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, 기본 1440분) |

알고리즘 `HS256`, 서명 키 `JWT_SECRET_KEY`. 로그아웃은 Stateless이므로 서버가 토큰을 무효화하지 않고
Frontend가 `localStorage`(`bs_token`)에서 폐기합니다.

### 3.3 벡터 임베딩 (Pinecone)

| 항목 | 값 |
|---|---|
| 인덱스명 | `recycling-ssg` |
| 임베딩 모델 | Upstage `solar-embedding-2-passage` |
| 문서 타입 | `doc_type="national_law"` (전국 공통), `doc_type="region_exception"` (경기도 예외) |
| 메타데이터 필드 | `major_category`, `minor_category`, `item`, `method`, `region`(경기 시·군), `exception_type`, `source`/`source_url` |
| 조회 방식 | 메타데이터 필터 + 벡터 유사도(semantic search), k=3~10 |

자세한 조회 로직(`rag/src/agents/rule_lookup.py`)은 [09-service-architecture.md](09-service-architecture.md)에서 다룹니다.

### 3.4 Vision 추론 산출물 (비영속)

| 필드 | 의미 |
|---|---|
| `class_id`, `score` | Top-1 예측 |
| `candidate_scores[]` | Top-1 제외 나머지 후보 (최대 `VISION_TOP_K - 1`, 기본 4개) |
| `internal_meta.bbox` | 메인 객체 bbox, 0~1 정규화 XYXY → `feedback.bbox_*`로 영속화 |
| `internal_meta.model_version` | 체크포인트 식별자 → `feedback.model_version`으로 영속화 |
| `internal_meta.inference_ms` | 추론 소요 시간 (로그용, 미영속) |

---

## 4. 저장하지 않는 데이터 (명시적 비저장 정책)

| 데이터 | 사유 |
|---|---|
| 평문 비밀번호 | bcrypt 해시만 저장 |
| 채팅 메시지/응답 | `/api/v1/chat`은 Stateless 요구사항 |
| `request_id` | 응답 헤더로만 내려주고 DB에는 저장하지 않음(로그에만 남음) |
| 행정안전부 API 응답 캐시 | 조회 시마다 실시간 호출(배출요일이 변경될 수 있어 캐시하지 않음) |
| `feedback`에 지역 정보 | 사용자의 "현재" 지역을 그때그때 `users.region_id`로 조회 |

---

## 5. 참고

- ERD: [12-erd.md](12-erd.md)
- API 필드 계약: [10-api-specification.md](10-api-specification.md)
- 원본 조사 문서: [`docs/DATABASE_SCHEMA.md`](../DATABASE_SCHEMA.md)
- 시딩 코드: `backend/db/seed.py`, `backend/db/taxonomy_loader.py`
