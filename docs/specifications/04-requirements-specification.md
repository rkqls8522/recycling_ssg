# 요구사항 명세서

**버전** v1.0 · **기준일** 2026-09-28

[02-requirements-definition.md](02-requirements-definition.md)에서 정의한 요구사항(FR/NFR)을
입력/처리/출력/예외 단위로 상세화합니다. 필드 수준의 계약은 [10-api-specification.md](10-api-specification.md),
오류 코드는 [15-error-specification.md](15-error-specification.md)를 참고하세요.

---

## 1. FR-101~105: 인증/회원

| 항목 | 내용 |
|---|---|
| 관련 API | `POST /auth/signup`, `POST /auth/login`, `POST /auth/logout`, `GET /users/me` |
| 입력 | 회원가입: `email`(형식 검증), `password`(8~72바이트 UTF-8) — 로그인: `email`, `password` |
| 처리 | 회원가입 시 이메일 중복 검사 → bcrypt 해시 → `users` INSERT(`region_id=NULL`). 로그인 시 이메일로 조회 → bcrypt 검증 → JWT 발급(`HS256`, 24시간) |
| 출력 | 회원가입: `user_id`,`email`,`region:null`,`created_at` — 로그인: `access_token`,`user` |
| 예외 | 이메일 중복(409), 형식 오류(422), 자격증명 불일치(401 — 계정 없음/비밀번호 오류 구분하지 않음) |
| 비고 | 로그아웃은 Stateless — 서버 상태 변경 없이 204만 반환. 프로필 조회는 `password_hash`를 응답에서 완전히 제외 |

## 2. FR-201~203: 지역

| 항목 | 내용 |
|---|---|
| 관련 API | `GET /regions`(인증 불필요), `PATCH /users/me/region` |
| 입력 | 목록 조회: `sido_name`(선택) — 변경: `region_id`(1~56) |
| 처리 | 목록: `regions` 테이블 전체/필터 조회. 변경: `region_id` 존재 검증 후 `users.region_id` UPDATE |
| 출력 | 목록: `items: Region[]`(최대 56) — 변경: `user_id`, `region` |
| 예외 | 미지원 시·도(422, 전용 문구), 존재하지 않는 `region_id`(404 `REGION_NOT_FOUND`) |
| 게이트 규칙 | `users.region_id IS NULL`인 상태로 `/analyze`, `/disposal/schedule`, `/chat` 호출 시 **409 `USER_REGION_REQUIRED`** — 세 API 공통 |

## 3. FR-301~308: 이미지 분석

| 항목 | 내용 |
|---|---|
| 관련 API | `POST /analyze` (내부적으로 `POST /internal/v1/predict` 위임) |
| 입력 | `image`(multipart File, `jpeg`/`jpg`/`png`/`webp`, ≤10MB) |
| 처리 순서 | ① JWT 검증 ② `region_id` NULL 체크 ③ 업로드 검증(타입/크기/0바이트) ④ 디코드+EXIF보정+1920px축소+JPEG재인코딩 ⑤ Vision 예측 ⑥ 메인 객체 게이트 ⑦ S3 업로드 ⑧ DB 트랜잭션(`images`→`feedback`→`feedback_candidates`) ⑨ 신뢰도 게이트(<0.5) ⑩ 배출요일/배출방법 best-effort 조회 |
| 출력 | 성공: `major_category`,`minor_category`,`class_id`,`score`,`candidate_scores[]`,`user_region`,`disposal_day`,`national_rule`,`region_rule`,`image_id`,`feedback_id`,`warnings[]` |
| 예외(재촬영, 200) | `AI_NO_MAIN_OBJECT`(저장 없음), `AI_LOW_CONFIDENCE`(저장은 완료, 미응답 상태 유지) |
| 예외(오류) | 업로드 검증 실패(400/413/415), Vision 연동 실패(502/503/504), DB 실패(503, S3 보상 삭제 수행) |
| 데이터 규칙 | 저장되는 이미지는 **재인코딩된 바이트**(원본 아님) — Vision 분석과 S3 저장에 동일한 바이트 사용. `feedback_candidates`는 분석 시점 스냅샷으로 이후 불변 |

상세 분기는 [07-flowchart.md](07-flowchart.md) §1, 시퀀스는 [08-sequence-diagram.md](08-sequence-diagram.md) §2 참고.

## 4. FR-401~406: 피드백

