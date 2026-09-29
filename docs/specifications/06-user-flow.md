# 사용자 흐름도 (User Flow)

**버전** v1.0 · **기준일** 2026-09-28 · **기준** `frontend/src` 실제 라우팅/화면 구조

---

## 1. 화면(라우트) 목록

| 경로 | 화면 컴포넌트 | 설명 |
|---|---|---|
| `/login` | `AuthScreen` | 로그인/회원가입 (탭 전환) |
| `/region` | `RegionScreen` | 시/도 → 시/군/구 선택 |
| `/home`, `/capture` | `PhotoCaptureScreen` | 카메라 촬영/이미지 업로드 + 분석 요청 (동일 컴포넌트) |
| `/result` | `ResultScreen` | 분류 결과, 피드백, AI 채팅 드로어 |
| `/mypage` | `MyPageScreen` | 프로필, 지역 변경, 즐겨찾기 |

> **현재 코드 상태 참고**: 라우트 가드 컴포넌트(`RequireAuth`, `RootRedirect`)가 구현되어 있지만
> `App.tsx`에서 실제로는 비활성화(주석 처리)되어 있어, 로그인 없이도 URL로 각 화면에 직접
> 진입할 수 있습니다. 각 화면이 `if (!user) return null`로 자체 방어만 하는 상태로, 이 흐름도는
> **의도된 정상 흐름** 기준으로 작성했습니다. 자세한 내용은
> [../troubleshooting/README.md](../troubleshooting/README.md)에 기록합니다.

---

## 2. 전체 흐름도

```mermaid
flowchart TD
    Start([앱 진입]) --> Login[/login\n로그인/회원가입/]
    Login -- 회원가입 성공 --> Login
    Login -- 로그인 성공 --> RegionCheck{region\n선택됨?}
    RegionCheck -- 아니오(신규 가입자) --> Region[/region\n지역 선택/]
    RegionCheck -- 예 --> Home[/home\n촬영 화면/]
    Region -- 저장 --> Home

    Home --> Capture{촬영/업로드}
    Capture --> Analyzing[분석 중\n5단계 진행바 + 팁 카드]
    Analyzing --> AnalyzeResult{분석 결과}
    AnalyzeResult -- SUCCESS --> Result[/result\n분류 결과 화면/]
    AnalyzeResult -- RETAKE_REQUIRED --> Fail[재촬영 안내 화면\n힌트 카드]
    Fail -- 다시 촬영 --> Home

    Result -- "맞아요" --> Confirm[피드백: confirm]
    Confirm --> Home
    Result -- "다른 후보 선택" --> CandidatePicker[하단 시트:\nTop-K 후보 목록]
    CandidatePicker -- 후보 선택 --> SelectCandidate[피드백: select-candidate]
    CandidatePicker -- "여기 없어요" --> AgentThinking[AI 심층 분석 화면\n가상 추론 단계 표시]
    AgentThinking --> NotInList[피드백: not-in-list\nRAG 재분류]
    NotInList -- 성공 --> Result
    NotInList -- 실패 --> Fail
    SelectCandidate --> Result

    Result -- 채팅 아이콘 --> ChatDrawer[하단 드로어:\nAI Agent 채팅]
    ChatDrawer --> Result

    Home -- 마이페이지 아이콘 --> MyPage[/mypage/]
    Result -- 즐겨찾기 클릭\n(마이페이지에서) --> Result
    MyPage -- 지역 변경 --> Region
    MyPage -- 즐겨찾기 추가/삭제 --> MyPage
    MyPage -- 로그아웃 --> Login
```

![2. 전체 흐름도](images/06-user-flow-01-overview.png)

---

## 3. 필수 선행 조건 흐름 — 지역 선택

```mermaid
flowchart LR
    A[회원가입] -->|"region: null"| B[로그인]
    B -->|"user.region == null?"| C{지역 선택 여부}
    C -- null --> D[GET /regions\n56개 목록\n토큰 불필요] --> E[PATCH /users/me/region]
    C -- 있음 --> F[홈 화면 진입]
    E --> F
    F -.->|"지역 없이 analyze/disposal/chat 호출 시"| G[409 USER_REGION_REQUIRED\n→ 지역 선택 화면으로 강제 이동]
```

![3. 필수 선행 조건 흐름 — 지역 선택](images/06-user-flow-02-region-precondition.png)

회원가입은 지역을 받지 않으므로(`region: null` 고정), **지역 선택은 로그인 직후 반드시 거쳐야 하는
관문**입니다. 이를 생략하면 분석/배출정보/채팅 API가 전부 409로 막힙니다.

---

## 4. 촬영 화면(`PhotoCaptureScreen`) 내부 상태 전이

```mermaid
stateDiagram-v2
    [*] --> capture
    capture --> analyzing: 촬영/업로드 완료
    analyzing --> [*]: SUCCESS → /result로 이동
    analyzing --> fail: RETAKE_REQUIRED
    fail --> capture: 다시 촬영
    capture --> capture: 실시간 뷰파인더\n(OpenCV.js GrabCut으로\n중앙 물체 인식 가이드)
```

![4. 촬영 화면(`PhotoCaptureScreen`) 내부 상태 전이](images/06-user-flow-03-capture-states.png)

- `capture`: 라이브 카메라 뷰파인더가 화면 중앙 가이드 프레임 안의 물체를 실시간으로 인식해
  "너무 멀어요 / 가까워요 / 인식됐어요" 안내를 표시합니다(`getUserMedia` 실패 시 OS 카메라 앱으로 대체).
- `analyzing`: 실제 응답 시간과 무관하게 최소 3초(`MIN_ANALYZING_MS`) 동안 진행바를 보여줘 화면이
  깜빡이지 않게 합니다.
- `fail`: 실패 유형별 힌트(흐림/어두움/다중 객체/불분명)를 안내하지만, 현재는 백엔드가 세부 사유를
  내려주지 않아 대부분 "불분명" 기본값으로 표시됩니다.

---

## 5. 참고

- 처리 로직의 세부 분기: [07-flowchart.md](07-flowchart.md)
- 화면별 상세 동작: [05-functional-specification.md](05-functional-specification.md)
- 페르소나 기반 시나리오: [03-user-scenarios.md](03-user-scenarios.md)
