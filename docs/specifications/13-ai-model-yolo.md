# AI 모델 명세서 — YOLO (Vision 객체 탐지)

**버전** v1.0 · **기준일** 2026-09-28 · **작성 기준** `ai/models/yolo/`, `vision/`, `data/taxonomy/waste_classes.json` 직접 조사

> Faster R-CNN 실험은 이 프로젝트에서 별도로 학습되지 않아 문서화 대상에서 제외했습니다(YOLO 단일
> 모델 아키텍처로 진행). 이 문서는 실제 실험 산출물(`ai/models/yolo/`)을 근거로 하며, 근거를 찾을 수
> 없는 부분은 추측 없이 "확인 불가"로 명시합니다.

---

## 1. 모델 개요

| 항목 | 값 |
|---|---|
| 태스크 | Object Detection (단일 클래스 탐지 후 "메인 객체" 선정) |
| 베이스 모델 | `yolo26n.pt` (Ultralytics, nano 크기, COCO 사전학습 가중치에서 파인튜닝 시작) |
| 프레임워크 | Ultralytics 8.4.143 + PyTorch 2.11.0 (CUDA 12.8) |
| 클래스 수 | 17개 (재활용 폐기물 대/소분류) |
| 입력 해상도 | 640×640 (`imgsz=640`) |
| 산출물 | `weights/best.pt` (운영 배포), `weights/last.pt` (참고용) |
| 서빙 | `vision/` FastAPI 서버가 `POST /internal/v1/predict`로 노출(Backend 전용 내부 API) |

> `weights/yolo26n.pt`(COCO 사전학습 원본)는 **운영에 절대 사용하면 안 됩니다** — 17개 폐기물
> taxonomy가 아닌 COCO class 인덱스를 반환해 모든 `class_id`가 조용히 오염됩니다.

---

## 2. 클래스 정의 (17개, `class_id` = YOLO class index)

| class_id | 대분류 | 소분류 | class_id | 대분류 | 소분류 |
|---|---|---|---|---|---|
| 0 | 고철류 | 고철 | 9 | 종이류 | 박스류 |
| 1 | 고철류 | 비철금속 | 10 | 종이류 | 신문지 |
| 2 | 나무 | 나무 | 11 | 종이류 | 종이 |
| 3 | 도기류 | 도기 | 12 | 캔류 | 캔 |
| 4 | 비닐 | 비닐 | 13 | 페트병 | 페트병 |
| 5 | 스티로폼 | 스티로폼 | 14 | 플라스틱류 | 플라스틱 |
| 6 | 유리병 | 유리병 | 15 | 플라스틱류 | 장난감 |
| 7 | 의류 | 의류 | 16 | 형광등 | 형광등 |
| 8 | 종이류 | 책 | | | |

이 표는 `data/taxonomy/waste_classes.json`이 단일 소스이며, 원래 86개였던 소분류를 대분류(12개)는
유지한 채 17개로 병합한 결과입니다(병합 이력: [`docs/DATABASE_SCHEMA.md`](../DATABASE_SCHEMA.md) §10).

---

## 3. 학습 데이터

- 원본: `data/train100val/` (Training/Validation 분리), 전처리 결과물은 `data/processed/`
  (`annotations/`, `coco/`, `images/`, `labels/`, `manifests/`)에 COCO 포맷 등으로 저장.
- 전처리 스크립트: `ai/preprocessing/01_common_detection_preprocess_flexible_damage.py`,
  `02_common_detection_preprocess_damage_ratio20.py` — 탐지 대상 객체의 손상/잘림 비율 기준 필터링 로직 포함.
- 클래스 재배치: 17개 소분류 병합 시 라벨(JSON)과 이미지 18,589개를 실제로 물리 재배치해 새 폴더
  구조에 맞춤(유실/불일치 0건 확인, [`DATABASE_SCHEMA.md`](../DATABASE_SCHEMA.md) §10 참고).

---

## 4. 학습 실험 — 베이스라인

