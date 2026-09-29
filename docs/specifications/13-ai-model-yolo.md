# AI 모델 명세서 — YOLO (Vision 객체 탐지)

**버전** v2.0 · **기준일** 2026-09-29 · **작성 기준** `ai/models/yolo/`, `ai/preprocessing/`, `vision/`,
`data/taxonomy/waste_classes.json` 직접 조사 + `model/yolo` 브랜치(커밋 `015e04b`, 2026-09-11) 실험
노트북·리포트 대조

> Faster R-CNN 실험은 이 프로젝트에서 별도로 학습되지 않아 문서화 대상에서 제외했습니다(YOLO 단일
> 모델 아키텍처로 진행). 이 문서는 실제 실험 산출물을 근거로 하며, 근거를 찾을 수 없는 부분은 추측
> 없이 "확인 불가"로 명시합니다. 숫자에는 **실측**(커밋된 산출물에 실제로 기록된 값)과 **계획**(코드는
> 있지만 실행 출력이 없는 값)을 구분해 표기합니다.

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
아래 §5의 소규모 파일럿 실험은 이 병합 **이전**의 86개 소분류 기준으로 진행되었다는 점에 유의하세요 —
두 실험 세트의 class_id는 서로 다른 체계입니다.

---

## 3. 데이터 파이프라인

### 3.1 원본 데이터

- 프로덕션 데이터셋: `data/train100val/`(Training 32,580장 / Validation 4,598장, AI Hub 생활폐기물
  데이터셋 기준 clean/damaged 원본). Training은 `clean`(원형)과 `damaged`(일부·상당·완전파손 3단계)로
  나뉘어 있습니다.
- 파일럿 데이터셋: `data/sample/train9val2.zip`(§5.1 참고, 86개 소분류 기준 932장 — 파일럿 전용의
  훨씬 작은 샘플로, 프로덕션 데이터셋과는 별개입니다).

### 3.2 프로덕션 전처리 스크립트

`ai/preprocessing/`에 있는 두 스크립트는 **입출력 구조와 품질 검사 로직은 동일하고, "파손 이미지를
얼마나 섞을지"의 샘플링 정책만 다릅니다**:

| 스크립트 | 정책 | 비고 |
|---|---|---|
| `01_common_detection_preprocess_flexible_damage.py` | `clean` 우선 + `damaged`로 부족분 보충(목표: clean 80% + damaged 20%, 한쪽이 부족하면 다른 쪽 여유분으로 채움) | 클래스별 최종 수량이 clean 가용량에 따라 들쭉날쭉해질 수 있음 |
| `02_common_detection_preprocess_damage_ratio20.py` | `base_total = min(목표 수량, clean 가용량)`을 먼저 정하고, 그중 정확히 20%를 damaged로 **치환**(총량은 clean만 썼을 때와 동일, 구성 비율만 80:20 고정) | 현재 `data/processed/`를 생성한 실제 스크립트(§3.3 확인) |

두 스크립트 모두 SHA-1 기반 이미지 매니페스트(`manifests/image_manifest.csv`), 클래스 매핑
(`annotations/class_mapping.json`), bbox clip 검사, YOLO/COCO 이중 포맷 export(`EXPORT_FORMATS =
['YOLO', 'COCO']`, Faster R-CNN 공통 사용을 염두에 둔 설계)를 공유합니다. damaged 이미지는 일부·
상당·완전파손 세 단계에서 최대한 균등 샘플링합니다.

### 3.3 실제 산출물 검증

`data/processed/manifests/sampling_summary.csv`를 직접 확인한 결과, `damage_ratio_target=0.2`,
`actual_damage_ratio≈0.2`, `target_met=True`가 전 클래스에서 일관되게 나타나 — **02번(고정 20%
비율) 스크립트가 현재 `data/processed/`(및 §5의 프로덕션 베이스라인 학습 데이터)를 생성한 실제
스크립트임을 확인**했습니다. 예: 고철류/고철은 clean 651장 중 521장 + damaged 130장 = 651장
(20.0%), 고철류/비철금속은 clean 79장 + damaged 20장 = 99장(20.2%)으로 구성됩니다.

