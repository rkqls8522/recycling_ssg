# 시퀀스 다이어그램

**버전** v1.0 · **기준일** 2026-09-28

이 문서는 분리쏙의 핵심 흐름을 시퀀스 다이어그램으로 정리합니다. 전체 아키텍처는
[09-service-architecture.md](09-service-architecture.md), 각 단계의 필드는
[10-api-specification.md](10-api-specification.md)를 참고하세요.

---

## 1. 회원가입 ~ 지역 선택 ~ 로그인

```mermaid
sequenceDiagram
    actor U as 사용자
    participant FE as Frontend
    participant BE as Backend

    U->>FE: 이메일/비밀번호 입력 (회원가입)
    FE->>BE: POST /api/v1/auth/signup
    BE-->>FE: 201 { user_id, region: null }
    FE->>BE: POST /api/v1/auth/login
    BE-->>FE: 200 { access_token, user.region: null }
    Note over FE: region == null → 지역 선택 화면으로 분기
    FE->>BE: GET /api/v1/regions (토큰 불필요)
    BE-->>FE: 200 { items: [...56개] }
    U->>FE: 시/도 → 시/군/구 선택
    FE->>BE: PATCH /api/v1/users/me/region { region_id }
    BE-->>FE: 200 { region: {...} }
    Note over FE: 이후 /analyze, /disposal, /chat 호출 가능
```

![1. 회원가입 ~ 지역 선택 ~ 로그인](images/08-sequence-01-auth-region.png)

---

## 2. 이미지 분석 (`POST /api/v1/analyze`)

```mermaid
sequenceDiagram
    actor U as 사용자
    participant FE as Frontend
    participant BE as Backend
    participant VS as Vision(:8100)
    participant S3 as AWS S3
    participant DB as MySQL
    participant RAG as RAG 서비스(:8001)
    participant GOV as 행정안전부 API

    U->>FE: 촬영/업로드
    FE->>BE: POST /api/v1/analyze (multipart image)
    BE->>BE: JWT 검증 + region_id NULL 체크(409 USER_REGION_REQUIRED)
    BE->>BE: 이미지 검증 → 디코드/EXIF보정/1920px축소/JPEG 재인코딩
    BE->>VS: POST /internal/v1/predict (재인코딩된 동일 바이트)
    alt 메인 객체 없음
        VS-->>BE: 422 VISION_NO_MAIN_OBJECT
        BE-->>FE: 200 { status: RETAKE_REQUIRED, code: AI_NO_MAIN_OBJECT, feedback_id: null }
        Note over BE,DB: 저장 없음 (예측값 자체가 없음)
    else 예측 성공
        VS-->>BE: 200 { class_id, score, candidate_scores[], bbox, model_version }
        BE->>S3: 이미지 업로드
        S3-->>BE: s3_key
        BE->>DB: BEGIN → images INSERT → feedback INSERT → feedback_candidates INSERT(Top-K)
        alt DB 실패
            DB-->>BE: 오류
            BE->>S3: 보상 삭제(delete_object)
            BE-->>FE: 503 DATABASE_ERROR
        else DB 성공
            DB-->>BE: COMMIT (feedback_id 확정)
            alt Top-1 score < 0.5
                BE-->>FE: 200 { status: RETAKE_REQUIRED, code: AI_LOW_CONFIDENCE, feedback_id }
                Note over BE,DB: 재학습 데이터 수집 목적으로 이미 저장 완료(미응답 상태)
            else Top-1 score >= 0.5
                par best-effort 배출요일 조회
                    BE->>GOV: 배출요일 조회(sgg_name)
                    GOV-->>BE: disposal_day 또는 실패
                and best-effort 배출방법 규정 조회
                    BE->>RAG: POST /rule_node { major/minor_category, ... }
                    RAG-->>BE: { national_rule, region_rule } 또는 실패
                end
                BE-->>FE: 200 { status: SUCCESS, class_id, score, candidate_scores, disposal_day, national_rule, region_rule, feedback_id, warnings[] }
            end
        end
    end
```

![2. 이미지 분석 (`POST /api/v1/analyze`)](images/08-sequence-02-analyze.png)

> 행정안전부 API와 RAG `/rule_node` 조회는 **서로 독립적인 best-effort 호출**입니다. 어느 한쪽이
> 실패해도 다른 쪽 결과와 분석 성공 자체에는 영향을 주지 않고, 실패 코드만 `warnings[]`에 추가됩니다.

---

## 3. 피드백 — "다른 후보 선택" / "여기 없어요" (Gemini 재분류)

