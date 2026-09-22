# 데이터베이스 스키마

이 문서는 **실제 배포된 MySQL(Railway) 데이터베이스**를 `information_schema` +
`SHOW CREATE TABLE`로 직접 조회해서 작성했습니다. `backend/models/*.py`(SQLAlchemy
모델)는 이 실제 스키마와 항상 일치하도록 유지되고 있으니, 코드 타입까지 보고
싶으면 `backend/models/` 를, "지금 DB에 실제로 뭐가 있는지"를 보고 싶으면 이
문서를 보면 됩니다.

- DB 엔진: MySQL 8.0 (Railway 호스팅), 스토리지 엔진 InnoDB
- 문자셋/Collation: `utf8mb4` / `utf8mb4_unicode_ci` (이모지 포함 모든 유니코드 저장 가능)
- 연결 정보(호스트/포트/비밀번호)는 절대 이 문서에 적지 않습니다 — 루트 `.env`의
  `DATABASE_URL` 하나로만 관리합니다.
- 테이블 7개: `users`, `regions`, `waste_classes`, `images`, `feedback`,
  `feedback_candidates`, `favorites`
- Master 데이터(`regions`, `waste_classes`)는 서버 기동 시
  `backend/db/seed.py`가 `data/taxonomy/*.json`을 읽어 자동으로 채웁니다
  (멱등적 update-or-insert — 이미 있으면 갱신만 하고, 없으면 추가. **삭제는 절대
  하지 않음** — 그래서 taxonomy를 줄일 때는 사람이 직접 지워줘야 합니다).

> 작성 시점(2026-09-18) 기준 `waste_classes`는 **17개 클래스** 체계입니다.
> 기존 86개 소분류를 대분류는 그대로 두고 소분류만 병합한 결과이며, 자세한
> 매핑은 이 문서 끝의 "6. 최근 변경 이력"을 참고하세요.

---

## 1. ER 다이어그램

```mermaid
erDiagram
    REGIONS ||--o{ USERS : "거주 지역"
    USERS ||--o{ FEEDBACK : "분석 요청"
    USERS ||--o{ FAVORITES : "즐겨찾기"
    IMAGES ||--|| FEEDBACK : "분석된 이미지"
    WASTE_CLASSES ||--o{ FEEDBACK : "predicted_class_id"
    WASTE_CLASSES ||--o{ FEEDBACK : "final_class_id"
    WASTE_CLASSES ||--o{ FEEDBACK_CANDIDATES : "class_id"
    WASTE_CLASSES ||--o{ FAVORITES : "class_id"
    FEEDBACK ||--o{ FEEDBACK_CANDIDATES : "Top-K 후보"

    REGIONS {
        int region_id PK
        varchar sido_name
        varchar sgg_name
    }
    USERS {
        bigint user_id PK
        varchar email UK
        varchar password_hash
        int region_id FK "nullable"
    }
    WASTE_CLASSES {
        int class_id PK
        varchar major_category
        varchar minor_category
    }
    IMAGES {
        bigint image_id PK
        varchar s3_key
        varchar content_type
    }
    FEEDBACK {
        bigint feedback_id PK
        bigint user_id FK
        bigint image_id FK
        int predicted_class_id FK
        decimal predicted_score
        int final_class_id FK "nullable"
        bool is_correct "nullable"
        enum correction_source "nullable"
        enum review_status
    }
    FEEDBACK_CANDIDATES {
        bigint feedback_id PK_FK
        smallint candidate_rank PK
        int class_id FK
        decimal score
    }
    FAVORITES {
        bigint favorite_id PK
        bigint user_id FK
        int class_id FK
    }
```

---

## 2. `users` — 회원 정보

로그인 계정 + 현재 선택한 거주 지역.

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|---|---|---|---|---|
| `user_id` | `BIGINT UNSIGNED` | NO | AUTO_INCREMENT | PK. 사용자 고유 ID |
| `email` | `VARCHAR(255)` | NO | - | 로그인 이메일. **UNIQUE** |
| `password_hash` | `VARCHAR(255)` | NO | - | bcrypt 해시. 평문 저장 금지 |
| `region_id` | `INT UNSIGNED` | YES | NULL | 현재 선택 지역. 회원가입 직후 NULL(=지역 미선택) |
| `created_at` | `DATETIME` | NO | `CURRENT_TIMESTAMP` | 가입 시각 |
| `updated_at` | `DATETIME` | NO | `CURRENT_TIMESTAMP` (on update) | 마지막 수정 시각 |