---

## 4. R&D 타임라인 개요

이 프로젝트의 YOLO 실험은 **서로 다른 두 데이터 규모/클래스 체계**에서 두 단계로 진행되었습니다.
아래 §5·§6은 각각 이 두 단계를 다룹니다.

```text
[Phase 1] 소규모 증강·하이퍼파라미터 전략 스크리닝
  86개 소분류(병합 전) · train 9장/val 2장 (총 932장) · model/yolo 브랜치
  → "어떤 증강·학습 설정이 우리 데이터에 유효한가?"를 싼 비용으로 먼저 검증

        ↓ (여기서 확인한 방법론과 교훈을 프로덕션 규모에 적용)

[Phase 2] 프로덕션 규모 베이스라인
  17개 소분류(병합 후) · train 7,623장/val 2,201장 · 현재 브랜치(00_yolo_baseline_no_aug)
  → 실제 서비스 배포 후보 체크포인트 학습
```

Phase 1은 `model/yolo` 브랜치(커밋 `015e04b`)에만 존재하며 현재 작업 브랜치에는 병합되어 있지
않습니다. Phase 2는 현재 브랜치의 `ai/models/yolo/00_yolo_baseline_no_aug/`에 실측 결과가 커밋되어
있습니다.

---

## 5. Phase 1 — 소규모 증강 전략 스크리닝 (`model/yolo` 브랜치)

> **출처**: `model/yolo` 브랜치(커밋 `015e04b`)의 `ai/notebooks/01_recycling_eda_preprocess_*.ipynb`,
> `02_yolo_baseline_augmentation_search_*.ipynb`, `03_yolo_optuna_hyperparameter_tuning_*.ipynb`와
> `ai/models/yolo/01_experiment_augmentation/report/`. 이 파일들은 현재 브랜치에는 없으므로, 재현하려면
> 해당 브랜치를 체크아웃하거나 `git show model/yolo:<경로>`로 조회해야 합니다.

### 5.1 실험 설계

- **데이터**: 원본 932장(raw_images) 중 전처리 후 train 761장/val 165장, 86개 소분류(병합 전) 기준
  클래스당 train 약 9장/val 약 2장 — 클래스 수 대비 매우 작은 파일럿 규모입니다.
- **원칙**: (1) Validation에는 어떤 증강도 적용하지 않는다 — 실험마다 "시험지"가 달라지면 비교가
  불공정해짐. (2) 모든 실험은 새 pretrained 모델에서 시작한다 — 이전 실험 weight를 이어받으면 공정한
  비교가 아님. (3) 최적 조합 선정은 Validation 기준이며, 최종 확정에는 별도 Test set 평가가 필요함
  (이 파일럿에는 Test set이 없었음 — §5.4 참고).
- **고유 실험 설정 35개**(`B`=Baseline/Control, `Y`=YOLO 내장 증강, `C`=OpenCV 오프라인 증강,
  `H`=Hybrid)를 먼저 seed42로 1차 실행하고, 그중 상위 3개(`B01`, `Y14`, `H04`)를 seed
  123/777로 추가 재검증해 **총 41개 학습 run**을 실행했습니다(`report/per_class/` CSV 41개로 확인):

  | 그룹 | 고유 설정 | 재검증 포함 총 run | 방식 |
  |---|---|---|---|
  | B (대조군) | 2 (`B00`, `B01`) | 4 | `B00` 전체 증강 OFF, `B01` Ultralytics 기본값 그대로 — `B01`은 3개 시드 모두 재실행 |
  | Y (YOLO 내장) | 15 | 17 | HSV/flip/rotation/translate/scale/shear/perspective/mosaic/mixup/cutmix 단일 및 조합 — 그중 `Y14`(mosaic+mixup+cutmix)만 3개 시드 재실행 |
  | C (OpenCV 오프라인) | 14 | 14 | brightness/gamma/CLAHE/blur/noise/JPEG압축/affine/perspective/flip 단일 및 조합, 원본과 같은 장수의 static train set 생성(80% 확률 적용 + 20% 원본 유지, JPEG quality 95 저장) — 상위 3위 안에 든 것이 없어 재검증 없음 |
  | H (Hybrid) | 4 | 6 | OpenCV 오프라인 증강 + YOLO 온라인 증강 조합 — 그중 `H04`(JPEG압축+HSV/기하)만 3개 시드 재실행 |

  Copy-Paste는 이번 실험에서 의도적으로 제외했습니다 — 전처리 단계에서 polygon 라벨 일부를 bbox로
  변환해 순수 segmentation 데이터가 아니게 되었고, bbox만으로 잘라 붙이면 배경까지 함께 복사되어
  부자연스러운 이미지가 되기 때문입니다.
