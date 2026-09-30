# backend 폴더 안내서

이 문서는 `backend/` 폴더 아래에 있는 **모든 폴더와 모든 파일**이 각각 무엇을
하는지 하나하나 설명합니다. 백엔드 개발을 잘 모르거나 이 프로젝트가 처음이어도
읽을 수 있도록, 전문 용어가 나올 때마다 쉬운 말로 함께 풀어 썼고, 각 파일 안의
주요 함수까지 구체적으로 짚었습니다.

> 전체 서비스 개요(시스템 구성도, API 19개 목록, 도메인 규칙 등)는 저장소
> 루트의 [`README.md`](../README.md) 를 먼저 보시는 걸 추천합니다. 이 문서는
> 그중 **backend 폴더 내부**만 아주 자세히 설명합니다.
>
> API를 하나씩 curl로 테스트해보고 싶다면 →
> [`docs/API_TEST_COMMANDS.md`](../docs/API_TEST_COMMANDS.md)

---

## 목차

1. [이 폴더는 한마디로 무엇인가요](#1-이-폴더는-한마디로-무엇인가요)
2. [실행 방법 (요약)](#2-실행-방법-요약)
3. [폴더 전체 지도](#3-폴더-전체-지도)
4. [폴더별 상세 설명](#4-폴더별-상세-설명)
5. [최상위 파일 설명](#5-최상위-파일-설명)
6. [요청 하나가 실제로 지나가는 길 (예시 2가지)](#6-요청-하나가-실제로-지나가는-길-예시-2가지)
7. [실제 배포 DB 스키마와 코드를 맞춘 이력](#7-실제-배포-db-스키마와-코드를-맞춘-이력)
8. [겪었던 문제와 해결 이력 (트러블슈팅 일지)](#8-겪었던-문제와-해결-이력-트러블슈팅-일지)
9. [자주 나오는 용어 풀이](#9-자주-나오는-용어-풀이)

---

## 1. 이 폴더는 한마디로 무엇인가요

`backend/` 는 **스마트폰 앱(Frontend)이 인터넷으로 말을 거는 상대**입니다.

사용자가 앱에서 "폐기물 사진을 올렸어요"라고 하면, 그 요청을 받아서

- 로그인한 사람이 맞는지 확인하고 (인증)
- 사진을 크기 줄이고 압축해서, AI 분석 서버(Vision)에 보내 무슨 쓰레기인지 물어보고
- 그 결과와 사진을 데이터베이스·저장소(S3)에 기록하고
- "이건 플라스틱류/플라스틱이고, 화·목요일에 배출하세요" 같은 최종 답을
  다시 앱에 돌려주는 일을 하는 프로그램입니다.

이 폴더 안의 코드는 **FastAPI**라는 Python 웹 프레임워크로 만들어져 있고,
`main.py`를 실행하면 하나의 서버 프로그램이 되어 돌아갑니다. 이 서버는
**19개 API 중 17개**(회원가입/로그인, 지역 선택, 이미지 분석, 피드백,
분리배출 정보, AI 챗봇, 즐겨찾기 등)를 담당하고, 나머지 2개(실제 사진을
보고 "이게 무슨 쓰레기인지" 알아내는 AI 모델 자체)는 저장소의 `vision/`
폴더에 있는 **별도의 서버**가 담당합니다. `backend/` 는 그 Vision 서버에게
"이 사진 좀 분석해줘"라고 요청만 보내는 쪽입니다.

---

## 2. 실행 방법 (요약)

> 자세한 설명과 여러 시나리오는 저장소 루트 [`README.md`](../README.md) 참고.
> 아래는 backend 폴더만 놓고 봤을 때 필요한 핵심만 요약한 것입니다.

### 처음 한 번만

```bash
# 저장소 루트에서 (backend 는 uv workspace 의 "멤버"라서 반드시 --all-packages 필요)
uv sync --all-packages

# 설정값 채우기 (backend 가 아니라 "저장소 루트"에 .env 를 만든다 — 3장 참고)
cp .env.example .env
```

`.env` 를 열어 최소한 아래 항목은 채워야 실제로 동작합니다.

| 항목 | 안 채우면 어떻게 되나 |
|---|---|
| `DATABASE_URL` | MySQL 접속 불가 → 대부분의 API가 `503 DATABASE_ERROR` |
| `JWT_SECRET_KEY` | 기본값 그대로 쓰면 토큰 위조 위험 (운영 배포 전 반드시 교체) |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_S3_BUCKET` | `/api/v1/analyze` 가 `502 S3_UPLOAD_FAILED`. 개발 중이면 `STORAGE_BACKEND=local` 로 우회 가능 |
| `PUBLIC_WASTE_API_SERVICE_KEY` | 없어도 서비스는 죽지 않음. 분석은 성공하되 `disposal_day: null` + 경고만 붙음 |
| `GEMINI_API_KEY` | 없어도 서비스는 죽지 않음. "여기에 없어요" 기능만 `503 GEMINI_NOT_CONFIGURED`, 챗봇은 미리 준비된 문장으로 답변 |

`DATABASE_URL`에 적은 MySQL 데이터베이스 자체는 미리 만들어져 있어야 합니다
(테이블은 앱이 자동으로 만들어주지만 데이터베이스 자체는 안 만들어줌):

```sql
CREATE DATABASE recycling_ssg CHARACTER SET utf8mb4;
```

### 서버 실행

```bash
# backend 폴더 안에서
uv run uvicorn main:app --reload --port 8000
```

또는 저장소 루트의 `scripts/run-dev.sh`(Vision 서버까지 같이 띄워주고,
MySQL/AWS 없이도 동작하는 개발 모드)를 쓰는 걸 추천합니다.

서버가 켜지면 `AUTO_CREATE_TABLES=true`(기본값)일 때 SQLAlchemy가 필요한
표를 전부 만들고, `AUTO_SEED_MASTER_DATA=true`(기본값)일 때 `regions`(56행)
`waste_classes`(86행)를 `../data/taxonomy/*.json`에서 읽어 채워 넣습니다 —
Vision 서버도 똑같은 파일을 보기 때문에, 양쪽에서 `class_id` 숫자가 항상
같은 뜻으로 통합니다.

> ⚠️ `AUTO_CREATE_TABLES`는 개발 편의용입니다. 운영 배포 전에는 Alembic 같은
> 정식 마이그레이션 도구로 바꾸는 걸 권장합니다 (지금은 이미 만들어진 표는
> 건드리지 않고, 없는 표만 만듭니다 — 7장 참고).

---

## 3. 폴더 전체 지도

```
backend/
├── main.py                  ← 서버의 "시작점". 여기서부터 모든 게 연결된다
├── pyproject.toml           ← 이 프로그램이 필요로 하는 부품(라이브러리) 목록
├── test_image.jpg           ← 개발자가 직접 넣어둔 테스트용 샘플 사진 (주전자)
│                              (비밀번호·주소 같은 설정값은 backend/ 가 아니라
│                               저장소 루트의 .env / .env.example 에 있다)
│
├── api/                     ← "요청을 받는 창구" (19개 API 중 17개가 여기)
├── core/                    ← 여러 창구가 공통으로 쓰는 기반 시설(설정/DB/인증/오류처리)
├── models/                  ← 데이터베이스 "표(table)"의 설계도
├── schemas/                 ← 요청/응답 JSON의 "형식 검사표"
├── services/                ← 외부 세계(S3, Vision 서버, 공공API, Gemini)와 대화하는 코드
├── agent/                   ← AI 챗봇(후속 질문 답변) 담당
├── db/                      ← 데이터베이스 초기 데이터 채워 넣기
└── tests/                   ← "이 코드가 제대로 동작하는지" 자동으로 확인하는 코드
```

---

## 4. 폴더별 상세 설명

### 4.1 `api/` — 요청을 받는 창구 (17개 엔드포인트)

은행에 비유하면 "1번 창구", "2번 창구"처럼, 앱이 보내는 요청 종류마다 담당
파일이 하나씩 있습니다. 각 파일은 FastAPI의 `APIRouter`를 하나씩 만들고,
`main.py`가 이 라우터들을 전부 조립합니다.

| 파일 | 담당 API (Method + 경로) | 하는 일 |
|---|---|---|
| `health.py` | `GET /health`, `GET /ready` | 서버 생존 확인, DB 연결까지 확인 (`/ready`는 DB가 죽으면 `503 SERVICE_NOT_READY`) |
| `auth.py` | `POST /api/v1/auth/{signup,login,logout}` | 회원가입(비밀번호 bcrypt 해시), 로그인(JWT 발급), 로그아웃(Stateless라 사실상 검증만) |
| `users.py` | `GET /api/v1/users/me`, `PATCH /api/v1/users/me/region` | 내 프로필 조회, 사는 지역(구/시) 선택·변경 |
| `regions.py` | `GET /api/v1/regions` | 서울 25개 구 + 경기 31개 시·군(56개) 목록. `sido_name` 쿼리로 필터 가능 |
| `analyze.py` | `POST /api/v1/analyze` | **가장 핵심 파일.** 사진 검증 → 리사이즈/압축 → Vision 전송 → confidence 확인 → S3 업로드 → DB 저장 → 배출정보 조회까지 한 번에 처리 |
| `feedback.py` | `POST /api/v1/feedback/{id}/{confirm,select-candidate,not-in-list}` | "맞아요"/"다른 후보 선택"/"Gemini로 재분석" 3가지 처리. 소유권(403)·중복처리(409) 검증 공통 함수(`_load_owned_feedback`) 포함 |
| `disposal.py` | `GET /api/v1/disposal/schedule` | 특정 품목(`class_id`)+내 지역의 배출 요일/시간/방법을 공공데이터에서 조회 |
| `chat.py` | `POST /api/v1/chat` | AI 챗봇 후속 질문. 대화 내용은 저장하지 않음(Stateless) |
| `favorites.py` | `GET/POST /api/v1/favorites`, `DELETE /api/v1/favorites/{id}` | 즐겨찾기 등록/조회/삭제. 같은 품목 중복 등록은 `409` |
| `__init__.py` | (없음, 빈 파일) | Python에게 "이 폴더는 하나의 묶음(패키지)입니다"라고 알리는 표시 |

> 💡 이 파일들 안의 함수 하나하나가 `@router.get(...)`, `@router.post(...)`
> 같은 데코레이터로 실제 웹 주소(URL)와 연결되어 있습니다.

### 4.2 `core/` — 모든 창구가 함께 쓰는 공통 설비

건물로 치면 "전기·수도·보안 시스템"에 해당합니다. `api/` 안의 어느 파일이든
이 폴더의 기능들을 가져다 씁니다.

| 파일 | 핵심 내용 | 쉬운 설명 |
|---|---|---|
| `config.py` | `class Settings(BaseSettings)` | 저장소 루트의 `.env`(절대경로로 고정 — cwd가 어디든 항상 같은 파일을 봄)를 읽어 DB 주소·JWT 비밀키·S3 키·AI 키 등을 하나의 `settings` 객체로 모아준다 |
| `database.py` | `engine`, `SessionLocal`, `Base`, `get_db()`, `check_db_connection()` | SQLAlchemy로 MySQL에 접속하는 통로(pytest 실행 시에만 예외적으로 SQLite 사용, `tests/conftest.py` 참고). `get_db()`는 API 함수마다 자동으로 "요청 하나당 DB 세션 하나"를 만들어주는 FastAPI 의존성(dependency) |
| `security.py` | `hash_password`/`verify_password`, `create_access_token`/`decode_access_token`, `TokenExpiredError`/`TokenInvalidError` | 비밀번호는 **bcrypt**로 단방향 암호화, 로그인 "출입증"은 **JWT**(HS256)로 발급·검증 |
| `deps.py` | `get_current_user(...)` | `Authorization: Bearer <토큰>` 헤더를 읽어 "이 요청을 보낸 사람이 누구인지" 확인하는 FastAPI 의존성. 토큰이 없으면 401, 깨졌으면 401, DB에 그 유저가 없으면 404 |
| `exceptions.py` | `class AppError`, `auth_required()`/`database_error()`/`validation_error()` 등 헬퍼, `register_exception_handlers(app)` | 오류가 나면 **항상 같은 JSON 모양**(`success/code/message/details/request_id`)으로 응답하도록 통일. `SQLAlchemyError`를 잡아 항상 `503 DATABASE_ERROR`로 바꿔주는 안전망도 여기 있음(각 API가 개별적으로 안 잡아도 최종적으로 여기서 막아줌) |
| `middleware.py` | `class RequestIDMiddleware` | 모든 요청/응답에 추적번호(`X-Request-ID`)를 자동으로 붙여줌. 클라이언트가 헤더로 보내면 그걸 그대로 쓰고, 없으면 새로 만듦 |
| `paths.py` | `taxonomy_data_dir()` | 공용 데이터 폴더(`data/taxonomy/`) 등, 프로젝트 안의 다른 폴더 위치를 cwd와 무관하게 절대경로로 계산 |
| `__init__.py` | - | 빈 파일. 패키지 표시용 |

### 4.3 `models/` — 데이터베이스 "표"의 설계도

엑셀 표를 코드로 그대로 옮겨놓은 것이라고 생각하면 됩니다. 파일 하나 =
데이터베이스 테이블 하나. **7개 테이블**이 여기 정의되어 있고, 이 설계도를
바탕으로 서버가 실제 MySQL에 표를 만듭니다 (단, 이미 있는 표는 안 건드림 —
7장 참고).

| 파일 | 테이블 | 저장하는 내용 |
|---|---|---|
| `user.py` | `users` | 회원 이메일, bcrypt로 암호화된 비밀번호, 선택한 지역(`region_id`, nullable) |
| `region.py` | `regions` | 서울 25개 구 + 경기 31개 시·군, 총 56개 고정 목록 (`region_id` 1~56 고정) |
| `waste_class.py` | `waste_classes` | 86종류 폐기물 분류(대분류/소분류) 목록 |
| `image.py` | `images` | 업로드 사진이 저장된 S3 위치(`s3_key`)와 실제 저장 형식(`content_type`). **`user_id`/`created_at` 컬럼은 일부러 없음** — 소유자는 `feedback.user_id`로 이미 추적되기 때문 (7장 참고) |
| `feedback.py` | `feedback` | AI가 처음 예측한 결과(`predicted_class_id`/`predicted_score`/`bbox_*`/`model_version`) + 사용자가 최종 확정한 결과(`final_class_id`/`is_correct`/`correction_source`) |
| `feedback_candidate.py` | `feedback_candidates` | AI가 제시한 "다른 후보들" Top-K 목록. **기본키가 `(feedback_id, rank)` 복합키** — 별도의 자동증가 ID가 없음 (7장 참고) |
| `favorite.py` | `favorites` | 사용자가 즐겨찾기한 품목. (사용자, 품목) 조합은 유일해야 함 |
| `timestamps.py` | (테이블 아님) | `utcnow()` 하나만 있는 파일. "지금 시각"을 항상 **표준시(UTC)**로 통일해서 기록하는 공용 도구. MySQL의 `NOW()`는 서버 로컬시간이라 애매해질 수 있어서, Python 쪽에서 직접 UTC로 찍음 |
| `__init__.py` | - | 위 7개 테이블 설계도를 한 번에 불러 모으는 파일 (`Base.metadata`가 이걸 보고 표를 만듦) |

> 💡 `region.py`와 `waste_class.py`의 실제 **내용물**(56개 지역 이름, 17개
> 분류 이름)은 여기 없고, 저장소 루트의 `data/taxonomy/` 폴더에 JSON으로
> 있습니다. 이 파일들은 어디까지나 "표의 칸(컬럼) 모양"만 정의합니다.

### 4.4 `schemas/` — 요청/응답의 "형식 검사표"

`models/`가 "DB에 뭘 저장하는지"라면, `schemas/`는 "**앱과 주고받는 JSON이
어떤 모양이어야 하는지**"를 정의합니다(Pydantic 라이브러리 사용). 예를 들어
"회원가입할 때 email은 반드시 이메일 형식이어야 하고, password는 8자
이상이어야 한다" 같은 규칙이 여기 있습니다. 형식이 안 맞으면 FastAPI가
자동으로 `422 REQUEST_VALIDATION_ERROR`를 돌려줍니다.

| 파일 | 관련 API | 주요 타입 |
|---|---|---|
| `common.py` | 모든 API 공용 | `ErrorResponse`, `RegionOut`, `CandidateScoreOut`, `UtcDatetime`(시각을 항상 `2026-09-11T09:00:00Z` 형식 문자열로 바꿔주는 타입) |
| `auth.py` | 회원가입/로그인 | `SignupRequest/Response`, `LoginRequest/Response` |
| `user.py` | 내 프로필, 지역 변경 | `UserProfileOut`, `RegionUpdateRequest/Response` |
| `region.py` | 지역 목록 | `RegionListResponse` |
| `analyze.py` | 이미지 분석 | `AnalyzeSuccessResponse`(성공), `AnalyzeRetakeResponse`(재촬영 안내) — 응답이 상황에 따라 둘 중 하나 |
| `feedback.py` | confirm/select-candidate/not-in-list | `ConfirmResponse`, `SelectCandidateRequest/Response`, `NotInListResponse` |
| `disposal.py` | 분리배출 정보 | `DisposalScheduleResponse` |
| `chat.py` | 챗봇 | `ChatRequest`(메시지 1~1000자 제한), `ChatResponse` |
| `favorite.py` | 즐겨찾기 | `FavoriteItemOut`, `FavoriteListResponse`, `FavoriteCreateRequest/Response` |
| `health.py` | 서버 상태 | `HealthResponse`, `ReadyResponse` |
| `vision.py` | (Frontend용 아님) | Vision 서버가 보내는 응답(`VisionPredictResponse`, `BBox`, `InternalMeta`)을 해석하기 위한 내부 전용 형식 |
| `__init__.py` | - | 빈 파일. 패키지 표시용 |

### 4.5 `services/` — 바깥 세상과 실제로 대화하는 코드

`api/` 파일들이 "무엇을 할지 지시"한다면, `services/`는 "**실제로 가서
해오는**" 역할입니다. AWS, Vision 서버, 정부 API, Gemini 등 우리 서버
바깥에 있는 시스템과의 통신이나, 사진 가공 같은 무거운 작업은 전부 여기
모여 있습니다.

| 파일 | 무엇을 하나 |
|---|---|
| `storage.py` | **창구 역할.** `settings.storage_backend` 값("s3" 또는 "local")을 보고 `s3_service`와 `local_storage` 중 어느 쪽을 쓸지 그때그때 골라줌 (`upload_image`/`download_image`/`delete_object` 3개 함수를 그대로 위임) |
| `s3_service.py` | **진짜 AWS S3**와 통신. `build_object_key()`가 `feedback/2026/09/13/{user_id}-{uuid}.jpg` 형태의 키를 만들고, `upload_image`/`download_image`/`delete_object`로 실제 업로드·다운로드·삭제. 연결 실패는 `S3_TIMEOUT`, 그 외 실패는 `S3_UPLOAD_FAILED`/`S3_DOWNLOAD_FAILED`로 변환 |
| `local_storage.py` | AWS 없이 개발할 때 **내 컴퓨터 디스크**(`.local_storage/` 폴더)에 저장. `s3_service`와 완전히 똑같은 함수 이름·의미를 가져서, 위쪽(`storage.py`)에서 보면 어느 쪽을 쓰는지 티가 안 남. 폴더 밖으로 벗어나는 경로(`../../etc/passwd` 같은)는 `_resolve()`에서 차단 |
| `image_processing.py` | **사진 가공.** 업로드된 사진을 Pillow로 실제 디코딩 → EXIF 방향 보정(스마트폰 세로사진이 눕지 않게) → 긴 변이 1920px 넘으면 비율 유지한 채 축소 → JPEG(또는 WebP)로 재인코딩. 투명 PNG는 검은 배경이 아니라 흰 배경으로 합성. 디코딩 자체가 안 되면 `IMAGE_DECODE_FAILED` |
| `image_validation.py` | 사진 가공 **이전** 단계의 가벼운 검사. 브라우저가 보낸 Content-Type이 허용 목록에 있는지, 파일이 비어있지 않은지, 용량 제한을 넘지 않는지만 빠르게 확인 |
| `vision_client.py` | **Vision 서버**(`backend`가 아니라 `vision/` 폴더에 있는 별도 서버)와 HTTP로 통신. `predict()`가 사진을 보내고 대분류/소분류/후보 목록/BBox를 받아옴. Vision 서버가 "중앙에 물체가 없다"고 하면 `VisionNoMainObjectError`를 던져서 analyze.py가 재촬영 응답으로 바꿀 수 있게 함 |
| `public_waste_client.py` | **행정안전부 공공데이터 API**와 통신. 서비스키가 이미 URL-encode된 상태로 발급되는 경우가 많아서 `_decoded_service_key()`가 먼저 `unquote()`한 뒤 httpx가 한 번만 인코딩하게 함(이중 인코딩 버그 방지). 실제 응답은 품목명이 아니라 **지역당 한 행**이고 폐기물 종류별로 컬럼 그룹(`FOD_WST_`/`LF_WST_`/`RCYCL_`/`TMPRY_BULK_WASTE_`)이 나뉘어 있어서, `_GROUP_PREFIX_BY_MAJOR_CATEGORY`로 우리 12개 대분류를 가장 가까운 그룹에 매핑해 그 그룹의 컬럼만 읽음(`extract_disposal_fields()`) |
| `disposal_service.py` | 위 `public_waste_client`를 감싸서, "이 폐기물 종류 + 이 지역"을 조합해 최종 배출 정보를 만듦. `get_disposal_info_or_raise()`(직접 조회 API용, 실패하면 오류)와 `get_disposal_info_or_warn()`(이미지 분석용, 실패해도 분석 자체는 성공시키고 `warnings`만 남김) 두 가지 버전 제공 |
| `gemini_service.py` | **Google Gemini**와 통신. `reanalyze_image()`는 "후보 목록에도 없어요" 눌렀을 때 사진을 다시 분석해 17개 클래스 중 하나로 강제 매핑(허용 목록 밖 답은 `GEMINI_BAD_RESPONSE`). `generate_text()`는 챗봇 답변 생성용. 키가 없으면 호출 전에 `GeminiNotConfiguredError` |
| `__init__.py` | - | 빈 파일. 패키지 표시용 |

### 4.6 `agent/` — AI 챗봇 (후속 질문 답변)

사용자가 분석 결과를 보고 "라벨이 안 떨어지면 어떻게 버려요?"처럼 추가로
물어볼 때 답변을 만드는 코드입니다. **대화 내용은 저장하지 않습니다**
(질문할 때마다 그 자리에서 다시 계산 — DB에 채팅 테이블 자체가 없음).

| 파일 | 하는 일 |
|---|---|
| `service.py` | 실제로 답변을 만드는 메인 로직(`answer_question`). 1) 이 feedback이 최종적으로 어떤 폐기물인지 확인(`_current_class`) → 2) 사용자 지역의 배출 정보를 최선을 다해 조회(실패해도 계속 진행) → 3) `tools.py`의 팁을 가져와서 → 4) Gemini에게 물어보거나, 키가 없으면 `_fallback_answer()`로 미리 정해둔 문장을 조립 |
| `tools.py` | `retrieve_tips(major_category)` — 폐기물 대분류별로 미리 준비해둔 "분리배출 팁" 모음(플라스틱류, 유리병, 캔류 등). 정식 RAG(검색증강생성) 대신 쓰는 간단한 참고자료 모음 |
| `prompts.py` | `build_chat_prompt(...)` — Gemini에게 보낼 질문 문장의 "틀(템플릿)". 분석 결과 + 지역 + 배출정보 + 팁 + 사용자 질문을 하나의 프롬프트로 조립 |
| `__init__.py` | - | 빈 파일. 패키지 표시용 |

### 4.7 `db/` — 데이터베이스 초기 데이터 채워 넣기

서버를 처음 켤 때, "서울 25개 구 + 경기 31개 시·군" 목록과 "17개 폐기물
분류" 목록을 데이터베이스에 자동으로 넣어주는 코드입니다. 이미 들어있으면
값만 최신화하고 중복으로 넣지 않습니다(멱등성 — 몇 번을 실행해도 결과가 같음).

| 파일 | 하는 일 |
|---|---|
| `taxonomy_loader.py` | `load_regions()`/`load_waste_classes()` — `data/taxonomy/*.json`(지역 목록, 폐기물 분류 목록)을 읽어 Python 자료구조로 반환. `@lru_cache`로 한 번만 읽고 재사용 |
| `seed.py` | `seed_regions()`/`seed_waste_classes()`/`seed_all()` — 읽어온 목록을 실제 `regions`/`waste_classes` 테이블에 INSERT하거나(없으면), 이미 있으면 값만 UPDATE |
| `__init__.py` | - | 빈 파일. 패키지 표시용 |

### 4.8 `tests/` — "제대로 동작하는지" 자동으로 확인하는 코드

사람이 매번 Postman으로 클릭해가며 확인하지 않아도, 이 폴더의 코드를
실행하면 **17개 API가 명세서대로 동작하는지 자동으로 검사**합니다. 실행:

```bash
cd backend
uv run pytest tests/ -q
```

| 파일 | 무엇을 검사하나 |
|---|---|
| `conftest.py` | 모든 테스트가 공유하는 준비물. **임시 SQLite 파일**을 DB로 쓰도록 환경변수를 미리 세팅하고(진짜 MySQL 없이 테스트 가능), `client`(FastAPI TestClient) · `db_session` · `signup_and_login`(회원가입+로그인을 한 번에 해주는 헬퍼) 픽스처 제공 |
| `test_auth.py` | 회원가입/로그인/로그아웃, 중복 이메일, 잘못된 비밀번호 |
| `test_regions.py` | 지역 목록 56개/필터/변경, 지원 안 하는 시·도 거부 |
| `test_health_and_profile.py` | `/health`·`/ready`, 내 프로필 조회, 만료/위조 토큰 거부 |
| `test_analyze.py` | 이미지 분석의 모든 경우의 수 — 성공, 저신뢰도 재촬영, 중앙객체없음 재촬영, DB 트랜잭션 실패 시 롤백+S3 보상삭제, 공공데이터 API 실패해도 분석은 성공 |
| `test_image_processing.py` | 사진이 실제로 1920px 이하로 축소되는지(비율 유지, 확대는 안 함), 용량이 실제로 줄어드는지, 투명 PNG가 흰 배경으로 합성되는지, 깨진 파일은 거부되는지 |
| `test_feedback.py` | "맞아요" 확정, 다른 후보 선택, 이미 처리된 피드백 재처리 거부 |
| `test_feedback_not_in_list.py` | Gemini 재분석 — 성공, 허용 클래스 밖 응답 거부, Gemini 오류 4종(NOT_CONFIGURED/TIMEOUT/BAD_RESPONSE/UNAVAILABLE) 각각의 매핑 |
| `test_disposal_and_chat.py` | 분리배출 정보 조회, 챗봇 질문(소유권·지역 확인 포함) |
| `test_favorites.py` | 즐겨찾기 등록/조회/삭제, 다른 사용자 즐겨찾기는 안 보임 |
| `test_storage_backends.py` | S3 저장소 ↔ 로컬 저장소 전환이 매끄러운지, 로컬 저장소가 경로 탈출 공격을 막는지 |
| `test_datetime_format.py` | 모든 시각이 `2026-09-11T09:00:00Z` 처럼 UTC 표기로 나가는지 |
| `test_error_contract.py` | 17개 엔드포인트가 전부 등록되어 있는지, 인증이 필요한 API가 실제로 401을 내는지, 모든 오류 응답이 5개 필드(`success/code/message/details/request_id`)를 갖추는지, `X-Request-ID`가 항상 붙는지 |
| `test_database_error_contract.py` | DB 연결이 끊겨도 `500`이 아니라 정해진 대로 `503 DATABASE_ERROR`가 나가는지 |
| `test_services_unit.py` | 개별 부품 단위 검사 — 공공데이터 응답 해석, 서비스키 디코딩, Gemini 응답 파싱 등 |

> `.pytest_cache/`, `__pycache__/` 폴더는 실행하면 자동 생성되는 임시
> 산출물입니다. 신경 쓰지 않아도 되고, 지워도 다시 생깁니다.

---

## 5. 최상위 파일 설명

| 파일 | 설명 |
|---|---|
| `main.py` | **서버의 시작점.** `api/`의 라우터 9개를 전부 조립하고, `RequestIDMiddleware`·CORS·오류 처리 핸들러를 등록하고, 서버가 켜질 때(`lifespan`) DB 표를 만들고 초기 데이터를 채우는 일까지 지휘한다. `uvicorn main:app` 명령으로 이 파일을 실행하면 서버가 뜬다 |
| `pyproject.toml` | 이 프로그램을 돌리는 데 필요한 라이브러리(부품) 목록과 최소 버전. `uv sync`가 이 목록을 보고 필요한 것들을 설치한다 (FastAPI, SQLAlchemy, boto3, Pillow, PyJWT, bcrypt, google-genai 등) |
| `test_image.jpg` | 개발 중 실제 사진으로 분석 흐름을 확인해볼 때 쓰는 샘플 이미지(스테인리스 주전자 사진) |

> 💡 **`.env`/`.env.example`은 `backend/` 안이 아니라 저장소 루트**
> (`recycling_ssg/.env`)에 있습니다. `core/config.py`가 실행 위치(cwd)와
> 무관하게 항상 "저장소 루트의 `.env`"를 절대경로로 찾아 읽도록 되어 있어서,
> `backend/` 안에서 서버를 켜든 루트에서 켜든 같은 설정 파일 하나만 관리하면
> 됩니다. (Vision 서비스는 `vision/.env`를 따로 씁니다 — 모델 경로 등
> Vision 고유 설정이라 분리되어 있습니다.)

---

## 6. 요청 하나가 실제로 지나가는 길 (예시 2가지)

### 6-1. "사용자가 폐기물 사진을 올렸을 때" (`POST /api/v1/analyze`)

```
① 앱이 사진을 첨부해 POST /api/v1/analyze 요청을 보냄
        │
② main.py 가 요청을 받아서 api/analyze.py 의 담당 함수로 연결
        │
③ core/deps.py 가 "이 사람 로그인 맞아?" 확인 (JWT 토큰 검사)
        │    → 지역을 아직 선택 안 했으면 여기서 409 USER_REGION_REQUIRED
        │
④ services/image_validation.py 가 "빈 파일 아님? Content-Type 맞음? 용량 이내?" 1차 검사
        │
⑤ services/image_processing.py 가 사진을 실제로 디코딩(→ 깨진 파일이면 여기서 400)
        │    → EXIF 방향 보정 → 1920px 이하로 축소 → JPEG로 재인코딩
        │
⑥ services/vision_client.py 가 압축된 사진을 Vision 서버로 전송
        │        (Vision 서버는 backend가 아닌 별도 폴더/서버: vision/)
        │        → "플라스틱류/플라스틱, 확신도 0.81" 같은 답이 옴
        │
⑦ 중앙 객체 자체를 못 찾았으면
        │   → schemas/analyze.py 의 AnalyzeRetakeResponse 형식으로
        │     "재촬영해주세요"(AI_NO_MAIN_OBJECT) 응답 (HTTP 200, S3/DB 저장
        │     없음 — 저장할 예측값 자체가 없음), 끝
        │   중앙 객체를 찾았으면 → 다음 단계 계속 (확신도와 무관하게 저장은 함)
        │
⑧ services/storage.py 가 압축된 사진을 S3(또는 로컬)에 저장
        │
⑨ models/image.py, models/feedback.py, models/feedback_candidate.py
   설계도대로 데이터베이스에 분석 결과를 기록 (하나의 트랜잭션)
        │    → 이 중 하나라도 실패하면 전부 롤백 + 방금 올린 S3 사진도 삭제
        │
⑩ 확신도가 낮으면(<0.5)
        │   → ⑨에서 저장은 이미 끝난 상태로, AnalyzeRetakeResponse 형식으로
        │     "재촬영해주세요"(AI_LOW_CONFIDENCE) 응답, 끝
        │     (재학습 데이터 수집 목적 — 저장된 행의 feedback_id도 응답에 포함)
        │   확신도가 충분하면 → 다음 단계 계속
        │
⑪ services/disposal_service.py 가 "이 지역 + 이 폐기물"의 배출 요일을 조회
        │    (이게 실패해도 분석 자체는 성공 처리, disposal_day만 null)
        │
⑫ schemas/analyze.py 의 AnalyzeSuccessResponse 형식에 맞춰
   최종 결과를 JSON으로 만들어 앱에 응답
```

### 6-2. "사용자가 분석 결과를 다른 걸로 정정할 때" (`POST /api/v1/feedback/{id}/select-candidate`)

```
① 앱이 "이 후보가 맞아요"라며 class_id 를 담아 요청
        │
② api/feedback.py 의 select_candidate() 함수로 연결
        │
③ _load_owned_feedback() 가 3단계로 확인:
        │   - feedback_id 가 존재하나? 없으면 404 FEEDBACK_NOT_FOUND
        │   - 내가 만든 feedback 맞나? 아니면 403 FEEDBACK_FORBIDDEN
        │   - 아직 미확정 상태인가? 이미 확정됐으면 409 FEEDBACK_ALREADY_COMPLETED
        │
④ 고른 class_id 가 최초 예측과 같으면 → 400 FEEDBACK_SAME_AS_PREDICTION
   ("맞다고 확인해주세요" 안내, confirm API를 쓰라는 뜻)
        │
⑤ 고른 class_id 가 분석 당시 Top-K 후보 목록(feedback_candidates)에
   실제로 있었는지 확인 → 없으면 400 FEEDBACK_INVALID_CANDIDATE
        │
⑥ 전부 통과하면 feedback 테이블 갱신:
   final_class_id=고른 값, is_correct=False, correction_source="USER"
        │
⑦ schemas/feedback.py 의 SelectCandidateResponse 형식으로 응답
```

이 전체 과정 중 어디서 문제가 생기든(사진이 이상함, S3 연결 실패, DB
오류 등) `core/exceptions.py`가 항상 같은 모양의 오류 메시지로 바꿔서
응답합니다.

---

## 7. 실제 배포 DB 스키마와 코드를 맞춘 이력 (2026-09-13)

Railway에 이미 만들어져 있던 `recycling_ssg` DB는 `models/` 폴더의 설계도로
**자동 생성된 것이 아니라, 누군가 직접 설계해서 만든 테이블**이었습니다.
실제로 비교해보니 `models/` 코드와 아래 두 군데가 달랐습니다.

| 테이블 | 실제 DB (Railway) | 원래 코드(models/) | 조치 |
|---|---|---|---|
| `images` | `user_id`, `created_at` 컬럼 자체가 없음 (`image_id`/`s3_key`/`content_type`만 있음) | `user_id`, `created_at` 컬럼이 있었음 | **코드를 실제 DB에 맞춰 두 컬럼 제거.** 이미지 소유자는 `feedback.user_id`로 이미 충분히 추적되므로 기능 손실 없음 |
| `feedback_candidates` | 기본키가 `(feedback_id, candidate_rank)` 복합키이고, 컬럼명이 `rank`가 아니라 `candidate_rank` | 별도의 `id` 자동증가 기본키 + `rank`라는 이름의 컬럼 | **코드를 실제 DB에 맞춰 수정.** Python에서는 여전히 `.rank`로 쓰지만(`mapped_column("candidate_rank", ...)`) 실제 DB 컬럼명만 `candidate_rank`로 매핑 |

고치기 전에는 `/api/v1/analyze`가 실제로 이 DB에 저장을 시도하면
`Unknown column 'rank' in 'field list'` 같은 오류로 **무조건 실패**했습니다
(로컬 SQLite 테스트 DB는 코드가 직접 만드는 표라 이 문제가 드러나지
않았습니다). 실제 라이브 DB에 트랜잭션+롤백으로 재검증해서 지금은 문제
없이 저장되는 것을 확인했습니다.

또한 실제 DB의 `feedback` 테이블에는 코드에는 없는 **`review_status`
(PENDING/APPROVED/REJECTED)** 컬럼이 있는데, 이건 "나중에 사람이 이 피드백을
재학습용 데이터로 써도 되는지 검수하는 상태"를 위한 컬럼으로 보입니다
(요구사항 정의서 BR-06 "지속적인 모델 개선"과 관련). 우리 API 어디에서도
이 값을 직접 다루지 않고, DB가 자동으로 `PENDING` 기본값을 채워주기 때문에
**지금 당장 코드를 바꿀 필요는 없습니다** — 다만 나중에 "피드백 검수/승인"
관리자 기능을 만들게 되면 이 컬럼을 그때 활용하면 됩니다.

실제 DB는 이외에도 CHECK 제약조건(`chk_feedback_result_state` 등)으로
"미응답=전부 NULL / 확정=is_correct TRUE+final_class_id=predicted_class_id
+correction_source NULL / 정정=is_correct FALSE+final_class_id NOT NULL+
correction_source NOT NULL" 규칙을 DB 레벨에서도 강제하고 있는데, 우리
`api/feedback.py`의 로직이 정확히 이 규칙대로 값을 채우기 때문에 문제없이
통과합니다.

> ⚠️ **`AUTO_CREATE_TABLES=true`는 "없는 표만 만들고, 이미 있는 표는 절대
> 건드리지 않습니다"**(SQLAlchemy `create_all()`의 동작). 그래서 위 표처럼
> 실제 DB와 모델이 어긋나 있어도 서버는 조용히 켜지고, 실제로 그 표에
> INSERT/SELECT를 시도하는 순간에야 오류가 드러납니다. 앞으로 모델을
> 고치거나 새 컬럼을 추가할 때는, **로컬 SQLite 테스트만으로 안심하지 말고
> 실제 MySQL(Railway)에서도 한 번은 직접 확인**하는 걸 권장합니다.

---

## 8. 겪었던 문제와 해결 이력 (트러블슈팅 일지)

나중에 비슷한 문제를 또 만났을 때 빨리 알아볼 수 있도록 남겨둡니다.

### 8-1. `torch`/`torchvision` import 오류 (`NP_SUPPORTED_MODULES`)

**증상**: `import torchvision`이 `ImportError: cannot import name
'NP_SUPPORTED_MODULES' from 'torch._dynamo.utils'`로 실패.

**원인**: torch 2.11.x가 numpy 2.4 이상과 호환되지 않음. torch 내부의
numpy 연동 코드가 import 실패하는데, 그 실패를 감싸는 `except ImportError:
pass`가 진짜 원인을 조용히 삼켜버려서 엉뚱한 데서 오류가 남.

**해결**: 저장소 루트 `pyproject.toml`에 `numpy>=2.3,<2.4`로 상한선 고정.
(원인 분석 과정은 저장소 루트 커밋 이력 참고)

### 8-2. Windows "애플리케이션 제어 정책"이 `python.exe` 실행을 차단

**증상**: `.venv/Scripts/python.exe`를 실행만 하면 `Permission denied`
(Git Bash) / `애플리케이션 제어 정책에서 이 파일을 차단했습니다` (PowerShell).
`uv`나 `ruff`(둘 다 Python이 아닌 네이티브 실행 파일)는 멀쩡히 동작해서
더 헷갈렸음.

**원인**: 정확한 원인은 불명(Windows Defender Application Control /
Smart App Control 계열로 추정). 특정 `.venv`의 `python.exe` 파일 자체가
찍혀서 차단된 것으로 보이고, 그 `.venv`를 쓰던 VS Code Jupyter 커널
프로세스들이 파일을 물고 있어 더 꼬여 있었음.

**해결**: (1) 그 `.venv`를 쓰던 Jupyter 커널 프로세스를 종료해 파일 잠금
해제 → (2) `.venv` 폴더 통째로 삭제 → (3) `uv sync --all-packages`로
처음부터 새로 생성 → 정상 동작 확인. **같은 증상이 다시 나타나면 이
순서를 그대로 따라 하면 됩니다.**

### 8-3. `.env`가 어디 있는지 헷갈림 (`backend/.env` vs 루트 `.env`)

처음에는 `backend/.env`를 썼는데, 팀에서 저장소 루트에 `.env`를 두는
방식으로 통일하기로 해서 `core/config.py`가 **cwd와 무관하게 항상 저장소
루트의 `.env`를 절대경로로 찾도록** 바꿨습니다(2번 항목 참고). `vision/`은
여전히 자기 폴더 안의 `vision/.env`를 따로 씁니다.

---

## 9. 자주 나오는 용어 풀이

| 용어 | 쉬운 설명 |
|---|---|
| **API / 엔드포인트** | 앱이 서버에게 "이거 해줘"라고 부탁할 때 쓰는 정해진 주소. 예: `POST /api/v1/analyze` |
| **JWT (JSON Web Token)** | 로그인하면 발급되는 "디지털 출입증". 이후 요청마다 이 출입증을 같이 보내면 서버가 "아, 로그인한 사람이구나" 하고 알아본다 |
| **ORM (models/ 폴더)** | 데이터베이스의 표(table)를 Python 코드로 다룰 수 있게 해주는 방식(여기서는 SQLAlchemy). SQL 문을 직접 안 써도 됨 |
| **스키마 (schemas/ 폴더)** | 요청/응답 JSON이 지켜야 할 형식 규칙(여기서는 Pydantic). "이 필드는 꼭 있어야 한다", "이건 숫자여야 한다" 등 |
| **의존성(Dependency, FastAPI 용어)** | `core/deps.py`의 `get_current_user`처럼, API 함수가 실행되기 **전에** 자동으로 먼저 실행되어 값을 준비해주는 함수. "로그인 확인", "DB 연결 준비" 같은 공통 작업을 반복해서 안 써도 되게 해줌 |
| **미들웨어** | 모든 요청이 공통으로 거쳐가는 중간 관문. 이 프로젝트에선 "추적번호 붙이기"에 사용 |
| **환경변수 / .env** | 코드에 직접 적으면 위험한 값(비밀번호, API 키)을 코드 밖 별도 파일에 보관하는 방식 |
| **S3** | 아마존이 제공하는 "사진/파일 보관 창고" 서비스. 우리 DB에는 파일 자체가 아니라 "S3의 몇 번 칸에 있는지"(경로, `s3_key`)만 저장 |
| **Vision 서버** | 사진을 보고 "이게 무슨 쓰레기인지" 알아맞히는 AI(YOLO 모델)가 돌아가는 별도 서버. `backend/`가 아니라 저장소의 `vision/` 폴더에 있다 |
| **Gemini** | Google의 생성형 AI. 우리 서비스에서는 (1) 일반 AI가 못 맞췄을 때 "한 번 더 봐줘"라고 요청하는 보조 수단, (2) 챗봇 후속 질문 답변 생성 두 곳에만 사용 |
| **멱등성(idempotent)** | 몇 번을 반복 실행해도 결과가 똑같은 성질. `db/seed.py`가 서버를 100번 재시작해도 지역/분류 데이터가 중복되지 않는 이유 |
| **트랜잭션 / 롤백** | 여러 DB 작업(예: 사진 기록 + 분석 결과 기록 + 후보 목록 기록)을 "전부 성공하거나 전부 취소"로 묶는 것. 중간에 하나라도 실패하면 이미 처리된 것까지 전부 되돌림(롤백) |
