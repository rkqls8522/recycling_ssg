# 트러블슈팅

**기준일** 2026-09-28

이 문서는 크게 두 가지를 다룹니다.

1. **환경/실행 트러블슈팅** — 개발 환경을 세팅하고 실행하는 과정에서 실제로 겪은 문제와 해결법
2. **알려진 코드 상태(Known Issues)** — 문서 작성 중 코드 조사로 확인된, 아직 정리되지 않은 지점

배포 관련 이슈는 [../deployment/README.md](../deployment/README.md)의 트러블슈팅 섹션도 함께 참고하세요.

---

## 1. 환경/실행 트러블슈팅

| 증상 | 원인 / 해결 |
|---|---|
| `ModuleNotFoundError: sqlalchemy` 등 | 루트에서 `uv sync`만 실행해 workspace member인 `backend`의 의존성이 제거됨 → **`uv sync --all-packages`**로 재설치 |
| `ImportError: cannot import name 'NP_SUPPORTED_MODULES'` (torch/torchvision) | torch 2.11은 **numpy ≥ 2.4와 호환되지 않음**. 루트 `pyproject.toml`이 `numpy>=2.3,<2.4`로 고정 중이니 `uv sync --all-packages`로 재설치 |
| `/internal/v1/predict`가 503 `VISION_MODEL_NOT_READY` | 체크포인트 없음 → `weights/best.pt` 배치 또는 `MODEL_PATH` 환경변수로 지정 |
| `/analyze`가 502 `S3_UPLOAD_FAILED` | AWS 자격증명 미설정 → 개발 중이라면 `STORAGE_BACKEND=local`로 우회 |
| `/analyze`의 `warnings`에 `RAG_SERVICE_UNAVAILABLE` | RAG 서비스(:8001)가 기동되어 있지 않음 — 아래 §2 참고 |
| PowerShell에서 `curl` 문법 오류 | `curl`이 `Invoke-WebRequest` 별칭 → **`curl.exe`** 사용 |
| Git Bash에서 `-F "image=@/c/..."`가 `000` | MinGW curl이 POSIX 절대경로를 못 엶 → `cygpath -m` 변환 또는 상대 경로 사용 |
| Git Bash에서 한글 본문이 400 | 인자 인코딩 문제 → 본문을 파일로 저장 후 `--data-binary "@body.json"` |
| PowerShell 응답 한글이 깨짐 | PS 5.1 인코딩 문제 → `[Text.Encoding]::UTF8.GetString($r.RawContentStream.ToArray())` |
| 학습된 체크포인트 대신 COCO 사전학습 가중치가 로드됨 | `weights/yolo26n.pt`(COCO)를 `MODEL_PATH`로 잘못 지정한 경우 — 17개 폐기물 taxonomy가 아닌 COCO class 인덱스가 반환되어 `class_id`가 조용히 오염됨. 반드시 파인튜닝된 `best.pt`를 지정 |

자세한 셸별 주의사항은 [`docs/API_TEST_COMMANDS.md`](../API_TEST_COMMANDS.md)를 참고하세요.

---

## 2. RAG 서비스 관련

| 증상 | 원인 / 해결 |
|---|---|
| RAG 서비스가 기동되지 않음 | `scripts/run-dev.sh`/`.ps1`은 **Backend·Vision만** 자동 기동합니다. RAG 서비스는 별도로 `uv run uvicorn rag.main:app --host 127.0.0.1 --port 8001`로 수동 기동해야 합니다 |
| 첫 요청이 유독 느림(약 2초 이상) | `rule_lookup.py`의 규칙 조회는 임베딩+벡터DB 왕복이 필요해 건당 약 2초가 걸립니다. `scripts/warm_rule_cache.py`로 사전에 캐시를 예열하세요(전체 17개 클래스 × 지역 조합을 미리 조회) |
| `/chat`이 항상 결정적 템플릿 답변만 나옴 | RAG 서비스 프로세스 자체의 `GEMINI_API_KEY`/`GOOGLE_API_KEY`가 설정되지 않았거나, 사용자 지역이 미선택 상태 → `backend/agent/service.py`가 자동으로 폴백 답변 생성(오류 아님) |
| `not-in-list`가 재분류 결과와 무관하게 종종 실패 | RAG 그래프의 `judge`(재분류 결과 검증) 노드와 재시도 루프가 **현재 그래프 배선에서 비활성화**되어 있어(§3.1), Gemini의 1차 분류를 검증 없이 그대로 사용합니다 |

---

## 3. 알려진 코드 상태 (Known Issues)

문서화를 위한 코드 조사 과정에서 확인된, 정리가 필요한 지점들입니다. 버그 리포트가 아니라
"현재 이런 상태다"라는 사실 기록이며, 후속 작업 계획 수립에 참고하세요.

