# 기능 명세서

**버전** v1.0 · **기준일** 2026-09-28 · **작성 기준** `frontend/src` 실제 화면 구현

요구사항 명세서([04](04-requirements-specification.md))가 "시스템이 무엇을 해야 하는가"를 다룬다면,
이 문서는 **각 화면이 실제로 어떻게 동작하는가**(상태, 검증, 예외 처리)를 다룹니다.

---

## 1. `AuthScreen` (`/login`) — 로그인/회원가입

| 항목 | 내용 |
|---|---|
| 진입 조건 | 앱 최초 진입, 또는 로그아웃 후 |
| 구성 | 로그인/회원가입 탭 전환형 단일 화면. 상단에 "분리쏙" 브랜딩 + "스마트 분리배출 가이드" 태그라인 |
| 입력 검증 | 이메일 형식, 비밀번호 최소 길이 — 실패 시 인라인 빨간 텍스트(`formError`)로 표시(전역 토스트 없음) |
| 성공 동작 | 로그인 성공 시 `AuthContext`가 `localStorage`(`bs_token`,`bs_user`)에 세션 저장 → `resolveHomeRoute(user)`가 `region` 유무로 `/region` 또는 `/home` 이동 |
| 실패 동작 | `AUTH_INVALID_CREDENTIALS`, `AUTH_EMAIL_EXISTS`, `REQUEST_VALIDATION_ERROR` 등을 폼 하단에 노출 |
| 로딩 상태 | 제출 버튼 스피너(`useAxios`의 `loading`) |

## 2. `RegionScreen` (`/region`) — 지역 선택

| 항목 | 내용 |
|---|---|
| 진입 조건 | 로그인 직후 `region == null`, 또는 마이페이지에서 지역 변경 |
| 구성 | 시/도 선택 → 시/군/구 선택 2단계 |
| 데이터 소스 | `GET /api/v1/regions`(토큰 불필요 — 지역 선택 전에도 호출 가능) |
| 저장 동작 | 선택 후 저장 버튼 → `PATCH /users/me/region` → 성공 시 "저장 중..." 표시 후 `/home`으로 이동 |
| 방어 로직 | `user`가 없으면(비로그인) `return null`로 렌더링 방지(가드 컴포넌트 자체는 비활성 상태 — §5 참고) |

## 3. `PhotoCaptureScreen` (`/home`, `/capture`) — 촬영/분석

동일 컴포넌트가 두 경로에 매핑되며, 내부적으로 `captureState`(`capture`\|`analyzing`\|`agent_thinking`\|`fail`)로
화면을 전환합니다.

### 3.1 `capture` 상태 — `CaptureView` + `LiveViewfinder`

| 항목 | 내용 |
|---|---|
| 카메라 | `getUserMedia`로 라이브 뷰파인더 실행. OpenCV.js(GrabCut, Web Worker) 기반으로 화면 중앙 가이드 프레임 안 물체를 실시간 인식해 "너무 멀어요/가까워요/인식됐어요" 상태 텍스트 표시 |
| 폴백 | `getUserMedia` 실패 시 `<input capture="environment">`로 OS 카메라 앱 대체 |
| 업로드 | 갤러리에서 이미지 선택도 지원 |
| 안내 | 지역 미설정 시 경고 배너 표시, 촬영 팁 카드 노출 |

### 3.2 `analyzing` 상태 — `AnalyzingView2`

| 항목 | 내용 |
|---|---|
| 표시 | 5단계 진행바 시뮬레이션 + 10초마다 회전하는 분리배출 팁 포스터(`TipPoster`) |
| 최소 대기시간 | `MIN_ANALYZING_MS = 3000` — 실제 API 응답이 더 빨라도 화면이 깜빡이지 않도록 최소 3초 유지 |
| 분기 | `POST /analyze` 응답의 `status`에 따라 `SUCCESS`→`/result`로 즉시 이동, `RETAKE_REQUIRED`→`fail` 상태로 전환 |

### 3.3 `fail` 상태 — `ResultFailView`

| 항목 | 내용 |
|---|---|
| 표시 | 실패 유형별 힌트 카드(`FailureHint`: `blurry`\|`dark`\|`multiple_objects`\|`unclear`\|`unknown`) + 촬영한 썸네일 |
| 현재 한계 | 백엔드가 세부 실패 사유를 내려주지 않아, 대부분 `unclear`(불분명) 기본값으로 표시됨 — `blurry`/`dark`/`multiple_objects`는 코드상 정의만 되어 있고 실제로 도달하는 경로가 없음(개선 여지) |
| 동작 | "다시 촬영" 버튼 → `capture` 상태로 복귀 |

### 3.4 `agent_thinking` 상태 — `AgentThinkingView`