- **공통 학습 설정**: `model=yolo26n.pt`, `epochs=50`, `batch=8`, `imgsz=640`, `patience=12`,
  `optimizer=auto`, `lr0=0.01`, `lrf=0.01`, `momentum=0.937`, `weight_decay=0.0005`,
  `warmup_epochs=3.0`(시드 42/123/777로 반복).

### 5.2 결과 — 단일 seed의 착시와 multi-seed 재검증

seed 42 한 번만 보면 커스텀 증강 조합이 기본값보다 나아 보였지만, 상위 3개를 3개 시드(42/123/777)로
재검증하자 순위가 뒤집혔습니다:

| 설정 | seed42 단독 mAP50-95 | 3-seed 평균 mAP50-95 | 표준편차 | 평균 Precision | 평균 Recall |
|---|---:|---:|---:|---:|---:|
| B01 `yolo_default_baseline` | 0.2119 | **0.2254** | **0.0118** | **0.2961** | 0.2241 |
| Y14 `mosaic_mixup_cutmix` | 0.2143 | 0.2106 | 0.0103 | 0.2585 | 0.2093 |
| H04 `cv_jpeg_plus_yolo_hsv_geo` | **0.2159**(1위) | 0.2009 | 0.0177(가장 큼) | 0.2804 | **0.2376** |

즉 H04는 seed42 단독으로는 1위였지만 seed 변동폭이 가장 크고 multi-seed 평균은 오히려 가장
낮았습니다. **33개 커스텀 증강·조합 설정(YOLO 내장 15 + OpenCV 14 + Hybrid 4) 중 어느 것도
Ultralytics 기본 증강(B01)을 multi-seed 기준으로 확실히 능가하지 못했습니다** — 이것이 이
파일럿의 핵심 결론입니다.

고유 설정 35개의 seed42 결과를 mAP50-95로 정렬하면 상위권(H04 0.216 → B01 0.212)과 하위권(C14
`opencv_mixed_combo` 0.120)의 차이는 있지만, 대부분의 커스텀 증강이 baseline보다 낮았습니다
(35개 중 baseline `B01` 대비 개선된 것은 상위 2~3개뿐). 전체 순위는
`model/yolo:ai/models/yolo/01_experiment_augmentation/report/summary/seed42_ranking.csv`에 있습니다.

**클래스별 비교의 함정**: baseline과 best(B01 seed777) 사이의 클래스별 mAP50-95 델타를 직접 계산해보면
(`baseline_vs_best_per_class.csv`, val 객체 0인 클래스 제외 83개 기준) 개선 39개·하락 42개로 평균은
+0.022에 불과한데, 개별 클래스는 -0.94 ~ +0.70까지 극단적으로 흔들립니다. 이는 실제 클래스별 성능
변화라기보다 **클래스당 Validation 이미지가 1~3장뿐이라 생기는 통계적 잡음**입니다. 파일럿 노트북
자체도 "Validation 객체가 0인 클래스는 평가 불가"라고 명시하고 있으며, 이 결과는 그 경고를
뒷받침합니다 — 이 규모의 파일럿에서는 클래스별 수치를 근거로 한 결론을 내리지 않는 것이 안전합니다.