### 3.1 RAG 서비스 — `judge` 검증 노드 비활성

`rag/src/graph/main_graph.py`에 재분류 결과를 검증하는 `judge` 노드와 재시도 루프
(`route_after_judge`, 최대 2회)가 구현되어 있지만, 실제 컴파일된 그래프 배선에서는 주석 처리되어
호출되지 않습니다. 활성화 시 재분류 정확도가 개선될 것으로 예상되나, 응답 시간(현재 60초 타임아웃)에
영향을 줄 수 있어 트레이드오프 검토가 필요합니다.

### 3.2 RAG 서비스 — 죽은 코드

- `rag/src/graph/main_graph.py::handle_direct_classification()` — 호출하는 곳이 없음
- `backend/agent/prompts.py`(`CHAT_SYSTEM_PROMPT`, `build_chat_prompt`) — RAG 서비스 도입 이전 설계의
  잔재로, 현재 어디서도 호출되지 않음(프롬프트 구성 책임이 `rag/src/prompts/templates.py`로 이동)
- `backend/services/gemini_service.py` — (구) Gemini 직접 호출 경로. `not-in-list`가 RAG
  `/reclassify`로 대체되며 미사용 상태로 남음

### 3.3 Frontend — 라우트 가드 비활성

`RequireAuth`/`RootRedirect` 컴포넌트(`frontend/src/pages/AuthScreen/`)가 구현되어 있지만
`App.tsx`에서 실제 라우트에 연결되지 않아, 로그인 없이 URL로 각 화면에 직접 진입할 수 있습니다.
각 화면이 `if (!user) return null`로 크래시는 방지하지만 로그인 화면으로 리다이렉트하지는 않습니다.

### 3.4 Frontend — 미연동/목업 데이터

- `MyPageScreen`의 포인트(`MOCK_POINTS=1024`)와 표시 이름 편집은 **백엔드 API 없이 클라이언트에만
  존재**하는 목업입니다.
- `src/api/mockData.ts`, `AnalyzingView.tsx`, `ResultSuccessView.tsx`는 실제 흐름에서 참조되지 않는
  죽은 코드입니다.
- `src/constants/wasteCategories.ts`(17개 분류 하드코딩)는 `data/taxonomy/waste_classes.json`을
  수동으로 미러링한 것이라, 분류 체계 변경 시 **두 곳을 함께 수정**해야 동기화가 유지됩니다.
- `ResultFailView`의 세부 실패 힌트(`blurry`/`dark`/`multiple_objects`)는 UI에 정의만 되어 있고,
  백엔드가 아직 이 정도로 세분화된 실패 사유를 내려주지 않아 대부분 `unclear` 기본값으로만 표시됩니다.

### 3.5 AI 모델 — 배포 체크포인트 추적 불가

`weights/best.pt`(운영 배포 체크포인트)를 `ai/models/yolo/`에 커밋된 41개 실험 run의 `best.pt`와
SHA-256으로 전수 대조했으나 **일치하는 산출물을 찾지 못했습니다**. 즉 현재 운영 중인 모델이 정확히
어떤 학습 설정(어떤 증강 전략, 몇 epoch)에서 나왔는지는 커밋된 자료만으로 재현할 수 없습니다.
향후 모델을 교체/재학습할 때는 학습 커맨드와 설정을 산출물과 함께 반드시 기록해 두는 것을 권장합니다.
자세한 내용은 [../specifications/13-ai-model-yolo.md](../specifications/13-ai-model-yolo.md) §5를 참고하세요.

### 3.6 즐겨찾기 목록 구조

`waste_classes` 참조 FK는 `ON DELETE RESTRICT`가 기본값이라 분류 체계가 참조 중이면 삭제할 수
없습니다. 17개 소분류를 다시 축소/병합하는 마이그레이션을 할 경우, 시드 로직(`seed_waste_classes()`)이
"추가/갱신만 하고 삭제는 하지 않는" 멱등적 방식이라 사라진 `class_id`를 참조하는 기존 행을
**수동으로 정리**해야 합니다(2026-09-18 마이그레이션 당시에도 동일한 절차 필요했음 —
[`docs/DATABASE_SCHEMA.md`](../DATABASE_SCHEMA.md) §10 참고).

---

## 4. 참고

- 서비스 아키텍처: [../specifications/09-service-architecture.md](../specifications/09-service-architecture.md)
- 오류 코드 카탈로그: [../specifications/15-error-specification.md](../specifications/15-error-specification.md)
- 배포 절차/이슈: [../deployment/README.md](../deployment/README.md)