`ai/models/yolo/00_yolo_baseline_no_aug/` (증강 없이 학습한 대조군)

| 항목 | 값 |
|---|---|
| 하이퍼파라미터 | `epochs=15`, `imgsz=640`, `batch=8`, `patience=12`, `seed=42`, `optimizer=auto→AdamW` |
| 증강 | 전부 비활성화(0.0) — 순수 베이스라인 |
| 학습 시간 | 약 126.8분(15 epoch) |
| **정밀도(Precision)** | 0.7970 |
| **재현율(Recall)** | 0.7895 |
| **F1** | 0.7932 |
| **mAP50** | 0.8368 |
| **mAP75** | 0.8296 |
| **mAP50-95** | 0.8098 |
| 추론 속도 | 약 7.26 ms/image |

**클래스별 mAP50-95 편차** (`baseline_per_class_map.csv`): 상위 — 종이류/책 0.969, 형광등 0.961,
스티로폼 0.948. 하위 — **고철류/비철금속 0.251**(다른 클래스 대비 뚜렷한 이상치), 종이류/종이 0.571,
페트병 0.698, 종이류/신문지 0.655, 플라스틱류/플라스틱 0.728. 비철금속 클래스는 데이터 특성상
(형태 다양성이 커서) 추가 데이터 보강 또는 세분류 재검토가 필요한 후보로 판단됩니다.

---

## 5. 학습 실험 — 증강 전략 비교 (`01_experiment_augmentation/`)

베이스라인 대조군(B) + OpenCV 기반 오프라인 증강(C) + YOLO 자체 증강(Y) + 혼합(H) 총 **41개 실험 run**을
동일 조건(모델/이미지 크기/배치는 고정)에서 비교했습니다.

| 그룹 | 개수 | 방식 | 예시 |
|---|---|---|---|
| **B** (대조군) | 4 | 무증강 / YOLO 기본 증강, 시드만 다르게(42/123/777) 반복 | `B00_no_aug_control_seed42`, `B01_yolo_default_baseline_seed*` |
| **C** (OpenCV 오프라인 증강) | 14 | 증강을 데이터셋 생성 단계에서 미리 적용(학습 시 추가 증강 0) | 밝기/대비, 감마, CLAHE, 가우시안 블러/노이즈, 모션 블러, JPEG 압축, 어파인, 원근, 좌우반전, 혼합 조합 |
| **Y** (YOLO 자체 증강) | 15 | 학습 중 실시간 증강(`hsv_*`, `translate`, `scale`, `shear`, `perspective`, `mosaic`, `mixup`, `cutmix` 등) | `Y08_yolo_mosaic_seed42`, `Y09_yolo_mixup_seed42` |
| **H** (혼합) | 4 | OpenCV 오프라인 증강 + YOLO 실시간 증강 조합 | `H03_cv_mixed_plus_yolo_light_seed42` |

**공통 학습 설정**(`args.yaml` 공통값): `model=yolo26n.pt`, `epochs=50`, `batch=8`, `imgsz=640`,
`patience=12`, `optimizer=auto`, `lr0=0.01`, `lrf=0.01`, `momentum=0.937`, `weight_decay=0.0005`,
`warmup_epochs=3.0`, `auto_augment=randaugment`, `erasing=0.4` (시드만 42/123/777로 반복).

**결과 저장 위치**: 각 run 폴더의 `results.csv`(epoch별 지표), `args.yaml`(적용 하이퍼파라미터),
`confusion_matrix*.png`, `Box{P,R,F1,PR}_curve.png`. `report/summary/opencv_generation_*.csv`는
학습 지표 비교표가 **아니라** 각 OpenCV 증강 단계의 이미지별 생성 로그(원본→증강본 매핑, 객체 수
변화 확인용)입니다 — run 간 성능 비교는 각 run의 `results.csv`를 직접 대조해야 합니다.