**제약조건**
- PK: `user_id`
- UNIQUE: `uq_users_email` (`email`)
- FK: `fk_users_region` — `region_id` → `regions.region_id`, **ON DELETE SET NULL**
  (그 지역이 삭제되면 사용자는 지역 미선택 상태로 돌아감)

**인덱스**: `idx_users_region_id` (`region_id`)

---

## 3. `regions` — 지원 지역 Master

서울 25개 자치구 + 경기 31개 시·군, 총 56행. `backend/db/seed.py`가
`data/taxonomy/regions.json`에서 자동으로 채웁니다.

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|---|---|---|---|---|
| `region_id` | `INT UNSIGNED` | NO | (수동 지정) | PK. 현재 1~56 사용 |
| `sido_name` | `VARCHAR(50)` | NO | - | 시/도명 |
| `sgg_name` | `VARCHAR(50)` | NO | - | 시/군/구명 |
| `created_at` | `DATETIME` | NO | `CURRENT_TIMESTAMP` | Master 등록 시각 |

**제약조건**
- PK: `region_id`
- UNIQUE: `uq_regions_sido_sgg` (`sido_name`, `sgg_name`)
- **CHECK** `chk_regions_supported_sido`: `sido_name IN ('서울특별시', '경기도')`
  — 이 두 시/도 외에는 애초에 행 자체를 넣을 수 없음

---

## 4. `waste_classes` — 폐기물 분류 Master (YOLO ↔ 서비스 공유 계약)

**YOLO 모델의 class index와 정확히 같은 값**을 `class_id`로 사용합니다. Vision
서버도 Backend도 같은 `data/taxonomy/waste_classes.json`을 읽어 이 테이블을
채우므로, 모델이 뱉는 숫자와 이 테이블의 행이 항상 1:1로 맞아야 합니다(하나라도
어긋나면 엉뚱한 카테고리로 응답이 나감).

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|---|---|---|---|---|
| `class_id` | `INT UNSIGNED` | NO | (수동 지정) | PK. YOLO class index와 동일. 현재 **0~16** (17개) |
| `major_category` | `VARCHAR(100)` | NO | - | 대분류 (예: "고철류") |
| `minor_category` | `VARCHAR(100)` | NO | - | 소분류 (예: "고철") |

**제약조건**
- PK: `class_id`
- UNIQUE: `uq_waste_classes_major_minor` (`major_category`, `minor_category`) —
  같은 대/소분류 조합이 두 번 들어갈 수 없음

**현재 17개 전체 목록** (대분류 12개는 유지, 소분류만 병합한 결과)

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

---

## 5. `images` — 업로드 이미지 Object Key

실제 이미지 바이트는 S3(또는 로컬 개발 시 디스크)에 있고, 이 테이블은 그
위치(Object Key)만 저장합니다. Presigned URL이 아니라 **영구 Object Key**를
저장하는 점이 중요합니다(URL은 만료되지만 Key는 안 만료됨).

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|---|---|---|---|---|
| `image_id` | `BIGINT UNSIGNED` | NO | AUTO_INCREMENT | PK |
| `s3_key` | `VARCHAR(1024)` | NO | - | S3 Object Key (예: `feedback/2026/09/12/3-abc.jpg`) |
| `content_type` | `VARCHAR(50)` | NO | `'image/jpeg'` | 저장된 MIME 타입. 업로드 시 항상 재인코딩되므로 사실상 `image/jpeg` 또는 `image/webp`만 나옴 |

**제약조건**: PK `image_id`만 있고 FK는 없음(다른 테이블이 이 테이블을 참조).

---

## 6. `feedback` — AI 분석 결과 + 사용자 피드백