| 항목 | 내용 |
|---|---|
| 트리거 | `POST /feedback/{id}/not-in-list` 요청 중(RAG 재분류 대기) |
| 표시 | 가짜(연출용) 다단계 추론 리스트 + 경과 시간 카운터 — 실제 RAG 처리는 최대 60초까지 걸릴 수 있어 "심층 분석 중"이라는 기대치를 설정 |

> **알려진 죽은 코드**: `AnalyzingView.tsx`(구버전, `AnalyzingView2`로 대체됨)와
> `ResultSuccessView.tsx`(참조하는 곳 없음)는 폴더에 남아있지만 실제 흐름에서 렌더링되지 않습니다.

## 4. `ResultScreen` (`/result`) — 분류 결과

| 항목 | 내용 |
|---|---|
| 진입 조건 | 분석 성공 직후(`location.state.result` 필요), 또는 마이페이지 즐겨찾기 클릭 |
| 빈 상태 | `location.state.result`가 없으면(새로고침 등) 즉시 `/capture`로 리다이렉트 |
| 즐겨찾기 진입 | 실제 촬영 이미지 없이 진입한 경우, 썸네일 대신 카테고리 이모지로 대체 표시 |
| 구성 | 결과 카드(품목명/수거요일), 배출 방법 안내 카드(`national_rule`+`region_rule`, 또는 구버전 `steps`/`notes` 폴백), 출처 링크, "다시 촬영"/"맞아요" CTA, 플로팅 채팅 버튼 |
| 후보 재선택 | 하단 시트로 `candidate_scores` 목록 표시 + "여기 없어요" 옵션 |
| 피드백 연동 | "맞아요"→confirm, 후보 선택→select-candidate, "여기 없어요"→not-in-list(→`agent_thinking` 화면으로 전환 후 재진입) |
| 오류 표시 | 피드백 제출 실패 시 하단 시트 내 인라인 에러(`feedbackError`), 전역 토스트 없음 |

### 4.1 `ChatDrawer` — AI Agent 채팅

| 항목 | 내용 |
|---|---|
| 트리거 | 결과 화면의 플로팅 채팅 버튼 |
| 구성 | 슬라이드업 드로어, 추천 질문 칩, 타이핑 인디케이터 |
| 연동 | `POST /api/v1/chat`(`{feedback_id, message}`) |
| 오류 처리 | 실패 시 인라인 봇 메시지("답변을 가져오지 못했어요" 류) 또는 콘솔 로그로만 처리(전용 오류 UI 없음) |

## 5. `MyPageScreen` (`/mypage`) — 마이페이지

| 항목 | 내용 |
|---|---|
| 구성 | 프로필 헤더(표시 이름 — **클라이언트 로컬 편집만, 백엔드 미저장**), 포인트 표시(**하드코딩 `MOCK_POINTS=1024`, 실제 API 없음**), 지역 변경 링크, 즐겨찾기 목록 |
| 즐겨찾기 목록 | `GET /favorites` — 로딩 중 스켈레톤 3행 표시 |
| 즐겨찾기 추가 | `FavoriteModal`(대분류→소분류 2단계 피커) → `POST /favorites` |
| 즐겨찾기 삭제 | `DELETE /favorites/{id}` |
| 즐겨찾기 클릭 | `/result` 화면으로 이동(실제 분석 없이 해당 분류의 결과 화면을 합성해서 보여줌 — 배출정보 재조회를 위해 `GET /disposal/schedule` 호출) |
| 로그아웃 | `POST /auth/logout` → 세션 클리어 → `/login` |

> **참고**: 포인트/표시 이름은 실제 서비스 요구사항이라기보다 UI 목업 단계의 잔재로 보이며,
> 백엔드에 대응 API가 없습니다. 정식 기능으로 만들려면 별도 요구사항 정의가 필요합니다.

---

## 6. 공통 UX 패턴

| 패턴 | 구현 방식 |
|---|---|
| 로딩 | 짧은 액션은 버튼 내 스피너(`useAxios.loading`), 긴 흐름(분석/재분류)은 전용 풀스크린 로딩 화면 |
| 오류 표시 | 전역 토스트/스낵바 없음 — 폼/섹션별 인라인 에러 텍스트로 로컬 처리 |
| 인증 헤더 | `authHeaders()`/`apiHeaders()`(매 요청 수동 부착, axios 인터셉터 없음) + 매 요청 신규 `X-Request-ID` |
| 세션 저장 | `localStorage`(`bs_token`,`bs_user`) — httpOnly 쿠키 아님 |
| 라우트 가드 | `RequireAuth`/`RootRedirect` 컴포넌트는 구현되어 있으나 `App.tsx`에서 비활성화 — 각 화면이 `if (!user) return null`로 개별 방어 |

---

## 7. 참고

- 화면 간 이동 흐름: [06-user-flow.md](06-user-flow.md)
- API 계약: [10-api-specification.md](10-api-specification.md)
- 프론트엔드 관련 알려진 이슈: [../troubleshooting/README.md](../troubleshooting/README.md)