> **확인 불가 사항**: 41개 run 각각의 `best.pt`와 `report/final_best/`, 그리고 실제 배포된
> `weights/best.pt`를 SHA-256으로 전수 대조했으나, **어느 run의 산출물과도 바이트 단위로 일치하지
> 않았습니다**. 즉 "최종적으로 어떤 증강 전략이 운영 모델로 채택되었는지"는 커밋된 산출물만으로는
> 재현/특정할 수 없습니다. `01_experiment_augmentation/runs/` 자체 지표만 놓고 epoch별 최고
> mAP50-95를 비교하면 `B01_yolo_default_baseline_seed777`(≈0.236)이 가장 높지만, 이는
> `00_yolo_baseline_no_aug`(0.81)와 조건(추정: 50 epoch + patience 조기종료, 또는 다른 데이터
> 구성)이 달라 두 실험 그룹의 수치를 직접 비교하기는 어렵습니다. 운영 반영 시에는 실제 배포
> 체크포인트를 만든 학습 커맨드/설정을 별도로 기록해두는 것을 권장합니다.

---

## 6. 추론 파이프라인 (`vision/inference.py`)

1. **체크포인트 로딩**: `MODEL_PATH` 환경변수 → 없으면 고정 경로 `weights/best.pt` (Vision 서버
   자체는 `ai/models/yolo/**`를 자동 스캔하지 않으며, 이 자동 탐색은 `scripts/run-dev.*` 개발
   스크립트의 책임입니다).
2. **1차 추론**: 매우 낮은 하한(`low_confidence_floor=0.05`)으로 `model.predict()` 1회 호출 —
   이 하한조차 못 넘으면 "메인 객체 없음"(`VISION_NO_MAIN_OBJECT`).
3. **메인 객체 선정**: 살아남은 박스 중 `confidence × area × (1 − 중심으로부터의 정규화 거리)`가
   최대인 박스를 선택 — 화면 중앙에 크고 확실하게 있는 물체를 우선시하는 휴리스틱.
4. **Top-K 추출**: 그 박스 위치의 NMS/argmax 이전 원시 클래스 점수 텐서에서 상위 `TOP_K`
   (기본 5, `VISION_TOP_K`)개를 그대로 추출 — confidence threshold와 무관하게 **항상 정확히
   TOP_K개**의 후보를 보장.
5. **출력 정규화**: bbox를 0~1 정규화 XYXY로 변환, `model_version` 문자열(체크포인트 식별자)을 함께 반환.

| 설정값 | 기본값 | 설명 |
|---|---|---|
| `low_confidence_floor` | 0.05 | 이 밑이면 탐지 자체가 없다고 판단 |
| `nms_iou` | 0.45 | NMS IoU 임계값 |
| `max_detections` | 100 | 이미지당 최대 탐지 수 |
| `top_k` (`VISION_TOP_K`) | 5 | 반환 후보 개수 |
| `VISION_CONFIDENCE_THRESHOLD`(Backend) | 0.5 | 이 미만이면 Backend가 재촬영 안내로 분기 |

---

## 7. 서비스 통합 계약

- Backend `/api/v1/analyze`가 재인코딩한 이미지 바이트를 그대로 Vision에 전달 — **저장된 이미지 =
  분석에 실제로 쓰인 이미지**(원본이 아닌 재인코딩본).
- `class_id`는 `waste_classes` 테이블·Frontend 상수(`wasteCategories.ts`)와 반드시 동기화되어야
  하는 계약값입니다(§[11-data-specification.md](11-data-specification.md) §1.3).
- 모델 교체 시 체크리스트: (1) 새 체크포인트를 `weights/best.pt`로 교체 또는 `MODEL_PATH` 지정,
  (2) 클래스 수/순서가 `data/taxonomy/waste_classes.json`과 정확히 일치하는지 확인,
  (3) `vision/tests/test_api_real_model.py`로 실제 추론 계약 검증.

---

## 8. 참고

- Vision 서버 아키텍처: [09-service-architecture.md](09-service-architecture.md) §3
- API 계약: [10-api-specification.md](10-api-specification.md) §17 (Vision 내부 API)
- 데이터 명세: [11-data-specification.md](11-data-specification.md)