```mermaid
sequenceDiagram
    actor U as 사용자
    participant FE as Frontend
    participant BE as Backend
    participant DB as MySQL
    participant S3 as AWS S3
    participant RAG as RAG 서비스(:8001)
    participant GEMINI as Google Gemini

    alt 다른 Top-K 후보 선택
        U->>FE: 후보 목록에서 선택
        FE->>BE: POST /feedback/{id}/select-candidate { class_id }
        BE->>DB: class_id가 Top-K 후보에 있는지 검증
        BE->>DB: UPDATE feedback SET final_class_id, is_correct=false, correction_source='USER'
        BE-->>FE: 200 { final_class_id, correction_source: USER }
    else "여기 없어요" (Gemini 재분류)
        U->>FE: "여기 없어요" 탭
        FE->>BE: POST /feedback/{id}/not-in-list
        BE->>S3: 원본 이미지 재다운로드
        S3-->>BE: image bytes
        BE->>RAG: POST /reclassify { img_url(base64), user_region }
        RAG->>RAG: LangGraph: classify(Gemini Vision) → disposal_lookup
        RAG->>GEMINI: 멀티모달 재분류 프롬프트
        GEMINI-->>RAG: { major_category, minor_category }
        RAG->>RAG: rule_lookup으로 national_rule/region_rule 조회
        alt 재분류 실패/판정 불가
            RAG-->>BE: { needs_retake: true }
            BE-->>FE: 200 { status: RETAKE_REQUIRED, code: AI_RECLASSIFY_FAILED }
        else 재분류 성공
            RAG-->>BE: { major_category, minor_category, disposal_result }
            BE->>DB: waste_classes에서 class_id 역조회
            BE->>DB: UPDATE feedback SET final_class_id, is_correct=false, correction_source='GEMINI'
            BE-->>FE: 200 { final_class_id, major_category, minor_category, national_rule, region_rule }
        end
    end
```

![3. 피드백 — "다른 후보 선택" / "여기 없어요" (Gemini 재분류)](images/08-sequence-03-feedback.png)

> **알려진 미완성 지점**: RAG 그래프의 `judge`(재분류 결과 검증) 노드와 재시도 루프는 코드에는
> 있지만 현재 그래프 배선에서 비활성화되어 있어(§[09-service-architecture.md](09-service-architecture.md) §4.2),
> 위 다이어그램의 `classify → disposal_lookup`은 **검증 없이 1회 분류 결과를 그대로 사용**하는
> 현재 동작을 반영한 것입니다.

---

## 4. AI Agent 후속 질문 (`POST /api/v1/chat`)

```mermaid
sequenceDiagram
    actor U as 사용자
    participant FE as Frontend
    participant BE as Backend (agent/service.py)
    participant RAG as RAG 서비스(:8001)
    participant GEMINI as Google Gemini

    U->>FE: 채팅창에 후속 질문 입력
    FE->>BE: POST /api/v1/chat { feedback_id, message }
    BE->>BE: feedback 존재/소유권/region 확인
    BE->>BE: agent.service.answer_question() 호출
    alt 사용자 지역 있음
        BE->>RAG: POST /chat_node { message, major/minor_category, user_region }
        RAG->>RAG: rule_lookup(national/region rule 조회, 캐시됨)
        RAG->>GEMINI: 규정 텍스트 + 질문 → 답변 생성 프롬프트
        GEMINI-->>RAG: 자연어 답변
        RAG-->>BE: { answer }
    end
    alt RAG 응답 있음
        BE-->>FE: 200 { feedback_id, answer, warnings: [] }
    else RAG 실패/미설정/지역 없음
        BE->>BE: _fallback_answer() — 결정적 템플릿 답변 생성
        BE-->>FE: 200 { feedback_id, answer(템플릿), warnings: ["RAG_SERVICE_UNAVAILABLE"] }
    end
    Note over BE: Stateless — message/answer 어디에도 저장하지 않음
```

![4. AI Agent 후속 질문 (`POST /api/v1/chat`)](images/08-sequence-04-chat.png)

---

## 5. 즐겨찾기

```mermaid
sequenceDiagram
    actor U as 사용자
    participant FE as Frontend
    participant BE as Backend
    participant DB as MySQL

    U->>FE: 결과 화면에서 "즐겨찾기 추가"
    FE->>BE: POST /api/v1/favorites { class_id }
    BE->>DB: (user_id, class_id) UNIQUE 확인
    alt 이미 존재
        BE-->>FE: 409 FAVORITE_ALREADY_EXISTS
    else 신규
        BE->>DB: INSERT favorites
        BE-->>FE: 201 { favorite_id, major_category, minor_category }
    end
    U->>FE: 마이페이지 → 즐겨찾기 목록 진입
    FE->>BE: GET /api/v1/favorites
    BE-->>FE: 200 { items[] } (최신 등록순)
    U->>FE: 항목 삭제
    FE->>BE: DELETE /api/v1/favorites/{favorite_id}
    BE->>DB: 소유권 확인 후 DELETE
    BE-->>FE: 204
```

![5. 즐겨찾기](images/08-sequence-05-favorites.png)

---

## 6. 참고

- 처리 단계의 분기 로직(성공/재촬영/오류)은 [07-flowchart.md](07-flowchart.md)에서 순서도로 다룹니다.
- 서비스별 내부 모듈 구조는 [09-service-architecture.md](09-service-architecture.md)를 참고하세요.