`/api/v1/analyze` 한 번 호출 = 이 테이블에 한 행. 이후 사용자가 "맞아요/틀렸어요"
피드백을 주면 같은 행을 UPDATE합니다(새 행을 만들지 않음).

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|---|---|---|---|---|
| `feedback_id` | `BIGINT UNSIGNED` | NO | AUTO_INCREMENT | PK |
| `user_id` | `BIGINT UNSIGNED` | NO | - | 분석 요청한 사용자 |
| `image_id` | `BIGINT UNSIGNED` | NO | - | 분석된 이미지. **UNIQUE**(이미지 1개 = feedback 1개) |
| `predicted_class_id` | `INT UNSIGNED` | NO | - | YOLO Top-1 예측 class_id |
| `predicted_score` | `DECIMAL(8,6)` | NO | - | Top-1 confidence, 0~1 |
| `final_class_id` | `INT UNSIGNED` | YES | NULL | 최종 확정된 class_id. 사용자가 아직 응답 안 했으면 NULL |
| `is_correct` | `TINYINT(1)` | YES | NULL | 최초 예측이 맞았는지. `NULL`(미응답)/`TRUE`/`FALSE` |
| `correction_source` | `ENUM('USER','GEMINI')` | YES | NULL | 누가 최종 class를 정정했는지 |
| `bbox_x1`/`y1`/`x2`/`y2` | `DECIMAL(8,6)` | NO | - | 메인 객체 bounding box, 0~1 정규화 좌표 |
| `model_version` | `VARCHAR(100)` | NO | - | 분석에 쓴 YOLO 체크포인트 버전 문자열 |
| `review_status` | `ENUM('PENDING','APPROVED','REJECTED')` | NO | `'PENDING'` | 이 피드백을 재학습 데이터로 쓸지 사람이 검수한 상태 |
| `created_at` | `DATETIME` | NO | `CURRENT_TIMESTAMP` | 분석 시각 |
| `updated_at` | `DATETIME` | NO | `CURRENT_TIMESTAMP` (on update) | 마지막 수정 시각(피드백 확정 시 갱신) |

**제약조건**
- PK: `feedback_id`
- UNIQUE: `image_id` (실제로는 인덱스지만 FK+애플리케이션 레벨에서 1:1 보장)
- FK: `fk_feedback_user` — `user_id` → `users.user_id`, **ON DELETE RESTRICT**
  (분석 이력이 있는 사용자는 삭제 못 함)
- FK: `fk_feedback_image` — `image_id` → `images.image_id`, **ON DELETE RESTRICT**
- FK: `fk_feedback_predicted_class` — `predicted_class_id` → `waste_classes.class_id`
- FK: `fk_feedback_final_class` — `final_class_id` → `waste_classes.class_id`
- **CHECK** `chk_feedback_predicted_score`: `0 <= predicted_score <= 1`
- **CHECK** `chk_feedback_bbox`: 4개 좌표 모두 0~1 사이 **그리고** `x1 < x2`,
  `y1 < y2` (찌그러지거나 뒤집힌 박스는 애초에 저장 불가)
- **CHECK** `chk_feedback_result_state` — 아래 3가지 조합만 허용(가장 중요한
  비즈니스 규칙):
  1. **미응답**: `is_correct IS NULL` AND `final_class_id IS NULL` AND
     `correction_source IS NULL`
  2. **"맞아요" 확인**: `is_correct = TRUE` AND `final_class_id = predicted_class_id`
     AND `correction_source IS NULL`
  3. **정정됨**: `is_correct = FALSE` AND `final_class_id IS NOT NULL` AND
     `correction_source IS NOT NULL` (USER 또는 GEMINI)
- **CHECK** `chk_feedback_review_state`: `review_status = 'APPROVED'`이면
  반드시 `final_class_id IS NOT NULL` (사용자 확인이 안 끝난 데이터는 재학습
  데이터로 승인할 수 없음)

**인덱스**: `idx_feedback_user_id`, `idx_feedback_image_id`,
`idx_feedback_predicted_class_id`, `idx_feedback_final_class_id`,
`idx_feedback_is_correct`, `idx_feedback_correction_source`,
`idx_feedback_review_status`, `idx_feedback_created_at`,
`idx_feedback_user_created_at`(`user_id`,`created_at`),
`idx_feedback_predicted_correct`(`predicted_class_id`,`is_correct`)

---

## 7. `feedback_candidates` — 분석 당시 Top-K 후보 스냅샷

`/analyze` 응답에 담겼던 Top-K 후보 목록을 그대로 저장. **분석 시점 스냅샷**이라
이후 사용자가 무엇을 선택하든 이 테이블 자체는 변하지 않습니다(섹션 9.2/9.3
규칙).

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|---|---|---|---|---|
| `feedback_id` | `BIGINT UNSIGNED` | NO | - | 부모 feedback. **PK의 일부** |
| `candidate_rank` | `SMALLINT UNSIGNED` | NO | - | 후보 순위, 1부터 시작. **PK의 일부** |
| `class_id` | `INT UNSIGNED` | NO | - | 후보 class_id |
| `score` | `DECIMAL(8,6)` | NO | - | 후보 score, 0~1 |

