/* ================================================================================================
   recycling_ssg MySQL Schema - FINAL (v8, 2026-09-29)
   ------------------------------------------------------------------------------------------------
   작성 근거
   - 실제 배포된 MySQL(Railway) 데이터베이스를 information_schema + SHOW CREATE TABLE로 직접 조회해
     작성한 docs/DATABASE_SCHEMA.md 를 1차 소스로 사용.
   - 첨부해주신 recycling_ssg_erdcloud_exact_v7.sql (이하 "v7")을 구조 기준선으로 참고.
   - backend/models/*.py (SQLAlchemy) 및 backend/db/seed.py, data/taxonomy/*.json 대조.

   v7 대비 변경사항 (실제 운영 DB와 다르던 부분을 이번 파일에서 바로잡음)
   ------------------------------------------------------------------------------------------------
   1) images 테이블에 content_type VARCHAR(50) NOT NULL DEFAULT 'image/jpeg' 컬럼 추가.
      - 업로드 시 image_processing 서비스가 재인코딩하므로, Gemini re-classify 시 올바른
        mime_type을 알려주기 위해 실제 저장된 포맷을 함께 저장한다 (jpeg 또는 webp만 나옴).
   2) feedback.image_id 를 (기존 비-UNIQUE KEY) -> UNIQUE 로 변경.
      - 이미지 1장 = feedback 1건의 1:1 관계를 DB 레벨에서도 강제한다(analyze.py가 실제로
        이미지 1개당 feedback을 정확히 1개만 만든다).
   3) waste_classes 는 구조는 v7과 동일하지만, 실제 데이터가 86개 세부 클래스가 아니라
      "2026-09-18 소분류 병합" 이후 17개(class_id 0~16) 로 운영 중이다. 대분류 12개는 유지,
      소분류만 병합됨. 아래 목업 데이터가 실제 운영 값과 동일하다.
   4) reviewed_at, chat_sessions/chat_messages 는 v7과 마찬가지로 이번에도 제외
      (실제 DB에도 없음. 채팅은 세션에 저장하지 않는 stateless 기능 - backend/agent/service.py 참고).
   5) created_at/updated_at 은 KST(UTC+9)로 저장된다 (2026-09-22 변경).
      - ORM INSERT/UPDATE: models/timestamps.py::now_kst() 가 Python에서 KST를 직접 채움.
      - ORM을 거치지 않는 직접 SQL INSERT(이 파일의 목업 데이터 등): DEFAULT CURRENT_TIMESTAMP
        폴백이 쓰이므로, 아래처럼 커넥션의 session time_zone을 +09:00으로 맞추고 사용할 것.
      - API 응답은 이 KST 값을 UTC로 환산해 `...Z` 형식으로 내려가므로 API 계약에는 영향 없음.
      이 파일에서는 목업 데이터의 created_at/updated_at을 전부 명시적 리터럴로 넣었으므로
      session time_zone 설정과 무관하게 값이 고정된다 (아래 SET 문은 그래도 관례상 맞춰둔다).

   ENGINE / CHARSET
   ------------------------------------------------------------------------------------------------
   - MySQL 8.0, ENGINE=InnoDB, DEFAULT CHARSET=utf8mb4, COLLATE=utf8mb4_unicode_ci
   - 테이블 7개: regions, waste_classes, users, images, feedback, feedback_candidates, favorites

   사용 방법
   ------------------------------------------------------------------------------------------------
   mysql -u <user> -p <password> < recycling_ssg_mysql_schema_final.sql
   (또는 MySQL Workbench 등에서 그대로 실행. DB가 이미 있으면 CREATE DATABASE 줄만 건너뛰어도 됨)
   ================================================================================================ */

SET NAMES utf8mb4;
SET time_zone = '+09:00';

CREATE DATABASE IF NOT EXISTS recycling_ssg
    DEFAULT CHARACTER SET utf8mb4
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE recycling_ssg;


/* ================================================================================================
   0. 초기화 (재생성용) - 기존 테이블이 있으면 자식 -> 부모 순서로 전부 삭제한다.
   처음 DB를 만드는 경우에는 그냥 실행해도 무해하다 (IF EXISTS).
   ================================================================================================ */

SET FOREIGN_KEY_CHECKS = 0;

DROP TABLE IF EXISTS feedback_candidates;
DROP TABLE IF EXISTS favorites;
DROP TABLE IF EXISTS feedback;
DROP TABLE IF EXISTS images;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS waste_classes;
DROP TABLE IF EXISTS regions;

SET FOREIGN_KEY_CHECKS = 1;


/* ================================================================================================
   1. regions - 서비스 지원 지역 Master (서울 25개 자치구 + 경기 31개 시/군, 총 56행)
   ------------------------------------------------------------------------------------------------
   backend/db/seed.py 가 서버 기동 시 data/taxonomy/regions.json 으로 idempotent upsert 한다.
   ================================================================================================ */