### 5.3 모델 선정 기준(이 프로젝트가 채택한 5단계 우선순위)

파일럿 노트북(02, 03)이 공통으로 명시한 최종 모델 선택 기준입니다. mAP50-95 하나만 보지 않고
다음 순서로 판단합니다:

1. **Multi-seed mAP50-95 평균** — 한 seed의 최고점보다 여러 seed 평균을 우선.
2. **Recall** — 사용자가 찍은 객체를 놓치지 않는 것이 서비스 특성상 중요하므로, mAP가 비슷한
   후보라면 Recall이 높은 쪽을 선호.
3. **표준편차(안정성)** — 평균이 조금 높아도 seed마다 크게 흔들리는 설정은 배제.
4. **클래스별 AP·Confusion Matrix** — 특정 카테고리만 크게 무너지는지 확인.
5. **실제 예측 이미지 육안 확인** — 수치가 좋아도 bbox가 이상하면 채택하지 않음.

### 5.4 실험에서 얻은 교훈(파일럿 노트북 원문 요지)

- 증강은 "많이 넣을수록 좋다"가 아니다 — 강한 Mosaic/MixUp/Perspective는 실제 서비스 이미지와
  분포가 멀어질 수 있다.
- mAP50-95만 보지 말고 Recall도 함께 봐야 한다.
- Validation 객체가 0인 클래스는 애초에 평가할 수 없다.
- 모든 원본이 주간 촬영이라는 편향이 있다 — 증강으로 저조도 대응력을 일부 보강할 수는 있어도
  실제 야간 데이터를 대체하지는 못한다.
- 이 파일럿의 "최적"은 Validation 기준으로 고른 것이며, Validation 자체가 모델 선택에 쓰였으므로
  독립적인 최종 성능을 주장하려면 별도 Test set 평가가 필요하다 — **이 파일럿에도, 현재 §6
  프로덕션 베이스라인에도 아직 독립 Test set 평가는 없습니다.**

### 5.5 다음 단계로 설계된 것 — Optuna 하이퍼파라미터 탐색 (계획, 미실행)

`03_yolo_optuna_hyperparameter_tuning_KAGGLE_damage_toggle.ipynb`는 위 결론(B01을 기준점으로 삼음)을
이어받아 학습 하이퍼파라미터(optimizer, lr0, lrf, momentum, weight_decay, warmup_epochs, cos_lr)를
Optuna(TPE sampler + MedianPruner, trial 25개, trial당 최대 40 epoch)로 탐색하는 **방법론과 코드**를
담고 있습니다. 권장 전체 흐름은 다음과 같습니다:

```text
① Baseline(B01) 확정
    ↓
② augmentation은 B01로 고정한 채 핵심 학습 하이퍼파라미터 Optuna 탐색
    ↓
③ Optuna Best를 3개 seed로 재확인
    ↓
④ 그 학습 하이퍼파라미터를 고정한 채 B01/H04/Y14 재비교
    ↓
⑤ 필요하면 최종 승자 augmentation 강도만 좁게 추가 탐색
    ↓
⑥ 최종 모델 multi-seed 검증 → ⑦ 독립 Test set 1회 평가
```

노트북에는 `USE_DAMAGED_DATA` 토글(`clean_only` vs `with_damaged_20pct`)도 설계되어 있어, damaged
데이터 포함 여부에 따라 별도로 하이퍼파라미터를 탐색할 수 있게 되어 있습니다.

> **중요 — 실행 여부**: 이 노트북의 모든 코드 셀 출력(output)이 비어 있어, **Optuna 탐색이 실제로
> 실행된 기록은 이 브랜치에 존재하지 않습니다.** 즉 5.5절은 "실측 결과"가 아니라 "설계된 계획"입니다.
> §3.2의 프로덕션 전처리 스크립트에 있는 `USE_DAMAGED_DATA` 개념적 토글(clean 80%+damaged 20%)은
> 이 계획과 방향이 맞닿아 있지만, 실제로 이 Optuna 절차를 거쳐 프로덕션 하이퍼파라미터가 결정되었다는
> 근거는 찾지 못했습니다(§6의 프로덕션 베이스라인은 `optimizer=auto`로 학습되어 Optuna 탐색값을
> 사용하지 않았습니다).