**제약조건**
- **복합 PK**: (`feedback_id`, `candidate_rank`)
- UNIQUE: `uq_feedback_candidates_feedback_class` (`feedback_id`, `class_id`) —
  같은 분석에 같은 class_id가 후보로 두 번 들어갈 수 없음
- FK: `fk_feedback_candidates_feedback` — `feedback_id` → `feedback.feedback_id`,
  **ON DELETE CASCADE** (feedback이 지워지면 후보들도 같이 삭제)
- FK: `fk_feedback_candidates_class` — `class_id` → `waste_classes.class_id`
- **CHECK** `chk_feedback_candidates_rank`: `candidate_rank >= 1`
- **CHECK** `chk_feedback_candidates_score`: `0 <= score <= 1`

**인덱스**: `idx_feedback_candidates_class_id` (`class_id`)

---

## 8. `favorites` — 사용자 즐겨찾기

특정 폐기물 분류를 즐겨찾기에 등록.

| 컬럼 | 타입 | NULL | 기본값 | 설명 |
|---|---|---|---|---|
| `favorite_id` | `BIGINT UNSIGNED` | NO | AUTO_INCREMENT | PK |
| `user_id` | `BIGINT UNSIGNED` | NO | - | 즐겨찾기 소유자 |
| `class_id` | `INT UNSIGNED` | NO | - | 즐겨찾기한 class_id |
| `created_at` | `DATETIME` | NO | `CURRENT_TIMESTAMP` | 등록 시각 |

**제약조건**
- PK: `favorite_id`
- UNIQUE: `uq_favorites_user_class` (`user_id`, `class_id`) — 같은 사용자가
  같은 class를 두 번 즐겨찾기할 수 없음
- FK: `fk_favorites_user` — `user_id` → `users.user_id`, **ON DELETE CASCADE**
  (사용자 삭제 시 즐겨찾기도 같이 삭제)
- FK: `fk_favorites_class` — `class_id` → `waste_classes.class_id`

**인덱스**: `idx_favorites_class_id` (`class_id`)

---

## 9. 삭제 정책(ON DELETE) 한눈에 보기

| FK | 부모가 삭제되면 |
|---|---|
| `users.region_id → regions` | `SET NULL` (지역 미선택으로) |
| `favorites.user_id → users` | `CASCADE` (같이 삭제) |
| `feedback.user_id → users` | `RESTRICT` (사용자 못 지움) |
| `feedback.image_id → images` | `RESTRICT` (이미지 못 지움) |
| `feedback_candidates.feedback_id → feedback` | `CASCADE` (같이 삭제) |
| `favorites.class_id`, `feedback.predicted_class_id`, `feedback.final_class_id`, `feedback_candidates.class_id → waste_classes` | `RESTRICT`(기본값) — 참조 중인 class는 못 지움 |

---

## 10. 최근 변경 이력

**2026-09-18: 폐기물 소분류 86개 → 17개 병합**
- 대분류 12개(고철류/나무/도기류/비닐/스티로폼/유리병/의류/종이류/캔류/페트병/
  플라스틱류/형광등)는 그대로 유지
- 소분류만 대폭 병합 (예: 고철류의 골프채/기타/전기프라이팬/주전자/철옷걸이/
  프라이팬 → 전부 "고철" 하나로)
- `data/train100val/`의 원본 라벨(JSON) + 이미지도 실제로 물리적으로 재배치해
  새 소분류 폴더 구조로 맞춤 (18,589개 파일, 유실/불일치 0건 확인)
- 기존 `waste_classes`가 idempotent seed 로직(삭제는 안 하고 추가/갱신만 함)
  때문에 옛 class_id(17~85)가 남아있었던 적이 있어 수동으로 정리함 — taxonomy를
  줄이는 마이그레이션에서는 `seed_waste_classes()`만으로는 부족하고, 사라진
  class_id를 참조하는 기존 행 정리까지 수동으로 해줘야 함

---

## 11. 참고

- Master 데이터 원본: `data/taxonomy/regions.json`, `data/taxonomy/waste_classes.json`
- 시딩 코드: `backend/db/seed.py`, `backend/db/taxonomy_loader.py`
- SQLAlchemy 모델: `backend/models/*.py`
- API 계약(요청/응답 필드) 문서: `docs/API_SPEC.md`
- curl 테스트 명령 모음: `docs/API_TEST_COMMANDS.md`
