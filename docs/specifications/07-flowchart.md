# 순서도 (Flowchart)

**버전** v1.0 · **기준일** 2026-09-28

시퀀스 다이어그램([08-sequence-diagram.md](08-sequence-diagram.md))이 "누가 누구를 호출하는가"를
보여준다면, 이 문서는 핵심 API의 **내부 분기 로직**(조건 판단 → 결과 분기)을 순서도로 정리합니다.

---

## 1. `POST /api/v1/analyze` 처리 순서도

```mermaid
flowchart TD
    A([이미지 업로드 요청]) --> B{JWT 유효?}
    B -- 아니오 --> B1[401 AUTH_*]
    B -- 예 --> C{users.region_id\nNULL?}
    C -- 예 --> C1[409 USER_REGION_REQUIRED]
    C -- 아니오 --> D{업로드 검증\n타입/용량/0바이트}
    D -- 실패 --> D1[400/413/415]
    D -- 통과 --> E[디코드 → EXIF 보정\n→ 1920px 축소 → JPEG 재인코딩]
    E --> F[Vision 서버 predict 호출]
    F --> G{메인 객체\n탐지됨?}
    G -- 아니오 --> G1[200 RETAKE_REQUIRED\nAI_NO_MAIN_OBJECT\n저장 없음]
    G -- 예 --> H[S3 업로드]
    H --> I[DB 트랜잭션:\nimages → feedback → feedback_candidates]
    I --> J{트랜잭션\n성공?}
    J -- 실패 --> J1[ROLLBACK\n+ S3 보상 삭제\n503 DATABASE_ERROR]
    J -- 성공 --> K{Top-1 score\n>= 0.5?}
    K -- 아니오 --> K1[200 RETAKE_REQUIRED\nAI_LOW_CONFIDENCE\nfeedback_id 포함\n※ 저장은 이미 완료]
    K -- 예 --> L["배출요일 조회 (행정안전부, best-effort)"]
    L --> M["배출방법 규정 조회 (RAG /rule_node, best-effort)"]
    M --> N[200 SUCCESS\nclass_id/score/candidate_scores\ndisposal_day/national_rule/region_rule\nfeedback_id/warnings]

    style G1 fill:#fff3cd
    style K1 fill:#fff3cd
    style N fill:#d4edda
    style B1 fill:#f8d7da
    style C1 fill:#f8d7da
    style D1 fill:#f8d7da
    style J1 fill:#f8d7da
```

![1. `POST /api/v1/analyze` 처리 순서도](images/07-flowchart-01-analyze.png)

**핵심 판단 지점**

| 분기 | 조건 | 결과 |
|---|---|---|
| 지역 미선택 게이트 | `users.region_id IS NULL` | 409 — 분석 자체를 시작하지 않음 |
| 메인 객체 게이트 | Vision이 중앙 객체를 하나도 탐지 못함 | 200 RETAKE_REQUIRED, **아무것도 저장 안 함** |
| 신뢰도 게이트 | Top-1 `score < VISION_CONFIDENCE_THRESHOLD`(0.5) | 200 RETAKE_REQUIRED, **저장은 이미 완료**(재학습 데이터 수집) |
| 외부 API 게이트 | 행정안전부/RAG 조회 실패 | 분석은 성공 처리, `warnings[]`에만 코드 기록 |

---

## 2. 피드백 3종 공통 선행 검증

```mermaid
flowchart TD
    A([피드백 요청\nconfirm / select-candidate / not-in-list]) --> B{feedback_id\n존재?}
    B -- 아니오 --> B1[404 FEEDBACK_NOT_FOUND]
    B -- 예 --> C{소유자==요청자?}
    C -- 아니오 --> C1[403 FEEDBACK_FORBIDDEN]
    C -- 예 --> D{is_correct\nIS NULL?\n=미처리}
    D -- 아니오 --> D1[409 FEEDBACK_ALREADY_COMPLETED]
    D -- 예 --> E[개별 처리 로직으로 진행]
```

![2. 피드백 3종 공통 선행 검증](images/07-flowchart-02-feedback-precheck.png)

---

## 3. `POST /feedback/{id}/not-in-list` 상세 분기 (RAG 재분류)

```mermaid
flowchart TD
    A([여기 없어요 선택]) --> B[공통 선행 검증 통과]
    B --> C{region 선택됨?}
    C -- 아니오 --> C1[409 USER_REGION_REQUIRED]
    C -- 예 --> D[S3에서 원본 이미지 재다운로드]
    D --> E{다운로드 성공?}
    E -- 아니오 --> E1[502 S3_DOWNLOAD_FAILED]
    E -- 예 --> F[RAG /reclassify 호출\nclassify → disposal_lookup]
    F --> G{RAG 서비스\n응답 성공?}
    G -- 실패/타임아웃 --> G1[502 RAG_SERVICE_UNAVAILABLE\n또는 504 RAG_RECLASSIFY_TIMEOUT]
    G -- 성공 --> H{needs_retake\n== true?}
    H -- 예 --> H1[200 RETAKE_REQUIRED\nAI_RECLASSIFY_FAILED]
    H -- 아니오 --> I{반환된 major/minor\n조합이 waste_classes에\n존재?}
    I -- 아니오 --> I1[502 RAG_BAD_RESPONSE]
    I -- 예 --> J[feedback UPDATE\nfinal_class_id, is_correct=false,\ncorrection_source=GEMINI]
    J --> K[배출요일/배출방법 조회]
    K --> L[200 NotInListResponse]
```

![3. `POST /feedback/{id}/not-in-list` 상세 분기 (RAG 재분류)](images/07-flowchart-03-not-in-list.png)

---

## 4. `POST /api/v1/chat` 답변 생성 분기

```mermaid
flowchart TD
    A([후속 질문 수신]) --> B{feedback 소유권/\nregion 검증}
    B -- 실패 --> B1[403/404/409]
    B -- 통과 --> C{user.region\n존재?}
    C -- 아니오 --> D[RAG 호출 생략]
    C -- 예 --> E[RAG /chat_node 호출]
    E --> F{RAG 응답\n성공?}
    F -- 실패 --> D
    F -- 성공 --> G[200 answer = RAG 생성 답변\nwarnings 없음]
    D --> H[결정적 템플릿 답변 생성\n_fallback_answer]
    H --> I[200 answer = 템플릿 답변\nwarnings: RAG_SERVICE_UNAVAILABLE 등]
```

![4. `POST /api/v1/chat` 답변 생성 분기](images/07-flowchart-04-chat.png)

---

## 5. 참고

- 각 분기의 정확한 필드/코드: [15-error-specification.md](15-error-specification.md)
- 호출 순서(누가 누구를 부르는가): [08-sequence-diagram.md](08-sequence-diagram.md)