---

## 6. Phase 2 — 프로덕션 규모 베이스라인 (`00_yolo_baseline_no_aug/`)

`ai/models/yolo/00_yolo_baseline_no_aug/`(증강 없이 학습한 대조군, 17개 클래스 병합 후, 현재 브랜치에
실측 결과 커밋됨)

| 항목 | 값 |
|---|---|
| 데이터 | train 7,623장 / val 2,201장(§3.3 전처리 산출물), 17개 병합 클래스 |
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

> **Phase 1과 직접 비교하면 안 되는 이유**: mAP50-95가 0.21 내외(Phase 1)에서 0.81(Phase 2)로
> 크게 뛴 것은 증강 전략의 효과가 아니라 **데이터 규모(클래스당 9~2장 → 수백 장)와 클래스 체계
> (86개 세분류 → 17개 병합)가 완전히 다르기 때문**입니다. §4의 R&D 타임라인이 보여주듯 Phase 1은
> "어떤 증강이 유효한가"를 싸게 검증하는 스크리닝이었고, Phase 2가 실제 배포 후보를 만드는
> 프로덕션 학습입니다.

### 6.1 여전히 확인되지 않는 지점

`weights/best.pt`(운영 배포 체크포인트)를 `ai/models/yolo/`에 커밋된 모든 실험 run의 `best.pt`와
SHA-256으로 전수 대조했으나 **일치하는 산출물을 찾지 못했습니다**. `00_yolo_baseline_no_aug`는
"증강 없이" 학습한 대조군이므로, 이 자체가 운영 모델일 가능성은 낮습니다 — 즉 **증강을 적용한
프로덕션 규모(17클래스, train100val) 학습이 실제로 이루어졌을 가능성이 높지만, 그 결과물이나 학습
커맨드/설정이 이 저장소에 커밋되어 있지 않습니다.** 향후 모델을 교체/재학습할 때는 (1) 학습에 사용한
정확한 커맨드·하이퍼파라미터·증강 설정, (2) 그 결과 체크포인트의 SHA-256을 `best.pt`와 함께 반드시
기록해 두는 것을 권장합니다.

---

## 7. 추론 파이프라인 (`vision/inference.py`)

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

## 8. 서비스 통합 계약

- Backend `/api/v1/analyze`가 재인코딩한 이미지 바이트를 그대로 Vision에 전달 — **저장된 이미지 =
  분석에 실제로 쓰인 이미지**(원본이 아닌 재인코딩본).
- `class_id`는 `waste_classes` 테이블·Frontend 상수(`wasteCategories.ts`)와 반드시 동기화되어야
  하는 계약값입니다(§[11-data-specification.md](11-data-specification.md) §1.3).
- 모델 교체 시 체크리스트: (1) 새 체크포인트를 `weights/best.pt`로 교체 또는 `MODEL_PATH` 지정,
  (2) 클래스 수/순서가 `data/taxonomy/waste_classes.json`과 정확히 일치하는지 확인,
  (3) `vision/tests/test_api_real_model.py`로 실제 추론 계약 검증, (4) §6.1의 교훈에 따라 학습
  커맨드·설정·체크포인트 해시를 함께 기록.

---

## 9. 참고

- Vision 서버 아키텍처: [09-service-architecture.md](09-service-architecture.md) §3
- API 계약: [10-api-specification.md](10-api-specification.md) §17 (Vision 내부 API)
- 데이터 명세: [11-data-specification.md](11-data-specification.md)
- Phase 1 원본 자료: `model/yolo` 브랜치(커밋 `015e04b2b99bc13a2832fb92e1115c8921729a12`,
  2026-09-11) — `git show model/yolo:<경로>`로 조회하거나 해당 브랜치를 별도로 체크아웃해 확인 가능.
