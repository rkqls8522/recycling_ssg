# recycling_ssg

**AI 기반 생활폐기물 스마트 분류 서비스**

폐기물을 촬영하면 Vision AI가 종류를 인식하고, 사용자가 선택한 지역 기준의 올바른
분리배출 방법을 안내합니다. AI가 틀렸을 때는 사용자가 후보 목록에서 직접 보정하거나
Gemini 재분석(Fallback)을 요청할 수 있고, 추가 궁금증은 AI Agent에게 대화로 물어볼 수
있습니다.

`recycling_ssg_API_상세명세서_v6.0` 과 `생활폐기물분류_요구사항정의서` 에 정의된
**19개 API(Backend 17 + Vision AI 2)** 의 구현체입니다.

---

## 목차

- [시스템 구성](#시스템-구성)
- [기술 스택](#기술-스택)
- [빠른 시작](#빠른-시작)
- [API 목록](#api-목록)
- [핵심 도메인 규칙](#핵심-도메인-규칙)
- [테스트](#테스트)
- [환경 변수](#환경-변수)
- [프로젝트 구조](#프로젝트-구조)
- [트러블슈팅](#트러블슈팅)

---

## 시스템 구성

```
React Frontend
   │  HTTPS  /api/v1/*
   ▼
┌─────────────────────────────────────────────┐
│ backend/   FastAPI  (17 endpoints)          │
│   ├── MySQL            회원/분석/피드백/즐겨찾기 │
│   ├── AWS S3           원본 이미지 (s3_key만 DB 저장) │
│   ├── 행정안전부 API    지역별 배출요일/방법        │
│   └── Gemini / Agent   Fallback 재분석, 후속 질문  │
└─────────────────────────────────────────────┘
   │  HTTP  /internal/v1/*   ← 사설망 전용, Frontend 직접 호출 금지
   ▼
┌─────────────────────────────────────────────┐
│ vision/    FastAPI + YOLO  (2 endpoints)    │
│   중앙 메인 객체 탐지 → Top-K 후보 + BBox        │
└─────────────────────────────────────────────┘
```

### 전체 서비스 흐름

```
촬영/업로드 → Vision AI 객체 탐지 → 메인 객체 결정
                                          │
             ┌────────────────────────────┴───────────┐
             │ 중앙 객체 없음                              │
             │  → HTTP 200 RETAKE_REQUIRED (재촬영 안내)   │
             │  → S3/DB 에 아무것도 저장하지 않음            │
             └──────────────────────────────────────────┘
                                          │ 메인 객체 있음
                                          ▼
   S3 업로드 → images/feedback/feedback_candidates INSERT (1 트랜잭션)
                                          │
             ┌────────────────────────────┴───────────┐
             │ Confidence 확인                            │
             │ Top-1 < 0.5                                │
             │  → HTTP 200 RETAKE_REQUIRED (재촬영 안내)   │
             │  → 저장은 위에서 이미 완료(재학습 데이터 수집) │
             └──────────────────────────────────────────┘
                                          │ Top-1 >= 0.5
                                          ▼
             대분류·소분류 + Top-K 후보 + 지역별 배출요일 반환
                                  ▼
                  "위 물건이 맞나요? 아니라면 골라주세요"
         ┌────────────────┬──────────────────┬─────────────────────┐
         │ 예             │ 다른 후보 선택      │ "여기에 없어요"        │
         ▼                ▼                  ▼
   is_correct=TRUE   is_correct=FALSE    Gemini 이미지 재분석
   source=NULL       source=USER         is_correct=FALSE, source=GEMINI
         └────────────────┴──────────────────┴─────────────────────┘
                                  ▼
                    최종 Class 기준 분리배출 안내 → AI Agent 추가 질문
```

---

## 기술 스택

| 영역 | 스택 |
|---|---|
| Backend | Python 3.13, FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| DB | MySQL |
| Vision AI | Ultralytics YOLO, PyTorch (17 class Object Detection) |
| Vision LLM | Gemini (`google-genai`) — 후보에 없을 때만 호출 |
| AI Agent | 분석 컨텍스트 + RAG 지식 기반 Stateless 응답 |
| Storage | AWS S3 (boto3) / 개발용 로컬 디스크 |
| 인증 | JWT (PyJWT) + bcrypt |
| 패키지 관리 | uv (workspace) |

---

## 빠른 시작

### 1. 의존성 설치

> ⚠️ **반드시 `--all-packages` 를 붙이세요.** `uv sync` 만 실행하면 workspace member인
> `backend` 의 의존성(SQLAlchemy, PyJWT, boto3 등)이 **제거**됩니다.

```bash
uv sync --all-packages
```

### 2. 개발 서버 2개 기동 (`run-dev`)

`scripts/run-dev.sh` 는 **Vision(:8100)과 Backend(:8000)를 한 번에 띄워주는 스크립트**입니다.
하는 일은 4가지입니다.

1. YOLO 체크포인트를 자동 탐색 (`weights/best.pt` → `ai/models/yolo/*/runs/*/weights/best.pt`)
2. Vision 서버 기동 후, Backend 가 그 주소를 바라보도록 연결
3. **개발용 설정 주입** — S3 이미지 저장(배포와 동일) + 테이블 생성/Master 시딩 자동 실행
   (DB는 항상 `.env`의 MySQL `DATABASE_URL`을 그대로 사용 — 이 스크립트가 덮어쓰지 않음)
4. 두 서버가 `/health` 200 을 낼 때까지 기다렸다가 준비 완료를 알림
   (로그는 `.dev-logs/`, Ctrl+C 로 둘 다 종료)

MySQL(`DATABASE_URL`)과 AWS 자격증명(`AWS_*`)은 `.env`에 항상 설정되어 있어야
합니다 — 이미지는 배포와 동일하게 실제 S3에 저장됩니다. AWS 없이 돌려야 하면
`STORAGE_BACKEND=local bash scripts/run-dev.sh` 로 로컬 디스크 저장으로 우회할
수 있습니다(그러면 `images.s3_key` 가 가리키는 파일이 S3 에 없게 됩니다).

```bash
bash scripts/run-dev.sh          # Git Bash
```
```powershell
.\scripts\run-dev.ps1            # PowerShell
```

- Backend: <http://127.0.0.1:8000> · Swagger UI: <http://127.0.0.1:8000/docs>
- Vision: <http://127.0.0.1:8100>

> Vision 모델은 `weights/best.pt` → `ai/models/yolo/*/runs/*/weights/best.pt` 순으로
> 자동 탐색합니다. **운영에 쓸 체크포인트를 `weights/best.pt` 로 복사**하거나
> `MODEL_PATH` 환경변수로 지정하세요.

### 3. 전체 API 검증

```bash
bash scripts/smoke-test.sh
```
```
===== 결과 =====
  PASS: 99
  FAIL: 0
  SKIP: 0
```

필드 정의·오류 코드 전체를 보려면 → **[docs/API_SPEC.md](docs/API_SPEC.md)**
(19개 엔드포인트의 요청/응답 필드표, 오류 코드 카탈로그, Frontend 연동 가이드. Word 버전: `docs/API_SPEC.docx`)

엔드포인트별로 하나씩 실행해 보려면 → **[docs/API_TEST_COMMANDS.md](docs/API_TEST_COMMANDS.md)**
(19개 API 전부에 대해 헤더·본문이 채워진 curl/PowerShell 명령어와 실제 응답 예시)

---

## API 목록

Base URL: `http://<host>/api/v1` · 인증: `Authorization: Bearer <JWT>`

| # | Method | Endpoint | Auth | 기능 |
|---|---|---|---|---|
| 1 | GET | `/health` | ✗ | Backend liveness |
| 2 | GET | `/ready` | ✗ | DB 포함 readiness |
| 3 | POST | `/api/v1/auth/signup` | ✗ | 회원가입 (지역은 받지 않음) |
| 4 | POST | `/api/v1/auth/login` | ✗ | 로그인 → JWT 발급 |
| 5 | POST | `/api/v1/auth/logout` | ✓ | 로그아웃 (204) |
| 6 | GET | `/api/v1/users/me` | ✓ | 내 프로필 |
| 7 | GET | `/api/v1/regions` | ✗ | 지원 지역 56개 (서울 25 + 경기 31). 로그인 전 지역 선택 UI 용 |
| 8 | PATCH | `/api/v1/users/me/region` | ✓ | 지역 선택/변경 |
| 9 | POST | `/api/v1/analyze` | ✓ | 이미지 분석 + S3/DB 저장 + 배출요일 |
| 10 | POST | `/api/v1/feedback/{id}/confirm` | ✓ | "예, 맞아요" |
| 11 | POST | `/api/v1/feedback/{id}/select-candidate` | ✓ | 다른 Top-K 후보 선택 |
| 12 | POST | `/api/v1/feedback/{id}/not-in-list` | ✓ | Gemini Fallback 재분석 |
| 13 | GET | `/api/v1/disposal/schedule` | ✓ | 지역별 분리배출 정보 |
| 14 | POST | `/api/v1/chat` | ✓ | AI Agent 후속 질문 (Stateless) |
| 15 | GET | `/api/v1/favorites` | ✓ | 즐겨찾기 조회 |
| 16 | POST | `/api/v1/favorites` | ✓ | 즐겨찾기 등록 (201) |
| 17 | DELETE | `/api/v1/favorites/{id}` | ✓ | 즐겨찾기 삭제 (204) |
| 18 | POST | `/internal/v1/predict` | Backend 전용 | YOLO 중앙 객체 + Top-K |
| 19 | GET | `/internal/v1/classes` | Backend 전용 | Vision taxonomy (17 class) |

### 공통 오류 응답

모든 HTTP 오류는 동일한 형태이며, 모든 응답(성공 포함)에 `X-Request-ID` 헤더가 붙습니다.

```json
{
  "success": false,
  "code": "AUTH_REQUIRED",
  "message": "로그인이 필요합니다.",
  "details": null,
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 핵심 도메인 규칙

| 규칙 | 설명 |
|---|---|
| **재촬영 분기는 오류가 아님** | Top-1 < 0.5 또는 중앙 객체 미탐지 → **HTTP 200** + `RETAKE_REQUIRED`. 중앙 객체 미탐지는 S3/DB에 **아무것도 저장하지 않음**; Top-1 < 0.5 는 재학습 데이터 수집을 위해 SUCCESS 와 동일하게 저장하되 `feedback_id` 는 응답에 노출하지 않음 |
| **저장 순서와 보상 트랜잭션** | S3 업로드 → `images` → `feedback` → `feedback_candidates` 를 한 트랜잭션으로. DB 실패 시 ROLLBACK + **업로드된 S3 객체 보상 삭제** |
| **외부 API 장애 격리** | 공공데이터 API 실패는 분석을 실패시키지 않고 `disposal_day: null` + `warnings[]` 로 응답 |
| **class_id 단일 소스** | `data/taxonomy/waste_classes.json` 이 YOLO 클래스 인덱스와 `waste_classes` 테이블이 공유하는 유일한 기준 |
| **feedback 에 문자열 미저장** | 대/소분류는 `class_id` JOIN 으로 해석. `feedback` 에는 문자열을 저장하지 않음 |
| **미응답 상태 보존** | 사용자가 아무 응답 없이 이탈하면 `final_class_id`/`is_correct`/`correction_source` 는 **NULL 유지** |
| **Gemini 는 Fallback 전용** | 일반 분석 과정에서 호출하지 않고 "여기에 없어요" 일 때만 호출. 결과는 17개 class_id 로 제한 |
| **대화 미저장** | `/api/v1/chat` 은 Stateless. message/answer 를 DB에 저장하지 않음 |
| **S3 는 key 만 저장** | 만료되는 Presigned URL 은 DB에 저장 금지 |
| **업로드 이미지는 항상 재인코딩** | 원본 그대로 저장하지 않고 1920px 이하로 축소 + JPEG(기본)로 재인코딩. Vision 서버와 S3 양쪽에 **같은 처리된 이미지**가 전달됨 |
| **시각 표기** | 모든 Datetime 은 UTC 기준 `2026-09-11T09:00:00Z` 형식 |

---

## 테스트

```bash
# Backend 단위/통합 테스트 (104개) — 외부 서비스 불필요
cd backend && ../.venv/Scripts/python.exe -m pytest tests/ -q

# Vision 테스트 (24개) — 실제 체크포인트가 있으면 실제 추론까지 검증
.venv/Scripts/python.exe -m pytest vision/tests -q

# 실제 서버 대상 전체 API 스모크 테스트 (100개 검사)
bash scripts/smoke-test.sh
```

| 테스트 | 검증 내용 |
|---|---|
| `backend/tests/test_analyze.py` | SUCCESS/저신뢰도/중앙객체없음 분기, DB 롤백 + S3 보상 삭제, 외부 API 장애 시 warnings |
| `backend/tests/test_feedback*.py` | confirm/select-candidate/not-in-list, Gemini 오류 4종 매핑, 소유권 검증 |
| `backend/tests/test_error_contract.py` | 17개 엔드포인트 등록 확인, 인증 요구사항, 오류 Body 5필드, X-Request-ID |
| `backend/tests/test_datetime_format.py` | ISO 8601 UTC(`Z`) 직렬화 |
| `backend/tests/test_storage_backends.py` | S3/로컬 백엔드 전환, path traversal 차단 |
| `vision/tests/test_api.py` | predict/classes/health 응답 계약, 오류 코드 매핑 |
| `vision/tests/test_api_real_model.py` | 실제 체크포인트 로드, taxonomy 일치, 실제 추론 |

---

## 환경 변수

### 내가 직접 만들어야 하는 파일은 2개뿐입니다

| 만들 파일 | 복사 원본 | 채울 내용 | 없으면? |
|---|---|---|---|
| `.env` | `.env.example` | DB 주소, JWT 시크릿, S3 자격증명, 외부 API 키 | 개발 기본값으로 동작(아래 참고) |
| `vision/.env` | `vision/.env.example` | **`MODEL_PATH` 하나만** 신경 쓰면 됩니다 | `weights/best.pt` 를 찾음 |

```bash
cp .env.example .env
cp vision/.env.example  vision/.env
```

> 두 파일 모두 `.gitignore` 에 있어 커밋되지 않습니다. **`.env.example` 은 커밋되므로
> 실제 키를 절대 적지 마세요.**

추가로 챙길 것 하나: **학습된 체크포인트를 `weights/best.pt` 로 복사**하세요.
(`ai/models/yolo/.../runs/<우승 실험>/weights/best.pt`)
`weights/yolo26n.pt` 는 COCO 사전학습 가중치라 **지정하면 안 됩니다** — 17개 폐기물
taxonomy 가 아닌 COCO class 인덱스를 반환해 모든 `class_id` 가 조용히 오염됩니다.

> `scripts/run-dev.sh` 로 개발 서버를 띄워도 `DATABASE_URL`(MySQL)은 항상
> `.env`에서 읽어옵니다. `.env`가 없으면 DB 연결이 안 되니 최소한 `DATABASE_URL`은
> 채워두세요. 이미지 저장도 기본이 S3라 `AWS_*` 도 함께 필요합니다 — `.env` 없이
> 동작하는 것은 체크포인트 자동 탐색뿐입니다.

### .env 항목별 설명

### 필수 (운영)

| 변수 | 설명 |
|---|---|
| `DATABASE_URL` | `mysql+pymysql://user:pw@host:3306/recycling_ssg?charset=utf8mb4` |
| `JWT_SECRET_KEY` | **32바이트 이상** 무작위 문자열 |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` / `AWS_S3_BUCKET` | S3 이미지 저장 |
| `VISION_SERVER_BASE_URL` | 예: `http://vision-host:8100/internal/v1` |

### 이미지 처리 (업로드 시 리사이즈/재인코딩)

| 변수 | 기본값 | 설명 |
|---|---|---|
| `IMAGE_MAX_DIMENSION` | `1920` | 긴 변 기준 이 값을 넘으면 비율 유지한 채 축소 (확대는 안 함) |
| `IMAGE_OUTPUT_FORMAT` | `jpeg` | `jpeg`(호환성 최우선) 또는 `webp`(용량 더 작음)로 재인코딩해 저장 |
| `IMAGE_OUTPUT_QUALITY` | `85` | JPEG/WEBP 인코딩 품질(1~100) |

> S3/Vision 서버 양쪽에 **같은 처리된 이미지**가 전달됩니다(`services/image_processing.py`).
> 실제 저장된 MIME 타입은 `images.content_type` 컬럼에 기록되어, Gemini
> Fallback(`not-in-list`) 재분석 시에도 정확한 타입을 그대로 사용합니다.

### 선택 (없으면 해당 기능이 규정된 오류/대체 동작으로 degrade)

| 변수 | 없을 때 동작 |
|---|---|
| `PUBLIC_WASTE_API_SERVICE_KEY` | `/analyze` 는 `disposal_day: null` + `warnings`, `/disposal/schedule` 은 502 `PUBLIC_WASTE_UNAVAILABLE` |
| `GEMINI_API_KEY` | `not-in-list` 는 503 `GEMINI_NOT_CONFIGURED`, `/chat` 은 결정적 템플릿 답변으로 동작 |

> 공공데이터 서비스키는 **인코딩/디코딩 형태 모두** 넣어도 됩니다 (내부에서 `unquote`
> 후 한 번만 인코딩하여 이중 인코딩 문제를 방지).

### 개발 전용

| 변수 | 설명 |
|---|---|
| `STORAGE_BACKEND=local` | S3 대신 로컬 디스크에 저장 (`s3_key` 의미는 동일). 기본값은 `s3` |
| `LOCAL_STORAGE_DIR` | 로컬 저장 경로 (기본 `./.local_storage`) |
| `AUTO_CREATE_TABLES` / `AUTO_SEED_MASTER_DATA` | 기동 시 테이블 생성 및 지역/폐기물 Master 시딩 |

---

## 프로젝트 구조

```
recycling_ssg/
├── backend/                 FastAPI Public API (17 endpoints)
│   ├── api/                 엔드포인트 라우터
│   ├── core/                설정·DB·보안(JWT/bcrypt)·예외·미들웨어
│   ├── models/              SQLAlchemy ORM (7 테이블)
│   ├── schemas/             Pydantic 요청/응답 스키마
│   ├── services/            S3·Vision·공공데이터·Gemini 클라이언트
│   ├── agent/               AI Agent (프롬프트·RAG·오케스트레이션)
│   ├── db/                  Master 데이터 시딩
│   └── tests/               104개 테스트
├── vision/                  Vision Server (2 internal endpoints)
│   ├── main.py              /internal/v1/predict, /classes, /health
│   ├── inference.py         YOLO 로딩, 중앙 메인 객체 선택, Top-K
│   └── tests/               24개 테스트
├── data/taxonomy/           regions.json(56) · waste_classes.json(17) ← 단일 소스
├── scripts/                 run-dev · stop-dev · smoke-test
├── docs/API_SPEC.md         API 명세서 (.docx 동봉)
├── docs/API_TEST_COMMANDS.md   19개 API 테스트 명령어 모음
└── ai/                      모델 학습/실험 (서비스 런타임과 무관)
```

### DB 스키마 (7 테이블)

```
regions ──< users ──┬──< feedback ──< feedback_candidates
                     └──< favorites
images ─────────────────< feedback
waste_classes ──────────< feedback (predicted_class_id / final_class_id)
waste_classes ──────────< feedback_candidates (class_id)
waste_classes ──────────< favorites (class_id)
```

> `images` 는 `user_id`를 갖지 않습니다 — 소유자는 `feedback.user_id`로
> 추적됩니다(실제 Railway DB 스키마와 맞춘 결과. 상세 배경은
> [`backend/README.md`](backend/README.md#7-실제-배포-db-스키마와-코드를-맞춘-이력-2026-09-13) 참고).

`chat_sessions` / `chat_messages` 는 **사용하지 않습니다** (대화 미저장).

---

## 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| `ModuleNotFoundError: sqlalchemy` 등 | 루트에서 `uv sync` 만 실행해 backend 의존성이 제거됨 → **`uv sync --all-packages`** |
| `ImportError: cannot import name 'NP_SUPPORTED_MODULES'` (torch/torchvision) | torch 2.11 은 **numpy ≥ 2.4 와 호환되지 않음**. 루트 `pyproject.toml` 이 `numpy>=2.3,<2.4` 로 고정하고 있으니 `uv sync --all-packages` 로 재설치 |
| `/internal/v1/predict` 가 503 `VISION_MODEL_NOT_READY` | 체크포인트 없음 → `weights/best.pt` 배치 또는 `MODEL_PATH` 지정 |
| `/analyze` 가 502 `S3_UPLOAD_FAILED` | AWS 자격증명 미설정 → 개발 중이라면 `STORAGE_BACKEND=local` |
| PowerShell 에서 `curl` 문법 오류 | `curl` 이 `Invoke-WebRequest` 별칭 → **`curl.exe`** 사용 |
| Git Bash 에서 `-F "image=@/c/..."` 가 `000` | MinGW curl 이 POSIX 절대경로를 못 엶 → `cygpath -m` 변환 또는 상대 경로 |
| Git Bash 에서 한글 본문이 400 | 인자 인코딩 문제 → 본문을 파일로 저장 후 `--data-binary "@body.json"` |
| PowerShell 응답 한글이 깨짐 | PS 5.1 인코딩 문제 → `[Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray())` |

자세한 셸별 주의사항은 [docs/API_TEST_COMMANDS.md](docs/API_TEST_COMMANDS.md#0-3-️-셸별-함정-실제로-겪은-것들) 참고.