| 항목 | 내용 |
|---|---|
| 관련 API | `POST /feedback/{id}/confirm`, `/select-candidate`, `/not-in-list` |
| 공통 선행 검증 | `feedback_id` 존재(404) → 소유자 일치(403) → 미처리 상태(409, `is_correct IS NULL`) |
| confirm 처리 | Body 없음 → `final_class_id=predicted_class_id`, `is_correct=true`, `correction_source=NULL` |
| select-candidate 처리 | `class_id`가 Top-K 후보 중 하나이며 Top-1과 달라야 함(400 위반 시) → `final_class_id=선택값`, `is_correct=false`, `correction_source='USER'` |
| not-in-list 처리 | S3 원본 재다운로드 → RAG `/reclassify` 호출(Gemini Vision 재분류 그래프) → `waste_classes` 역조회 → `final_class_id`, `is_correct=false`, `correction_source='GEMINI'` |
| 출력 | 각 API 응답 필드는 [10-api-specification.md](10-api-specification.md) §7 참고 |
| 예외 | `FEEDBACK_SAME_AS_PREDICTION`(400), `FEEDBACK_INVALID_CANDIDATE`(400), `S3_DOWNLOAD_FAILED`(502), `RAG_SERVICE_UNAVAILABLE`(502), `RAG_RECLASSIFY_TIMEOUT`(504), 재분류 실패 시 200 `AI_RECLASSIFY_FAILED` |
| 데이터 규칙 | `chk_feedback_result_state` CHECK 제약으로 "미응답/확인/정정" 3가지 조합만 DB 레벨에서 허용([11-data-specification.md](11-data-specification.md) §1.5) |

## 5. FR-501~504: AI Agent 채팅

| 항목 | 내용 |
|---|---|
| 관련 API | `POST /chat` |
| 입력 | `feedback_id`(본인 소유), `message`(1~1000자) |
| 처리 | feedback 존재/소유권/지역 검증 → `agent/service.py::answer_question` → (지역 있으면) RAG `/chat_node` 호출 → 실패 시 결정적 템플릿 답변으로 폴백 |
| 출력 | `feedback_id`, `answer`, `warnings[]` |
| 예외 | `FEEDBACK_FORBIDDEN`/`FEEDBACK_NOT_FOUND`(문구가 피드백 API와 다름), `USER_REGION_REQUIRED`, `AGENT_UNAVAILABLE`(502), `AGENT_TIMEOUT`(504) |
| 데이터 규칙 | **완전히 Stateless** — 질문/답변 어디에도 저장하지 않음. `session_id`/`message_id` 없음 |

## 6. FR-601~604: 즐겨찾기

| 항목 | 내용 |
|---|---|
| 관련 API | `GET/POST /favorites`, `DELETE /favorites/{id}` |
| 입력 | 등록: `class_id`(존재해야 함) — 삭제: `favorite_id` |
| 처리 | 등록 시 `(user_id, class_id)` UNIQUE 검증 후 INSERT. 조회는 본인 것만 `created_at DESC` |
| 출력 | 목록: `items[]` — 등록: `favorite_id`,`class_id`,`major_category`,`minor_category` |
| 예외 | `CLASS_NOT_FOUND`(404), `FAVORITE_ALREADY_EXISTS`(409), `FAVORITE_NOT_FOUND`(404 — 타인 소유 포함, 403 아님) |

---

## 7. 비기능 요구사항 구현 매핑

| NFR | 구현 위치 |
|---|---|
| NFR-101~103 (성능) | `vision/inference.py`(단일 forward pass), `rag/src/agents/rule_lookup.py`(`lru_cache`), 각 서비스 클라이언트의 `timeout_seconds` 설정 |
| NFR-201~203 (장애 격리) | `services/disposal_service.py`(`*_or_warn` 계열 함수), `api/analyze.py`(트랜잭션 실패 시 S3 보상 삭제) |
| NFR-301~305 (보안) | `core/security.py`(JWT/bcrypt), `core/deps.py::get_current_user`, 각 API의 소유권 검증(`_load_owned_feedback` 등), Vision/RAG `127.0.0.1` 바인딩 |
| NFR-401~403 (데이터 무결성) | `data/taxonomy/waste_classes.json` 단일 소스, `feedback` 테이블 CHECK 제약, `feedback_candidates` 분리 테이블 |
| NFR-501~503 (사용성) | Frontend `status` 기반 분기(`AnalyzeApiResponse`), 공통 오류 응답의 `message` 필드, `AnalyzingView2`의 진행바 |

---

## 8. 참고

- 요구사항 목록: [02-requirements-definition.md](02-requirements-definition.md)
- 화면 단위 상세 동작: [05-functional-specification.md](05-functional-specification.md)
- API 필드 계약: [10-api-specification.md](10-api-specification.md)