CREATE TABLE regions (

    region_id INT UNSIGNED NOT NULL
        COMMENT '지역 고유 ID. INT UNSIGNED, PK, 현재 1~56 사용',

    sido_name VARCHAR(50) NOT NULL
        COMMENT '시/도명. 지원값: 서울특별시/경기도',

    sgg_name VARCHAR(50) NOT NULL
        COMMENT '시/군/구명. 서울 25개 자치구 및 경기 31개 시군',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        COMMENT '지역 Master 등록 시각 (KST)',

    PRIMARY KEY (region_id),

    UNIQUE KEY uq_regions_sido_sgg (sido_name, sgg_name),

    CONSTRAINT chk_regions_supported_sido
        CHECK (sido_name IN ('서울특별시', '경기도'))

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='서비스 지원 지역 Master: 서울 25개 자치구 + 경기 31개 시군';


/* ================================================================================================
   2. waste_classes - 폐기물 분류 Master (YOLO class_id와 1:1로 맞아야 함)
   ------------------------------------------------------------------------------------------------
   2026-09-18 기준 17개(class_id 0~16) 로 운영 중. 대분류 12개는 유지, 소분류만 병합.
   backend/db/seed.py 가 data/taxonomy/waste_classes.json 으로 idempotent upsert 한다
   (삭제는 하지 않으므로 taxonomy를 줄일 때는 사람이 직접 옛 class_id 잔재를 정리해야 함).
   ================================================================================================ */

CREATE TABLE waste_classes (

    class_id INT UNSIGNED NOT NULL
        COMMENT 'YOLO/서비스 공통 Class ID. 현재 0~16 (17개)',

    major_category VARCHAR(100) NOT NULL
        COMMENT '폐기물 대분류. 예: 고철류, 플라스틱류',

    minor_category VARCHAR(100) NOT NULL
        COMMENT '폐기물 소분류. 예: 고철, 페트병',

    PRIMARY KEY (class_id),

    UNIQUE KEY uq_waste_classes_major_minor (major_category, minor_category)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='YOLO 폐기물 Class Master (현재 17개). major/minor는 이 테이블에서만 관리';


/* ================================================================================================
   3. users - 회원 정보 및 현재 선택 지역
   ================================================================================================ */

CREATE TABLE users (

    user_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT
        COMMENT '사용자 고유 ID',

    email VARCHAR(255) NOT NULL
        COMMENT '로그인 이메일. UNIQUE',

    password_hash VARCHAR(255) NOT NULL
        COMMENT 'bcrypt 해시. 평문 저장 금지',

    region_id INT UNSIGNED NULL
        COMMENT '사용자의 현재 선택 지역 ID. 회원가입 직후 NULL 가능',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        COMMENT '회원가입 시각 (KST)',

    updated_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
        COMMENT '회원정보 마지막 수정 시각 (KST)',

    PRIMARY KEY (user_id),

    UNIQUE KEY uq_users_email (email),

    KEY idx_users_region_id (region_id),

    CONSTRAINT fk_users_region
        FOREIGN KEY (region_id)
        REFERENCES regions(region_id)
        ON DELETE SET NULL

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='회원 정보 및 현재 선택 지역';


/* ================================================================================================
   4. images - AWS S3 이미지 Object Key 저장
   ------------------------------------------------------------------------------------------------
   실제 파일은 S3(or 로컬 개발 시 디스크)에 저장, DB에는 영구 Object Key만 저장한다
   (Presigned URL은 만료되므로 저장하지 않음). user_id/created_at은 두지 않는다 -- 소유권은
   feedback.user_id 로 추적한다 (/analyze 흐름에서 이미지 1개당 feedback이 정확히 1개 생성되므로
   images가 주인 없이 남는 경우가 없다).
   ================================================================================================ */

CREATE TABLE images (

    image_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT
        COMMENT '이미지 고유 ID',

    s3_key VARCHAR(1024) NOT NULL
        COMMENT 'AWS S3 Object Key. 예: feedback/2026/09/11/550e8400-...jpg',

    content_type VARCHAR(50) NOT NULL DEFAULT 'image/jpeg'
        COMMENT '실제 저장된 MIME 타입. 업로드 시 항상 재인코딩되어 image/jpeg 또는 image/webp만 나옴',

    PRIMARY KEY (image_id)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='AWS S3 이미지 Object Key 저장';


/* ================================================================================================
   5. feedback - AI 분석 결과 + 사용자 피드백 + 재학습 검수 상태
   ------------------------------------------------------------------------------------------------
   /api/v1/analyze 호출 1번 = 이 테이블 1행 생성. 이후 사용자의 "맞음/틀림" 응답으로 같은 행을
   UPDATE 한다 (새 행을 만들지 않음).

   최초 INSERT 상태: final_class_id/is_correct/correction_source 전부 NULL, review_status=PENDING
   "맞습니다": final_class_id=predicted_class_id, is_correct=TRUE, correction_source=NULL
   "아닙니다"->후보 선택: final_class_id=선택 class, is_correct=FALSE, correction_source=USER
   "여기에 없어요"->RAG/Gemini 재분류: final_class_id=재분류 결과, is_correct=FALSE, correction_source=GEMINI
   ================================================================================================ */

CREATE TABLE feedback (

    feedback_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT
        COMMENT 'AI 분석 및 사용자 피드백 고유 ID',

    user_id BIGINT UNSIGNED NOT NULL
        COMMENT '분석 요청 사용자. FK -> users.user_id',

    image_id BIGINT UNSIGNED NOT NULL
        COMMENT '분석 이미지. FK -> images.image_id. UNIQUE (이미지 1개 = feedback 1개)',

    predicted_class_id INT UNSIGNED NOT NULL
        COMMENT 'YOLO 최초 Top-1 예측 Class ID',

    predicted_score DECIMAL(8,6) NOT NULL
        COMMENT 'YOLO 최초 Top-1 class score. 0~1',

    final_class_id INT UNSIGNED NULL
        COMMENT '최종 확정 Class ID. 사용자 미응답이면 NULL',

    is_correct BOOLEAN NULL
        COMMENT '최초 YOLO 예측 정답 여부. TRUE/FALSE/NULL(미응답)',

    correction_source ENUM('USER', 'GEMINI') NULL
        COMMENT 'Class 수정 출처. USER/GEMINI/NULL',

    bbox_x1 DECIMAL(8,6) NOT NULL COMMENT '메인 객체 BBox x1. normalized 0~1',
    bbox_y1 DECIMAL(8,6) NOT NULL COMMENT '메인 객체 BBox y1. normalized 0~1',
    bbox_x2 DECIMAL(8,6) NOT NULL COMMENT '메인 객체 BBox x2. normalized 0~1',
    bbox_y2 DECIMAL(8,6) NOT NULL COMMENT '메인 객체 BBox y2. normalized 0~1',

    model_version VARCHAR(100) NOT NULL
        COMMENT '분석에 사용한 YOLO 모델/가중치 버전',

    review_status ENUM('PENDING', 'APPROVED', 'REJECTED')
        NOT NULL DEFAULT 'PENDING'
        COMMENT '재학습 데이터 검수 상태 (현재 앱 로직에서는 세팅하지 않음 - 기본값 PENDING으로 쌓이고, 추후 관리자 도구/수동 SQL로 APPROVED/REJECTED 갱신 예정)',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        COMMENT 'AI 분석/feedback 생성 시각 (KST)',

    updated_at DATETIME NOT NULL
        DEFAULT CURRENT_TIMESTAMP
        ON UPDATE CURRENT_TIMESTAMP
        COMMENT 'feedback 마지막 수정 시각 (KST)',

    PRIMARY KEY (feedback_id),

    /* ------------------------- INDEX ------------------------- */
    UNIQUE KEY idx_feedback_image_id (image_id),
    KEY idx_feedback_user_id (user_id),
    KEY idx_feedback_predicted_class_id (predicted_class_id),
    KEY idx_feedback_final_class_id (final_class_id),
    KEY idx_feedback_is_correct (is_correct),
    KEY idx_feedback_correction_source (correction_source),
    KEY idx_feedback_review_status (review_status),
    KEY idx_feedback_created_at (created_at),
    KEY idx_feedback_user_created_at (user_id, created_at),
    KEY idx_feedback_predicted_correct (predicted_class_id, is_correct),

    /* ------------------------- FOREIGN KEY ------------------------- */
    CONSTRAINT fk_feedback_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_feedback_image
        FOREIGN KEY (image_id) REFERENCES images(image_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_feedback_predicted_class
        FOREIGN KEY (predicted_class_id) REFERENCES waste_classes(class_id),

    CONSTRAINT fk_feedback_final_class
        FOREIGN KEY (final_class_id) REFERENCES waste_classes(class_id),

    /* ------------------------- CHECK ------------------------- */
    CONSTRAINT chk_feedback_predicted_score
        CHECK (predicted_score >= 0 AND predicted_score <= 1),

    CONSTRAINT chk_feedback_bbox
        CHECK (
            bbox_x1 >= 0 AND bbox_x1 <= 1
            AND bbox_y1 >= 0 AND bbox_y1 <= 1
            AND bbox_x2 >= 0 AND bbox_x2 <= 1
            AND bbox_y2 >= 0 AND bbox_y2 <= 1
            AND bbox_x1 < bbox_x2
            AND bbox_y1 < bbox_y2
        ),

    CONSTRAINT chk_feedback_result_state
        CHECK (
            (is_correct IS NULL AND final_class_id IS NULL AND correction_source IS NULL)
            OR (is_correct = TRUE AND final_class_id = predicted_class_id AND correction_source IS NULL)
            OR (is_correct = FALSE AND final_class_id IS NOT NULL AND correction_source IS NOT NULL)
        ),

    CONSTRAINT chk_feedback_review_state
        CHECK (review_status <> 'APPROVED' OR final_class_id IS NOT NULL)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='YOLO 최초 예측, 사용자/Gemini 최종 피드백, normalized BBox, 재학습 검수 상태 저장';


/* ================================================================================================
   6. feedback_candidates - 분석 당시 제시한 Top-K 후보 snapshot (Top-1 제외한 나머지)
   ------------------------------------------------------------------------------------------------
   candidate_rank 는 predicted_class_id(Top-1)를 제외한 "다른 후보"들의 순위다 (1부터 시작).
   분석 시점 스냅샷이므로 이후 사용자의 선택과 무관하게 이 테이블 자체는 변하지 않는다.
   ================================================================================================ */

CREATE TABLE feedback_candidates (

    feedback_id BIGINT UNSIGNED NOT NULL
        COMMENT '부모 feedback ID',

    candidate_rank SMALLINT UNSIGNED NOT NULL
        COMMENT '후보 순위 (Top-1 제외), 1부터 시작',

    class_id INT UNSIGNED NOT NULL
        COMMENT '후보 Class ID',

    score DECIMAL(8,6) NOT NULL
        COMMENT '후보 Class score. 0~1',

    PRIMARY KEY (feedback_id, candidate_rank),

    UNIQUE KEY uq_feedback_candidates_feedback_class (feedback_id, class_id),

    KEY idx_feedback_candidates_class_id (class_id),

    CONSTRAINT fk_feedback_candidates_feedback
        FOREIGN KEY (feedback_id) REFERENCES feedback(feedback_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_feedback_candidates_class
        FOREIGN KEY (class_id) REFERENCES waste_classes(class_id),

    CONSTRAINT chk_feedback_candidates_rank
        CHECK (candidate_rank >= 1),

    CONSTRAINT chk_feedback_candidates_score
        CHECK (score >= 0 AND score <= 1)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='분석 당시 사용자에게 제시한 Top-K 후보 snapshot (Top-1 제외)';


/* ================================================================================================
   7. favorites - 사용자 즐겨찾기 (폐기물 Class 단위)
   ================================================================================================ */

CREATE TABLE favorites (

    favorite_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT
        COMMENT '즐겨찾기 고유 ID',

    user_id BIGINT UNSIGNED NOT NULL
        COMMENT '즐겨찾기 소유 사용자 ID',

    class_id INT UNSIGNED NOT NULL
        COMMENT '즐겨찾기 폐기물 Class ID',

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
        COMMENT '즐겨찾기 등록 시각 (KST)',

    PRIMARY KEY (favorite_id),

    UNIQUE KEY uq_favorites_user_class (user_id, class_id),

    KEY idx_favorites_class_id (class_id),

    CONSTRAINT fk_favorites_user
        FOREIGN KEY (user_id) REFERENCES users(user_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_favorites_class
        FOREIGN KEY (class_id) REFERENCES waste_classes(class_id)

) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci
  COMMENT='사용자 폐기물 Class 즐겨찾기';


/* ================================================================================================
   8. 목업(Mock) 데이터
   ------------------------------------------------------------------------------------------------
   - regions(56)/waste_classes(17): 실제 운영 Master 데이터 그대로 (data/taxonomy/*.json 과 동일)
   - users(12): 이메일/지역 다양화. user 6, 10은 region_id NULL (가입 직후 지역 미선택 상태 재현
     -> 이 두 명은 아래 feedback에도 등장하지 않음. /analyze 는 지역 선택이 없으면 호출 자체가
     불가능하기 때문 - backend/api/analyze.py 참고)
   - 비밀번호: 전부 동일한 테스트 비밀번호 "Test1234!" 의 실제 bcrypt 해시
     ($2b$12$... 로 시작, backend/core/security.py::hash_password 결과물과 동일한 포맷)
   - images/feedback(20): PENDING(미응답, 저신뢰도 포함) / 맞음(CONFIRMED) / USER 정정 /
     GEMINI fallback 4가지 상태를 고루 섞어서 넣었다. review_status 도 일부 APPROVED/REJECTED로
     채워 재학습 데이터 검수 시나리오를 재현했다.
   - feedback_candidates: 각 feedback 당 2개씩, USER 정정 케이스는 선택된 final_class_id가
     후보 안에 존재하도록, GEMINI fallback 케이스는 최종 class가 후보 밖에 있도록 구성했다.
   - favorites(10)
   ================================================================================================ */

-- ------------------------------------------------------------------
-- 8-1. regions (56행)
-- ------------------------------------------------------------------
INSERT INTO regions (region_id, sido_name, sgg_name, created_at) VALUES
(1, '서울특별시', '종로구', '2026-08-01 00:00:00'),
(2, '서울특별시', '중구', '2026-08-01 00:00:00'),
(3, '서울특별시', '용산구', '2026-08-01 00:00:00'),
(4, '서울특별시', '성동구', '2026-08-01 00:00:00'),
(5, '서울특별시', '광진구', '2026-08-01 00:00:00'),
(6, '서울특별시', '동대문구', '2026-08-01 00:00:00'),
(7, '서울특별시', '중랑구', '2026-08-01 00:00:00'),
(8, '서울특별시', '성북구', '2026-08-01 00:00:00'),
(9, '서울특별시', '강북구', '2026-08-01 00:00:00'),
(10, '서울특별시', '도봉구', '2026-08-01 00:00:00'),
(11, '서울특별시', '노원구', '2026-08-01 00:00:00'),
(12, '서울특별시', '은평구', '2026-08-01 00:00:00'),
(13, '서울특별시', '서대문구', '2026-08-01 00:00:00'),
(14, '서울특별시', '마포구', '2026-08-01 00:00:00'),
(15, '서울특별시', '양천구', '2026-08-01 00:00:00'),
(16, '서울특별시', '강서구', '2026-08-01 00:00:00'),
(17, '서울특별시', '구로구', '2026-08-01 00:00:00'),
(18, '서울특별시', '금천구', '2026-08-01 00:00:00'),
(19, '서울특별시', '영등포구', '2026-08-01 00:00:00'),
(20, '서울특별시', '동작구', '2026-08-01 00:00:00'),
(21, '서울특별시', '관악구', '2026-08-01 00:00:00'),
(22, '서울특별시', '서초구', '2026-08-01 00:00:00'),
(23, '서울특별시', '강남구', '2026-08-01 00:00:00'),
(24, '서울특별시', '송파구', '2026-08-01 00:00:00'),
(25, '서울특별시', '강동구', '2026-08-01 00:00:00'),
(26, '경기도', '가평군', '2026-08-01 00:00:00'),
(27, '경기도', '고양시', '2026-08-01 00:00:00'),
(28, '경기도', '과천시', '2026-08-01 00:00:00'),
(29, '경기도', '광명시', '2026-08-01 00:00:00'),
(30, '경기도', '광주시', '2026-08-01 00:00:00'),
(31, '경기도', '구리시', '2026-08-01 00:00:00'),
(32, '경기도', '군포시', '2026-08-01 00:00:00'),
(33, '경기도', '김포시', '2026-08-01 00:00:00'),
(34, '경기도', '남양주시', '2026-08-01 00:00:00'),
(35, '경기도', '동두천시', '2026-08-01 00:00:00'),
(36, '경기도', '부천시', '2026-08-01 00:00:00'),
(37, '경기도', '성남시', '2026-08-01 00:00:00'),
(38, '경기도', '수원시', '2026-08-01 00:00:00'),
(39, '경기도', '시흥시', '2026-08-01 00:00:00'),
(40, '경기도', '안산시', '2026-08-01 00:00:00'),
(41, '경기도', '안성시', '2026-08-01 00:00:00'),
(42, '경기도', '안양시', '2026-08-01 00:00:00'),
(43, '경기도', '양주시', '2026-08-01 00:00:00'),
(44, '경기도', '양평군', '2026-08-01 00:00:00'),
(45, '경기도', '여주시', '2026-08-01 00:00:00'),
(46, '경기도', '연천군', '2026-08-01 00:00:00'),
(47, '경기도', '오산시', '2026-08-01 00:00:00'),
(48, '경기도', '용인시', '2026-08-01 00:00:00'),
(49, '경기도', '의왕시', '2026-08-01 00:00:00'),
(50, '경기도', '의정부시', '2026-08-01 00:00:00'),
(51, '경기도', '이천시', '2026-08-01 00:00:00'),
(52, '경기도', '파주시', '2026-08-01 00:00:00'),
(53, '경기도', '평택시', '2026-08-01 00:00:00'),
(54, '경기도', '포천시', '2026-08-01 00:00:00'),
(55, '경기도', '하남시', '2026-08-01 00:00:00'),
(56, '경기도', '화성시', '2026-08-01 00:00:00');

-- ------------------------------------------------------------------
-- 8-2. waste_classes (17행, 2026-09-18 소분류 병합 이후 기준)
-- ------------------------------------------------------------------
INSERT INTO waste_classes (class_id, major_category, minor_category) VALUES
(0, '고철류', '고철'),
(1, '고철류', '비철금속'),
(2, '나무', '나무'),
(3, '도기류', '도기'),
(4, '비닐', '비닐'),
(5, '스티로폼', '스티로폼'),
(6, '유리병', '유리병'),
(7, '의류', '의류'),
(8, '종이류', '책'),
(9, '종이류', '박스류'),
(10, '종이류', '신문지'),
(11, '종이류', '종이'),
(12, '캔류', '캔'),
(13, '페트병', '페트병'),
(14, '플라스틱류', '플라스틱'),
(15, '플라스틱류', '장난감'),
(16, '형광등', '형광등');

-- ------------------------------------------------------------------
-- 8-3. users (12명, password = 전부 "Test1234!")
-- ------------------------------------------------------------------
INSERT INTO users (user_id, email, password_hash, region_id, created_at, updated_at) VALUES
(1,  'kim.jimin@example.com',     '$2b$12$NjDivrZZ9smGYB47xbCqYeopejsqOBN0ToMa95Zn5HoGaYv9dZpfu', 23,   '2026-08-20 09:12:00', '2026-08-20 09:12:00'),
(2,  'lee.seoyeon@example.com',   '$2b$12$NjDivrZZ9smGYB47xbCqYeopejsqOBN0ToMa95Zn5HoGaYv9dZpfu', 14,   '2026-08-22 14:03:10', '2026-08-22 14:03:10'),
(3,  'park.minjun@example.com',   '$2b$12$NjDivrZZ9smGYB47xbCqYeopejsqOBN0ToMa95Zn5HoGaYv9dZpfu', 38,   '2026-08-25 08:45:00', '2026-08-25 08:45:00'),
(4,  'choi.yuna@example.com',     '$2b$12$NjDivrZZ9smGYB47xbCqYeopejsqOBN0ToMa95Zn5HoGaYv9dZpfu', 8,    '2026-08-27 19:20:33', '2026-08-27 19:20:33'),
(5,  'jung.hyunwoo@example.com',  '$2b$12$NjDivrZZ9smGYB47xbCqYeopejsqOBN0ToMa95Zn5HoGaYv9dZpfu', 48,   '2026-08-29 11:11:11', '2026-08-29 11:11:11'),
(6,  'kang.sujin@example.com',    '$2b$12$NjDivrZZ9smGYB47xbCqYeopejsqOBN0ToMa95Zn5HoGaYv9dZpfu', NULL, '2026-09-02 22:40:00', '2026-09-02 22:40:00'),
(7,  'yoon.dohyun@example.com',   '$2b$12$NjDivrZZ9smGYB47xbCqYeopejsqOBN0ToMa95Zn5HoGaYv9dZpfu', 1,    '2026-09-04 07:55:45', '2026-09-04 07:55:45'),
(8,  'han.jiwoo@example.com',     '$2b$12$NjDivrZZ9smGYB47xbCqYeopejsqOBN0ToMa95Zn5HoGaYv9dZpfu', 27,   '2026-09-06 13:30:00', '2026-09-06 13:30:00'),
(9,  'song.eunwoo@example.com',   '$2b$12$NjDivrZZ9smGYB47xbCqYeopejsqOBN0ToMa95Zn5HoGaYv9dZpfu', 19,   '2026-09-10 16:16:16', '2026-09-10 16:16:16'),
(10, 'shin.ara@example.com',      '$2b$12$NjDivrZZ9smGYB47xbCqYeopejsqOBN0ToMa95Zn5HoGaYv9dZpfu', NULL, '2026-09-14 09:00:00', '2026-09-14 09:00:00'),
(11, 'baek.seungmin@example.com', '$2b$12$NjDivrZZ9smGYB47xbCqYeopejsqOBN0ToMa95Zn5HoGaYv9dZpfu', 40,   '2026-09-18 20:05:00', '2026-09-18 20:05:00'),
(12, 'oh.harin@example.com',      '$2b$12$NjDivrZZ9smGYB47xbCqYeopejsqOBN0ToMa95Zn5HoGaYv9dZpfu', 56,   '2026-09-22 12:12:12', '2026-09-22 12:12:12');

-- ------------------------------------------------------------------
-- 8-4. images (20행, feedback과 1:1이므로 image_id = feedback_id로 맞춰서 입력)
-- ------------------------------------------------------------------
INSERT INTO images (image_id, s3_key, content_type) VALUES
(1,  'feedback/2026/08/21/550e8400-e29b-41d4-a716-446655440001.jpg', 'image/jpeg'),
(2,  'feedback/2026/08/24/550e8400-e29b-41d4-a716-446655440002.jpg', 'image/jpeg'),
(3,  'feedback/2026/08/23/550e8400-e29b-41d4-a716-446655440003.jpg', 'image/jpeg'),
(4,  'feedback/2026/08/26/550e8400-e29b-41d4-a716-446655440004.jpg', 'image/jpeg'),
(5,  'feedback/2026/08/26/550e8400-e29b-41d4-a716-446655440005.jpg', 'image/jpeg'),
(6,  'feedback/2026/08/30/550e8400-e29b-41d4-a716-446655440006.jpg', 'image/jpeg'),
(7,  'feedback/2026/08/28/550e8400-e29b-41d4-a716-446655440007.jpg', 'image/jpeg'),
(8,  'feedback/2026/09/01/550e8400-e29b-41d4-a716-446655440008.jpg', 'image/jpeg'),
(9,  'feedback/2026/08/30/550e8400-e29b-41d4-a716-446655440009.jpg', 'image/jpeg'),
(10, 'feedback/2026/09/03/550e8400-e29b-41d4-a716-446655440010.webp', 'image/webp'),
(11, 'feedback/2026/09/05/550e8400-e29b-41d4-a716-446655440011.jpg', 'image/jpeg'),
(12, 'feedback/2026/09/08/550e8400-e29b-41d4-a716-446655440012.jpg', 'image/jpeg'),
(13, 'feedback/2026/09/07/550e8400-e29b-41d4-a716-446655440013.jpg', 'image/jpeg'),
(14, 'feedback/2026/09/09/550e8400-e29b-41d4-a716-446655440014.jpg', 'image/jpeg'),
(15, 'feedback/2026/09/11/550e8400-e29b-41d4-a716-446655440015.jpg', 'image/jpeg'),
(16, 'feedback/2026/09/13/550e8400-e29b-41d4-a716-446655440016.jpg', 'image/jpeg'),
(17, 'feedback/2026/09/19/550e8400-e29b-41d4-a716-446655440017.jpg', 'image/jpeg'),
(18, 'feedback/2026/09/20/550e8400-e29b-41d4-a716-446655440018.webp', 'image/webp'),
(19, 'feedback/2026/09/23/550e8400-e29b-41d4-a716-446655440019.jpg', 'image/jpeg'),
(20, 'feedback/2026/09/25/550e8400-e29b-41d4-a716-446655440020.jpg', 'image/jpeg');

-- ------------------------------------------------------------------
-- 8-5. feedback (20행)
--   상태 분포: CONFIRMED(맞음) 11 / PENDING(미응답, 저신뢰도 포함) 4 /
--              USER 정정 3 / GEMINI fallback 2
--   review_status: APPROVED 6 / REJECTED 1 / 나머지 PENDING
-- ------------------------------------------------------------------
INSERT INTO feedback (
    feedback_id, user_id, image_id,
    predicted_class_id, predicted_score,
    final_class_id, is_correct, correction_source,
    bbox_x1, bbox_y1, bbox_x2, bbox_y2,
    model_version, review_status,
    created_at, updated_at
) VALUES
-- 1: user1, 비닐 예측 -> 맞음, 재학습 승인
(1,  1, 1,  4,  0.930000,  4, TRUE, NULL,
 0.120000, 0.150000, 0.780000, 0.860000, 'yolov8n-recycling-v1.2', 'APPROVED',
 '2026-08-21 10:00:00', '2026-08-21 10:03:00'),

-- 2: user1, 페트병 예측 -> 맞음
(2,  1, 2,  13, 0.880000,  13, TRUE, NULL,
 0.200000, 0.300000, 0.700000, 0.900000, 'yolov8n-recycling-v1.2', 'PENDING',
 '2026-08-24 18:22:00', '2026-08-24 18:24:30'),

-- 3: user2, 박스류 예측 -> 맞음, 재학습 승인
(3,  2, 3,  9,  0.950000,  9, TRUE, NULL,
 0.100000, 0.100000, 0.900000, 0.950000, 'yolov8n-recycling-v1.2', 'APPROVED',
 '2026-08-23 09:10:00', '2026-08-23 09:11:05'),

-- 4: user2, 유리병 예측(저신뢰도) -> 미응답 (재촬영 유도 케이스)
(4,  2, 4,  6,  0.410000,  NULL, NULL, NULL,
 0.250000, 0.400000, 0.600000, 0.750000, 'yolov8n-recycling-v1.3', 'PENDING',
 '2026-08-26 20:05:00', '2026-08-26 20:05:00'),

-- 5: user3, 캔 예측 -> 사용자가 "플라스틱"으로 정정 (후보 목록 안에서 선택), 재학습 승인
(5,  3, 5,  12, 0.900000,  14, FALSE, 'USER',
 0.150000, 0.200000, 0.650000, 0.800000, 'yolov8n-recycling-v1.3', 'APPROVED',
 '2026-08-26 11:40:00', '2026-08-26 11:42:20'),

-- 6: user3, 고철 예측 -> 맞음
(6,  3, 6,  0,  0.770000,  0, TRUE, NULL,
 0.300000, 0.350000, 0.700000, 0.720000, 'yolov8n-recycling-v1.3', 'PENDING',
 '2026-08-30 08:12:00', '2026-08-30 08:13:40'),

-- 7: user4, 플라스틱 예측 -> 사용자가 "비닐"로 정정
(7,  4, 7,  14, 0.680000,  4, FALSE, 'USER',
 0.180000, 0.220000, 0.680000, 0.790000, 'yolov8n-recycling-v1.3', 'PENDING',
 '2026-08-28 21:00:00', '2026-08-28 21:05:10'),

-- 8: user4, 책 예측 -> 맞음, 재학습 승인
(8,  4, 8,  8,  0.910000,  8, TRUE, NULL,
 0.220000, 0.180000, 0.760000, 0.880000, 'yolov8n-recycling-v1.3', 'APPROVED',
 '2026-09-01 10:30:00', '2026-09-01 10:31:00'),

-- 9: user5, 도기 예측(저신뢰도) -> 미응답
(9,  5, 9,  3,  0.590000,  NULL, NULL, NULL,
 0.100000, 0.500000, 0.550000, 0.900000, 'yolov8n-recycling-v1.3', 'PENDING',
 '2026-08-30 17:45:00', '2026-08-30 17:45:00'),

-- 10: user5, 스티로폼 예측 -> 맞음
(10, 5, 10, 5,  0.840000,  5, TRUE, NULL,
 0.270000, 0.310000, 0.730000, 0.770000, 'yolov8n-recycling-v1.3', 'PENDING',
 '2026-09-03 13:13:13', '2026-09-03 13:14:00'),

-- 11: user7, 종이 예측 -> "여기에 없어요" -> Gemini가 "의류"로 재분류 (후보 밖 결과), 재학습 승인
(11, 7, 11, 11, 0.720000,  7, FALSE, 'GEMINI',
 0.150000, 0.140000, 0.850000, 0.900000, 'yolov8n-recycling-v1.3', 'APPROVED',
 '2026-09-05 09:09:09', '2026-09-05 09:15:47'),

-- 12: user7, 비닐 예측 -> 맞음
(12, 7, 12, 4,  0.950000,  4, TRUE, NULL,
 0.190000, 0.210000, 0.710000, 0.810000, 'yolov8n-recycling-v1.3', 'PENDING',
 '2026-09-08 15:15:00', '2026-09-08 15:16:05'),

-- 13: user8, 형광등 예측 -> 맞음
(13, 8, 13, 16, 0.870000,  16, TRUE, NULL,
 0.330000, 0.360000, 0.660000, 0.700000, 'yolov8n-recycling-v1.3', 'PENDING',
 '2026-09-07 12:00:00', '2026-09-07 12:01:30'),

-- 14: user8, 신문지 예측(저신뢰도) -> 미응답
(14, 8, 14, 10, 0.450000,  NULL, NULL, NULL,
 0.120000, 0.480000, 0.580000, 0.910000, 'yolov8n-recycling-v1.3', 'PENDING',
 '2026-09-09 19:19:19', '2026-09-09 19:19:19'),

-- 15: user9, 캔 예측 -> 맞음, 재학습 승인
(15, 9, 15, 12, 0.930000,  12, TRUE, NULL,
 0.240000, 0.260000, 0.740000, 0.780000, 'yolov8n-recycling-v1.3', 'APPROVED',
 '2026-09-11 08:08:08', '2026-09-11 08:09:00'),

-- 16: user9, 장난감 예측 -> 사용자가 "플라스틱"으로 정정했지만 흐릿한 사진이라 재학습 반려
(16, 9, 16, 15, 0.660000,  14, FALSE, 'USER',
 0.170000, 0.190000, 0.690000, 0.830000, 'yolov8n-recycling-v1.3', 'REJECTED',
 '2026-09-13 21:21:21', '2026-09-13 21:23:00'),

-- 17: user11, 나무 예측 -> 맞음
(17, 11, 17, 2,  0.790000,  2, TRUE, NULL,
 0.280000, 0.300000, 0.720000, 0.760000, 'yolov8n-recycling-v1.3', 'PENDING',
 '2026-09-19 10:10:10', '2026-09-19 10:11:00'),

-- 18: user11, 박스류 예측 -> 맞음
(18, 11, 18, 9,  0.960000,  9, TRUE, NULL,
 0.110000, 0.130000, 0.890000, 0.930000, 'yolov8n-recycling-v1.3', 'PENDING',
 '2026-09-20 14:14:14', '2026-09-20 14:15:00'),

-- 19: user12, 비닐 예측(저신뢰도) -> 미응답
(19, 12, 19, 4,  0.550000,  NULL, NULL, NULL,
 0.160000, 0.170000, 0.640000, 0.720000, 'yolov8n-recycling-v1.3', 'PENDING',
 '2026-09-23 11:11:00', '2026-09-23 11:11:00'),

-- 20: user12, 비철금속 예측 -> "여기에 없어요" -> Gemini가 "고철"로 재분류 (후보 밖 결과)
(20, 12, 20, 1,  0.810000,  0, FALSE, 'GEMINI',
 0.200000, 0.230000, 0.700000, 0.750000, 'yolov8n-recycling-v1.3', 'PENDING',
 '2026-09-25 16:16:16', '2026-09-25 16:24:50');

-- ------------------------------------------------------------------
-- 8-6. feedback_candidates (각 feedback당 2개, Top-1 제외한 후보 스냅샷)
-- ------------------------------------------------------------------
INSERT INTO feedback_candidates (feedback_id, candidate_rank, class_id, score) VALUES
(1,  1, 14, 0.050000), (1,  2, 9,  0.020000),
(2,  1, 6,  0.070000), (2,  2, 14, 0.030000),
(3,  1, 11, 0.030000), (3,  2, 8,  0.010000),
(4,  1, 3,  0.350000), (4,  2, 0,  0.120000),
(5,  1, 14, 0.080000), (5,  2, 0,  0.010000),   -- 5번: 사용자가 rank1(14=플라스틱) 후보를 선택
(6,  1, 1,  0.150000), (6,  2, 12, 0.050000),
(7,  1, 4,  0.220000), (7,  2, 5,  0.060000),   -- 7번: 사용자가 rank1(4=비닐) 후보를 선택
(8,  1, 11, 0.060000), (8,  2, 9,  0.020000),
(9,  1, 6,  0.300000), (9,  2, 0,  0.080000),
(10, 1, 4,  0.100000), (10, 2, 14, 0.040000),
(11, 1, 8,  0.180000), (11, 2, 9,  0.070000),   -- 11번: Gemini 최종(7=의류)는 후보 밖
(12, 1, 14, 0.030000), (12, 2, 6,  0.010000),
(13, 1, 0,  0.080000), (13, 2, 1,  0.030000),
(14, 1, 11, 0.330000), (14, 2, 8,  0.150000),
(15, 1, 0,  0.040000), (15, 2, 1,  0.020000),
(16, 1, 14, 0.250000), (16, 2, 4,  0.050000),   -- 16번: 사용자가 rank1(14=플라스틱) 후보를 선택
(17, 1, 0,  0.120000), (17, 2, 9,  0.040000),
(18, 1, 11, 0.020000), (18, 2, 8,  0.010000),
(19, 1, 14, 0.280000), (19, 2, 9,  0.090000),
(20, 1, 12, 0.100000), (20, 2, 14, 0.040000);  -- 20번: Gemini 최종(0=고철)는 후보 밖

-- ------------------------------------------------------------------
-- 8-7. favorites (10행)
-- ------------------------------------------------------------------
INSERT INTO favorites (favorite_id, user_id, class_id, created_at) VALUES
(1,  1,  13, '2026-08-21 10:30:00'),
(2,  1,  4,  '2026-08-25 09:00:00'),
(3,  2,  9,  '2026-08-24 19:00:00'),
(4,  3,  14, '2026-08-27 12:00:00'),
(5,  4,  4,  '2026-08-29 20:00:00'),
(6,  5,  5,  '2026-09-04 08:00:00'),
(7,  7,  4,  '2026-09-06 21:00:00'),
(8,  8,  16, '2026-09-08 13:00:00'),
(9,  9,  12, '2026-09-12 16:00:00'),
(10, 11, 2,  '2026-09-20 21:00:00');


/* ================================================================================================
   9. 자주 사용될 SELECT 문 모음
   ------------------------------------------------------------------------------------------------
   backend/api/*.py, backend/services/*.py 에서 실제로 사용 중인 쿼리 패턴 + 운영/재학습에
   자주 필요한 분석 쿼리를 정리했다. ":placeholder" 로 표시된 값은 애플리케이션에서 바인딩
   파라미터로 교체해서 쓰면 된다 (여기서는 바로 실행해볼 수 있도록 예시 리터럴 값을 넣어둠).
   ================================================================================================ */

-- --------------------------------------------------------------------------
-- [인증/사용자] 이메일로 사용자 조회 (로그인/회원가입 중복확인) - auth.py
-- --------------------------------------------------------------------------
SELECT user_id, email, password_hash, region_id
FROM users
WHERE email = 'kim.jimin@example.com';

-- --------------------------------------------------------------------------
-- [사용자] 내 프로필 + 현재 선택 지역 조회 (지역 정보까지 JOIN) - users.py GET /me
-- --------------------------------------------------------------------------
SELECT u.user_id, u.email, u.created_at,
       r.region_id, r.sido_name, r.sgg_name
FROM users u
LEFT JOIN regions r ON r.region_id = u.region_id
WHERE u.user_id = 1;

-- --------------------------------------------------------------------------
-- [지역] 지역 목록 조회 (전체 또는 시/도 필터) - regions.py GET /regions
-- --------------------------------------------------------------------------
SELECT region_id, sido_name, sgg_name
FROM regions
ORDER BY region_id;

SELECT region_id, sido_name, sgg_name
FROM regions
WHERE sido_name = '경기도'
ORDER BY region_id;

-- --------------------------------------------------------------------------
-- [즐겨찾기] 내 즐겨찾기 목록 (최신순, class 이름 JOIN) - favorites.py GET /favorites
-- --------------------------------------------------------------------------
SELECT f.favorite_id, wc.class_id, wc.major_category, wc.minor_category, f.created_at
FROM favorites f
JOIN waste_classes wc ON wc.class_id = f.class_id
WHERE f.user_id = 1
ORDER BY f.created_at DESC;

-- --------------------------------------------------------------------------
-- [즐겨찾기] 전체 사용자 기준 인기 즐겨찾기 TOP N (관리자/추천용)
-- --------------------------------------------------------------------------
SELECT wc.class_id, wc.major_category, wc.minor_category, COUNT(*) AS favorite_count
FROM favorites f
JOIN waste_classes wc ON wc.class_id = f.class_id
GROUP BY wc.class_id, wc.major_category, wc.minor_category
ORDER BY favorite_count DESC
LIMIT 10;

-- --------------------------------------------------------------------------
-- [피드백] 피드백 소유권 + 완료여부 체크 (confirm/select-candidate/not-in-list 공통 전처리)
--          - feedback.py::_load_owned_feedback
-- --------------------------------------------------------------------------
SELECT feedback_id, user_id, image_id, predicted_class_id, final_class_id, is_correct
FROM feedback
WHERE feedback_id = 5
  AND user_id = 3;                       -- 소유자 검증
  -- is_correct IS NOT NULL 이면 이미 처리된 피드백(앱 레벨에서 409 처리)

-- --------------------------------------------------------------------------
-- [피드백] select-candidate 시 선택한 class가 실제 제시된 후보인지 검증
--          - feedback.py::select_candidate
-- --------------------------------------------------------------------------
SELECT 1
FROM feedback_candidates
WHERE feedback_id = 7
  AND class_id = 4
LIMIT 1;

-- --------------------------------------------------------------------------
-- [피드백] 사용자별 최근 분석 이력 (idx_feedback_user_created_at 활용)
-- --------------------------------------------------------------------------
SELECT f.feedback_id, wc.major_category, wc.minor_category,
       f.predicted_score, f.is_correct, f.created_at
FROM feedback f
JOIN waste_classes wc ON wc.class_id = f.predicted_class_id
WHERE f.user_id = 7
ORDER BY f.created_at DESC
LIMIT 20;

-- --------------------------------------------------------------------------
-- [피드백] 아직 응답 없는(PENDING) 분석 목록 - 사용자 알림/리마인드 후보
-- --------------------------------------------------------------------------
SELECT feedback_id, user_id, predicted_class_id, predicted_score, created_at
FROM feedback
WHERE is_correct IS NULL
ORDER BY created_at DESC;

-- --------------------------------------------------------------------------
-- [분석/통계] Class별 Top-1 정답률 (모델 성능 모니터링) - idx_feedback_predicted_correct 활용
-- --------------------------------------------------------------------------
SELECT wc.class_id, wc.major_category, wc.minor_category,
       COUNT(*)                                   AS total_answered,
       SUM(f.is_correct = TRUE)                    AS correct_count,
       ROUND(SUM(f.is_correct = TRUE) / COUNT(*) * 100, 1) AS accuracy_pct
FROM feedback f
JOIN waste_classes wc ON wc.class_id = f.predicted_class_id
WHERE f.is_correct IS NOT NULL
GROUP BY wc.class_id, wc.major_category, wc.minor_category
ORDER BY accuracy_pct ASC;

-- --------------------------------------------------------------------------
-- [분석/통계] 가장 많이 오답이 나는 Class TOP N (재학습 우선순위 판단용)
-- --------------------------------------------------------------------------
SELECT wc.class_id, wc.major_category, wc.minor_category,
       COUNT(*) AS wrong_count
FROM feedback f
JOIN waste_classes wc ON wc.class_id = f.predicted_class_id
WHERE f.is_correct = FALSE
GROUP BY wc.class_id, wc.major_category, wc.minor_category
ORDER BY wrong_count DESC
LIMIT 10;

-- --------------------------------------------------------------------------
-- [분석/통계] 오답 보정 출처(USER/GEMINI) 비율
--   - USER 비율이 높으면 Top-K 안에서 대부분 찾았다는 뜻
--   - GEMINI 비율이 높으면 "여기에 없어요"(Top-K 밖) 케이스가 많다는 뜻
-- --------------------------------------------------------------------------
SELECT correction_source, COUNT(*) AS cnt
FROM feedback
WHERE is_correct = FALSE
GROUP BY correction_source;

-- --------------------------------------------------------------------------
-- [분석/통계] 모델 버전별 정답률 비교 (모델 업그레이드 효과 확인)
-- --------------------------------------------------------------------------
SELECT model_version,
       COUNT(*)                                    AS total_answered,
       ROUND(SUM(is_correct = TRUE) / COUNT(*) * 100, 1) AS accuracy_pct
FROM feedback
WHERE is_correct IS NOT NULL
GROUP BY model_version
ORDER BY model_version;

-- --------------------------------------------------------------------------
-- [분석/통계] 저신뢰도(재촬영 유도) 비율 - VISION_CONFIDENCE_THRESHOLD 기준(예: 0.5)
-- --------------------------------------------------------------------------
SELECT
    SUM(predicted_score < 0.5) AS low_confidence_count,
    COUNT(*)                   AS total_count,
    ROUND(SUM(predicted_score < 0.5) / COUNT(*) * 100, 1) AS low_confidence_pct
FROM feedback;

-- --------------------------------------------------------------------------
-- [분석/통계] 일별 분석 건수 추이 (최근 30일, 활성도 모니터링)
-- --------------------------------------------------------------------------
SELECT DATE(created_at) AS analyze_date, COUNT(*) AS analyze_count
FROM feedback
WHERE created_at >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
GROUP BY DATE(created_at)
ORDER BY analyze_date;

-- --------------------------------------------------------------------------
-- [분석/통계] 지역별 가입자 수 분포
-- --------------------------------------------------------------------------
SELECT r.sido_name, r.sgg_name, COUNT(u.user_id) AS user_count
FROM regions r
LEFT JOIN users u ON u.region_id = r.region_id
GROUP BY r.region_id, r.sido_name, r.sgg_name
ORDER BY user_count DESC;

-- --------------------------------------------------------------------------
-- [재학습] 재학습용으로 승인된(APPROVED) 데이터셋 추출
--   - review_status는 앱에서 자동으로 세팅하지 않으므로, 사람이 수동으로 검수 후
--     UPDATE feedback SET review_status='APPROVED' WHERE ... 형태로 갱신한다.
-- --------------------------------------------------------------------------
SELECT f.feedback_id, i.s3_key, i.content_type,
       f.final_class_id, wc.major_category, wc.minor_category,
       f.bbox_x1, f.bbox_y1, f.bbox_x2, f.bbox_y2
FROM feedback f
JOIN images i ON i.image_id = f.image_id
JOIN waste_classes wc ON wc.class_id = f.final_class_id
WHERE f.review_status = 'APPROVED';

-- --------------------------------------------------------------------------
-- [재학습] 검수 대기 중(PENDING)이면서 이미 사용자 응답은 끝난 건 - 관리자 검수 큐
-- --------------------------------------------------------------------------
SELECT feedback_id, user_id, final_class_id, is_correct, correction_source, updated_at
FROM feedback
WHERE review_status = 'PENDING'
  AND is_correct IS NOT NULL
ORDER BY updated_at ASC;
