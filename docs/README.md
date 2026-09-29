# 문서 안내

recycling_ssg(분리쏙) 프로젝트의 전체 문서 인덱스입니다.

---

## 폴더 구조

```
docs/
├── specifications/     프로젝트 정의부터 오류 명세까지 — 기획/설계 문서 세트 (14종)
│   └── images/          다이어그램 5종 문서의 렌더링 이미지(.png) + 소스(.mmd)
├── troubleshooting/     환경설정·실행·알려진 코드 상태 트러블슈팅
├── deployment/           배포 절차 및 배포 관련 트러블슈팅
├── BENCHMARKING.md        타 팀 프로젝트 벤치마킹 — 장단점 및 분리쏙 적용점 정리
├── API_SPEC.md            (기존) 구현 기준 API 상세 명세 v6.1 — RAG 연동 이전 스냅샷
├── API_SPEC.docx          위 문서의 Word 버전
├── API_TEST_COMMANDS.md   19개 API curl/PowerShell 테스트 명령어 모음 + 실제 응답 예시
├── DATABASE_SCHEMA.md     (기존) 실제 배포 DB 스키마 조사 문서 — ERD/데이터 명세서의 원본 근거
└── README.md              이 문서
```

> **Mermaid 다이어그램이 들어간 5개 문서**(06/07/08/09/12)는 Mermaid를 렌더링하지 못하는 도구
> (Word, PPT, 일부 PDF 뷰어 등)에서도 볼 수 있도록, 각 다이어그램 아래에 **렌더링된 PNG 이미지**를
> 함께 넣었고, 문서 전체를 **PDF로도 내보내** 같은 파일명의 `.pdf`로 나란히 두었습니다
> (예: `06-user-flow.md` ↔ `06-user-flow.pdf`). 개별 다이어그램 이미지와 편집 가능한 Mermaid
> 소스(`.mmd`)는 `specifications/images/`에 있습니다 — 발표자료(PPT)에 낱장으로 붙여넣을 때는
> 이 폴더의 PNG를 바로 사용하면 됩니다.

> `API_SPEC.md`/`DATABASE_SCHEMA.md`/`API_TEST_COMMANDS.md`는 이번 문서화 작업 이전부터 있던
> **원본 엔지니어링 조사 문서**입니다. `specifications/` 세트는 이 문서들과 실제 코드베이스를
> 다시 검증해 정식 산출물 형식(요구사항 정의서, API 명세서 등)으로 재구성한 것이며, 세부 curl
> 예시처럼 중복이 불필요한 내용은 원본 문서를 참조하도록 링크로 연결해두었습니다. RAG 서비스
> 연동(배출방법 규정 조회, AI Agent 답변 생성, Gemini 재분류) 이후 변경된 부분은
> `specifications/10-api-specification.md`·`15-error-specification.md`가 최신 기준입니다.

---

## `specifications/` — 기획·설계 문서 14종

| 문서 | 내용 |
|---|---|
| [01-project-definition.md](specifications/01-project-definition.md) | 프로젝트 정의서 — 배경, 목표, 범위 |
| [02-requirements-definition.md](specifications/02-requirements-definition.md) | 요구사항 정의서 — 기능/비기능 요구사항 목록(ID 부여) |
| [03-user-scenarios.md](specifications/03-user-scenarios.md) | 사용자 시나리오 — 페르소나 3종 + 시나리오 |
| [04-requirements-specification.md](specifications/04-requirements-specification.md) | 요구사항 명세서 — 요구사항별 입력/처리/출력/예외 상세 |
| [05-functional-specification.md](specifications/05-functional-specification.md) | 기능 명세서 — 화면별 상세 동작(UI 상태, 검증, 알려진 목업) |
| [06-user-flow.md](specifications/06-user-flow.md) · [PDF](specifications/06-user-flow.pdf) | 사용자 흐름도 — 화면 간 이동 흐름(Mermaid + 이미지) |
| [07-flowchart.md](specifications/07-flowchart.md) · [PDF](specifications/07-flowchart.pdf) | 순서도 — 핵심 API 내부 분기 로직(Mermaid + 이미지) |
| [08-sequence-diagram.md](specifications/08-sequence-diagram.md) · [PDF](specifications/08-sequence-diagram.pdf) | 시퀀스 다이어그램 — 서버 간 호출 순서(Mermaid + 이미지) |
| [09-service-architecture.md](specifications/09-service-architecture.md) · [PDF](specifications/09-service-architecture.pdf) | 서비스 아키텍처 — 4개 프로세스 구성, 모듈 구조, 장애 격리(Mermaid + 이미지) |
| [10-api-specification.md](specifications/10-api-specification.md) | API 명세서 — 19개 엔드포인트 + RAG 내부 API 필드 계약 |
| [11-data-specification.md](specifications/11-data-specification.md) | 데이터 명세서 — 테이블/JSON/S3/JWT/벡터DB 데이터 정의 |
| [12-erd.md](specifications/12-erd.md) · [PDF](specifications/12-erd.pdf) | ERD — 7개 테이블 관계도 및 설계 결정(Mermaid + 이미지) |
| [13-ai-model-yolo.md](specifications/13-ai-model-yolo.md) | AI 모델 명세서(YOLO) — 아키텍처, 학습 실험, 추론 파이프라인 |
| [15-error-specification.md](specifications/15-error-specification.md) | 오류 명세서 — 전체 오류 코드 카탈로그 + 발생 매트릭스 |

> **14번(AI 모델 명세서 — Faster R-CNN)은 포함되지 않습니다.** 이 프로젝트는 YOLO 단일 아키텍처로
> 진행되어 Faster R-CNN 학습 코드/실험 결과가 존재하지 않기 때문입니다.

### 읽는 순서 추천

- **처음 프로젝트를 파악한다면**: 01 → 02 → 03 → 06 순서로 "무엇을, 왜, 어떻게 쓰는지"부터.
- **개발자로 합류한다면**: 09(아키텍처) → 10(API) → 11/12(데이터) → 08(시퀀스) → 07(플로우차트).
- **AI 모델을 다룬다면**: 13 → [troubleshooting](troubleshooting/README.md) §3.5(배포 체크포인트 추적 불가).

---

## `troubleshooting/` — 트러블슈팅

[troubleshooting/README.md](troubleshooting/README.md) — 환경설정/실행 이슈 + 코드 조사로 확인된
알려진 이슈(비활성화된 검증 로직, 미연동 목업 데이터 등)를 정리했습니다.

## `deployment/` — 배포

[deployment/README.md](deployment/README.md) — 4개 프로세스(Frontend/Backend/Vision/RAG) 수동
배포 절차, 환경변수, 기동 순서, 배포 관련 트러블슈팅. 현재 Docker/CI 자동화는 구성되어 있지
않으며, 이 문서에 향후 과제로 기록했습니다.

---

## 관련 코드 위치 요약

| 영역 | 경로 |
|---|---|
| Frontend | `frontend/` (React 19 + Vite) |
| Backend | `backend/` (FastAPI, 공개 API 17개) |
| Vision | `vision/` (FastAPI + YOLO, 내부 API 2개) |
| RAG 서비스 | `rag/` (FastAPI + LangGraph, 내부 API 3개) |
| 모델 학습/실험 | `ai/` (서비스 런타임과 무관, 학습 산출물 저장소) |
| 분류/지역 Master 데이터 | `data/taxonomy/` |
| 실행 스크립트 | `scripts/` |
