# `ai/` — 재활용품 객체탐지 모델 개발

YOLO26n 기반 17클래스 재활용품 탐지 모델을 만드는 과정 전체가 이 폴더에 있습니다.
전처리 스크립트, 실험 노트북, 그리고 모든 실험 산출물이 들어 있습니다.

최종 산출물은 저장소 루트의 `weights/best.pt` 이고, `vision` 서비스가 이 파일을 읽습니다.

```
ai/
├── preprocessing/   원본 데이터 → 학습 가능한 데이터셋으로 변환 (공통 전처리)
├── notebooks/       실험 노트북 00 ~ 07, 정리 노트북 99
└── models/yolo/     각 노트북이 남긴 학습 결과·리포트
```

---

## 목차

1. [빠른 참조 — 최종 모델](#1-빠른-참조--최종-모델)
2. [`preprocessing/` — 공통 전처리](#2-preprocessing--공통-전처리)
3. [`notebooks/` — 실험 노트북](#3-notebooks--실험-노트북)
4. [`models/yolo/` — 실험 산출물](#4-modelsyolo--실험-산출물)
5. [실험 흐름과 개선 과정](#5-실험-흐름과-개선-과정)
6. [겪은 문제와 해결](#6-겪은-문제와-해결)
7. [숫자를 읽을 때의 규칙](#7-숫자를-읽을-때의-규칙)
8. [신문지 증강 A/B 실험](#신문지-증강-ab-실험)

---

## 1. 빠른 참조 — 최종 모델

| 항목 | 값 |
|---|---|
| 가중치 | `weights/best.pt` (= `ai/models/yolo/07_final_training/runs/final_Y08_auto_seed42_e20_newsAug/weights/best.pt`) |
| 베이스 모델 | `yolo26n.pt` |
| 클래스 | 17개 |
| 학습 데이터 | 144,315장 (객체 158,590개) |
| 검증 데이터 | 10,548장 (객체 11,621개) |
| epoch / imgsz / batch | 20 / 640 / 8 |
| 증강 | `mosaic=0.7`, `close_mosaic=4`, 나머지 전부 0 |
| 하이퍼파라미터 | `optimizer="auto"` (Optuna 튜닝값 미사용) |
| 신문지(class 10) | **다른 클래스와 동일하게 증강** (`EXCLUDE_NEWSPAPER_FROM_AUG = False`) |
| mAP50-95 | **0.8676** |
| mAP50 | 0.9226 |
| Precision / Recall / F1 | 0.8987 / 0.8971 / 0.8979 |
| 추론 속도 | **1.33 ms/장** (RTX 4070 Laptop) |
| 학습 시간 | 약 20시간 |

> `test` 분할은 없습니다. 위 수치는 전부 **val 기준**입니다.
>
> **신문지 증강 여부는 A/B 로 확정했습니다.** 아래 [신문지 증강 A/B 실험](#신문지-증강-ab-실험) 참고.
>
> 과거에 기록이 엇갈렸던 원인도 확인됐습니다. `final_decision.json` 이 `"적용": false` 였던 것은
> 2차 학습 전 `--dry-run` 이 그 파일을 다시 쓴 탓이고, 1차 학습(09-28 08:22)은 실제로
> **제외한 상태**가 맞습니다.

---

## 2. `preprocessing/` — 공통 전처리

```
preprocessing/
├── __init__.py
└── 01_common_detection_preprocess_flexible_damage.py
```

### `01_common_detection_preprocess_flexible_damage.py`

원본 AI-Hub 데이터를 `data/processed/` 로 변환하는 **단일 진입점**입니다.
YOLO 와 Faster R-CNN 이 같은 데이터를 쓰도록 **YOLO·COCO 두 포맷을 동시에** 내보냅니다.

**입력**

```
data/생활폐기물image_10000_2000_500/
├── Training/{clean,damaged}/
└── Validation/
data/taxonomy/waste_classes.json      ← 17클래스 기준 정의
```

**출력 (`data/processed/`)**

| 경로 | 내용 |
|---|---|
| `images/{train,val}/` | 이미지 (resize·재인코딩 없이 원본 그대로 복사) |
| `labels/{train,val}/` | YOLO 포맷 라벨 (`class cx cy w h`, 정규화) |
| `coco/instances_{train,val}.json` | COCO 포맷 (Faster R-CNN 용) |
| `annotations/class_mapping.json` | canonical_id ↔ 클래스명 매핑 |
| `annotations/common_annotations.json` | 포맷 중립 중간 표현 |
| `manifests/image_manifest.csv` | **이미지 한 장당 한 행** — 출처·SHA1·클래스·손상도·제외사유 |
| `manifests/sampling_summary.csv` | 클래스별 목표/선택 수량 |
| `manifests/sampling_shortage.csv` | 목표를 못 채운 클래스 |
| `data.yaml` | Ultralytics 학습 설정 |

**핵심 로직**

- **canonical_id 기반 클래스 매핑** — 원본의 소분류 이름이 흔들려도 `waste_classes.json`
  의 17개 정의로 정규화합니다.
- **clean / damaged 혼합 샘플링** — 클래스당 `clean 80 : damaged 20` 을 목표로 하되,
  한쪽이 모자라면 다른 쪽으로 채웁니다. damaged 는 `일부훼손 / 상당훼손 / 완전훼손`
  에서 최대한 균등하게 뽑습니다.
- **bbox 클리핑 정책** — 이미지 밖으로 나간 비율이 `MAX_BBOX_CLIP_RATIO` 미만일 때만
  잘라서 사용하고, 그보다 크면 해당 객체를 버립니다.
- **한 이미지 = 한 클래스** — 서로 다른 클래스가 한 장에 있으면 이미지 전체를 제외합니다.
- **SHA-1 중복 검사** — 같은 파일이 두 번 들어가는 것(within-split duplicate)과,
  train 과 val 에 같은 이미지가 걸치는 것(**cross-split leakage**)을 모두 걸러냅니다.
- **결정적 샘플링** — 시드 고정이라 같은 입력에 같은 데이터셋이 나옵니다.

**주요 스위치**

```python
USE_DAMAGED_DATA        # False = clean 만, True = clean+damaged 혼합
TRAIN_IMAGES_PER_CLASS  # None = 상한 없음
MAX_BBOX_CLIP_RATIO     # bbox 클리핑 허용 한계
EXPORT_FORMATS          # ["YOLO", "COCO"]
```

이 스위치 조합이 실험마다 데이터셋을 바꾼 원인입니다 — [7장](#7-숫자를-읽을-때의-규칙) 참고.

---

## 3. `notebooks/` — 실험 노트북

### 실험 노트북

| 파일 | 데이터 | 클래스 | 무엇을 물었나 | 결과 |
|---|---|---|---|---|
| `00_yolo26n_baseline_no_aug_LOCAL_KAGGLE.ipynb` | 7,623장 | 86 | 아무것도 안 하면 몇 점인가 | mAP50-95 **0.3765** |
| `01_yolo_optuna_RESUME_TOTAL25_KAGGLE_LOCAL.ipynb` | 7,623장 | 86 | 하이퍼파라미터를 맞추면 얼마나 오르나 | **0.5209** (+38%) |
| `02_yolo_baseline_augmentation_search_paths_updated.ipynb` | 7,624장 | 17 | 어떤 증강이 제일 좋은가 (36종) | 최고 +0.013 |
| `04_yolo_damaged_data_compare.ipynb` | 15,516장 | 17 | 파손 이미지를 넣으면 어떻게 되나 | B01 0.8670 |
| `05_yolo_retune_17class_optuna_augmentation.ipynb` | 7,623장 | 17 | 17클래스에서 다시 튜닝하면 | Y14 0.8584 |
| `06_yolo_damaged_data_two_variants.ipynb` | 미기록 | 17 | 파손 비율 2종 비교 | Y08_hp1 0.842 |
| `07_final_training.py` | 144,315장 | 17 | 확정 설정으로 최종 학습 | **0.8639** |
| `99_results_summary.ipynb` | — | — | 00~07 전체를 한자리에 정리 | 그래프 11종 |

> **03번은 없습니다.** 02번의 2×2 대조에 빠져 있던 `B03`(증강OFF + tuned) 칸을 채우는
> 노트북이었고, 결과를 02번에 병합한 뒤 `models/yolo/_archive_merged_03_no_aug_tuned/`
> 로 옮겼습니다. 원본 노트북은 `notebooks/_archive/` 에 있습니다.

### 07번 관련 파일이 두 개인 이유

| 파일 | 용도 |
|---|---|
| `07_final_training.py` | **최종 학습 스크립트.** 터미널에서 돌리므로 VSCode 가 죽어도 20시간 학습이 안 끊깁니다 (노트북판은 같은 내용이라 정리했습니다) |
| `07_finalize.py` | 학습을 중간에 멈췄을 때 **평가·리포트·가중치 배포만** 따로 수행 |

`07_finalize.py` 가 필요한 이유: Ultralytics 는 `best.pt` 를 val mAP 기록 경신 때마다
저장하므로 중단해도 그때까지 최선의 가중치가 남습니다. 학습 뒤에 이어지는
평가·배포 단계만 별도로 돌릴 수 있게 분리했습니다.

```bash
uv run --no-sync python ai/notebooks/07_finalize.py --deploy
```

### `selective_aug.py`

**특정 클래스만 학습 중 증강에서 제외**하는 모듈입니다. 기본값은 신문지(class 10).

신문지는 원본이 1,736장뿐이라 **오프라인에서 미리 4배 증강해** 데이터셋에 넣었습니다.
여기에 학습 중 증강(mosaic/mixup/HSV/flip)까지 걸리면 같은 원본에 증강이 이중으로
쌓여 과증강이 됩니다. 그래서 신문지만 증강 파이프라인을 우회시킵니다.

**노트북 셀이 아니라 별도 `.py` 인 이유**는 Windows 의 멀티프로세싱 때문입니다.
`workers > 0` 이면 DataLoader worker 가 dataset 객체를 pickle 로 받는데, pickle 은
클래스의 *모듈 경로* 만 저장합니다. 노트북 셀에서 정의하면 모듈이 `__main__`(= 노트북)
이 되어 worker 가 import 하지 못합니다. 또 `__getitem__` 은 던더라 인스턴스에 꽂아도
무시되므로(파이썬이 타입에서 찾음) **서브클래스**여야 합니다.

### 기타

| 항목 | 설명 |
|---|---|
| `_archive/` | `00_01.ipynb`(초기 통합본), `03_yolo_no_aug_tuned_B03.ipynb` |
| `yolo26n.pt`, `weights/` | Ultralytics 가 자동 다운로드한 사전학습 가중치 |
| `runs/detect/` | Ultralytics 기본 출력 경로로 흘러나온 결과 (실험 산출물 아님) |
| `__pycache__/` | `selective_aug.py` 컴파일 캐시 |

> `runs/`, `weights/`, `yolo26n.pt`, `__pycache__/` 는 **재생성 가능한 부산물**입니다.
> `.gitignore` 로 제외돼 있습니다.

---

## 4. `models/yolo/` — 실험 산출물

노트북 하나가 폴더 하나에 대응합니다. **디스크 8.6 GB 중 git 에 올라가는 것은 약 72 MB**
입니다 — `opencv_datasets/`, `runs/`, `*.pt` 가 `.gitignore` 로 제외됩니다.

```
models/yolo/
├── 00_yolo_baseline_no_aug/                      40M   ← 노트북 00
├── 01_yolo_optuna_no_aug/                        96M   ← 노트북 01
├── 02_experiment_augmentation/                  7.9G   ← 노트북 02 (+ 03 병합)
├── 04_experiment_damaged_data/                   93M   ← 노트북 04
├── 05_retune_optuna_augmentation/               400M   ← 노트북 05
├── 06_1_only_clean_experiment/                  157M   ← 노트북 06 (clean 전용)
├── 06_2_clean+20percent_damaged_mixed_experiment/155M  ← 노트북 06 (파손 20% 혼합)
├── 06_1_clean+damaged_experiment/               5.0K   ← 빈 껍데기 (미실행)
├── 07_final_training/                            25M   ← 노트북 07 (최종)
├── 99_summary/                                  1.4M   ← 발표용 정리
├── _summary_report/                             1.3M   ← 99번 노트북 산출물
├── _archive_merged_03_no_aug_tuned/              19M   ← 03번 (02번에 병합 완료)
├── _archive_old_05_retune/                      6.0K   ← 폐기된 05번 초안
└── 이미지10개씩_이미지증강실험/                   1.5M   ← 초기 소규모 예비실험
```

### 실험 폴더의 공통 구조

```
<실험폴더>/
├── runs/<실험ID>_seed<N>_e<epoch>/     Ultralytics 학습 출력
│   ├── weights/{best,last}.pt          가중치 (git 제외)
│   ├── results.csv                     epoch 별 loss·metric 추이
│   ├── args.yaml                       실제 적용된 전체 학습 인자
│   ├── confusion_matrix*.png           혼동 행렬
│   ├── Box{P,R,F1,PR}_curve.png        PR/F1 곡선
│   └── train_batch*.jpg, val_batch*.jpg  실제 입력 샘플 (증강 확인용)
├── opencv_datasets/<정책>/seed_<N>/    OpenCV 오프라인 증강 캐시 (git 제외, 재생성 가능)
└── report/
    ├── summary/
    │   ├── experiment_results.csv      ★ 실험별 최종 지표 (핵심 파일)
    │   ├── runtime_processed.yaml      그 실험이 실제로 읽은 data.yaml 사본
    │   └── opencv_generation_*.csv     OpenCV 증강 생성 로그
    ├── per_class/<실험ID>_seed<N>.csv  클래스별 AP
    ├── preprocess/                     전처리 품질 리포트 사본
    └── final_best/                     최고 성능 설정의 시각자료
```

**`report/summary/experiment_results.csv` 가 모든 분석의 기준**입니다.
19개 컬럼에 `status`, `id`, `name`, `seed`, `requested_epochs`, `actual_epochs`,
`mAP50_95`, `precision`, `recall`, `f1`, `inference_ms_per_image`, `hp_source`,
`hp_params`, `train_minutes`, `best_pt`, `dataset_yaml` 등이 들어 있습니다.

`status` 가 `OK` 인 행만 유효합니다. 실패한 실험은 `FAILED` 로 `error` 컬럼과 함께
남습니다 — 학습이 터져도 표가 깨지지 않게 한 설계입니다.

### 폴더별 고유 산출물

**`00_yolo_baseline_no_aug/`**
```
report/baseline_summary.csv       단일 baseline 실험 결과
report/baseline_config.json       설정 스냅샷
report/runtime_data.yaml          86클래스 data.yaml
prediction_samples/               예측 결과 이미지
```

**`01_yolo_optuna_no_aug/`**
```
optuna_study.db                   Optuna sqlite study (재개용, 삭제하면 처음부터)
tune_runs/trial_NNNN/             trial 별 학습 출력
final_runs/optuna_best_no_aug_seed{42,123,777}/   채택안 3시드 재검증
report/trials.csv                 29 trial 전체 기록
report/selected_trial.json        ★ 채택된 하이퍼파라미터
report/parameter_importance.csv   파라미터 중요도
report/final_multiseed.csv        3시드 결과
```

**`02_experiment_augmentation/`** — 가장 큰 폴더 (7.9 GB, 대부분 `opencv_datasets`)
```
report/summary/seed42_ranking.csv          36종 전체 순위
report/summary/multiseed_summary.csv       상위 3종 3시드 재검증
report/summary/final_compare_15epoch.csv   15 epoch 최종 비교
report/summary/hyperparameter_effect_2x2.csv  ★ 2×2 요인 분해 (03번 병합분 포함)
report/summary/best_augmentation_config.json
report/summary/opencv_bbox_retention_qa.csv   기하 증강 후 bbox 보존율 QA
```

**`05_retune_optuna_augmentation/`**
```
optuna_study_17class.db
report/optuna/trials.csv, selected_trial.json, parameter_importance.csv
report/optuna/candidate_multiseed_summary.csv   상위 후보 3시드
report/optuna/top2_hyperparameters.json         ★ 06번이 읽어감
report/summary/top2_augmentations.json          ★ 06번이 읽어감
report/summary/retune_compare.csv
```

**`07_final_training/`** — 최종
```
report/decision/final_decision.json          ★ 무엇을 왜 골랐는지 전부 기록
report/decision/augmentation_effect.csv      증강별 평균 Δ (05·06-1·06-2 취합)
report/decision/hyperparameter_effect.csv    하이퍼파라미터 평균 Δ
report/summary/final_result.csv              ★ 최종 지표 + 데이터 규모
report/per_class/final_Y08_auto_seed42_e20.csv
report/final_best/best.pt                    배포본 사본
```

`final_decision.json` 은 취합한 노트북, 선택 이유, 학습 인자, 데이터 규모,
신문지 증강 제외 여부까지 한 파일에 담고 있어 **재현의 기준점**입니다.

**`99_summary/`** — 발표용. 그래프 12종 + `troubleshooting.csv`
```
01_headline_journey.png       10_newspaper_retrospective.png
02_86_to_17_classes.png       11_data_composition.png
03_optuna.png                 12_imbalance_improvement.png
...
troubleshooting.csv           ★ 문제-해결-효과 기록 (6장 참고)
```

**`_summary_report/`** — `99_results_summary.ipynb` 가 생성하는 그래프 11종과
`dataset_split_by_class.csv`(클래스별 train/val 집계), `summary_table.csv`.

> `99_summary/` 와 `_summary_report/` 는 **용도가 다릅니다.**
> 전자는 손으로 큐레이션한 발표용, 후자는 노트북이 자동 생성하는 분석용입니다.

---

## 5. 실험 흐름과 개선 과정

```
00  86클래스 baseline              0.3765
     │  하이퍼파라미터만 변경 (같은 데이터)
01  86클래스 Optuna                0.5209   ← +38%, 유일하게 순수한 성능 개선
     │
     │  ◆ 클래스 체계 변경: 86 → 17 (문제 자체가 쉬워짐, 개선 아님)
     ▼
02  17클래스 증강 36종 비교          최고 +0.013
     │  └ 03번이 2×2 의 빈 칸(B03)을 채워 병합
     │
     │  ◆ 데이터 확대: 7,624 → 15,516
     ▼
04  파손 데이터 투입                B01 0.8670
05  17클래스 재튜닝 + 증강 재실험     Y14 0.8584
     │
     │  ◆ 파손 비율 2종 분기
     ▼
06-1 clean 전용 / 06-2 clean+20% 파손   Y08_hp1 0.842
     │  05·06-1·06-2 를 취합해 최적 설정 확정
     │
     │  ◆ 데이터 확대: → 144,315 (9배)
     ▼
07  최종 학습 20 epoch              0.8639   ← 배포
```

### 각 단계에서 배운 것

**① 하이퍼파라미터 최적화는 효과가 컸다 — 단, 튜닝한 그 데이터에서만 (00 → 01)**

같은 데이터·같은 클래스·같은 epoch 에서 하이퍼파라미터만 바꿔 **+38%**.
시드 3개에서 편차 0.005 이하로 재현됐습니다. 중요도는 `lrf`(0.35) → `lr0`(0.22) →
`warmup_epochs`(0.16) 순이었고, `optimizer` 와 `cos_lr` 은 사실상 무의미했습니다.

**② 그 값은 데이터셋이 바뀌면 옮겨가지 않는다**

| 적용처 | 효과 |
|---|---|
| 86클래스 (탐색한 곳) | **+0.144** |
| 17클래스에 그대로 적용 | **−0.041** |
| 17클래스에서 다시 탐색 | −0.009 ~ −0.013 |

17클래스에서 **다시 튜닝해도** `optimizer="auto"` 를 이기지 못했습니다.
06-1·06-2 를 포함한 6회 측정에서 개선 비율 0%. 그래서 최종 모델은 `auto` 를 씁니다.

Ultralytics 의 `auto` 는 데이터 규모와 클래스 수를 보고 optimizer·lr·momentum 을
함께 정합니다. 데이터가 7,624 → 144,315 로 19배가 되면 에폭당 스텝 수도 19배라
적정 학습률이 달라지는데, 고정된 Optuna 값은 그걸 따라가지 못합니다.

**③ 증강 기법 선택의 효과는 작았다 — 측정이 제대로 된 범위에서는**

36종 중 최고가 `+0.013` 인데 시드 편차가 `±0.026` 이었습니다. 차이가 노이즈에
묻혀 있어 단일 시드 순위는 신뢰할 수 없습니다.

다만 **기하 변형을 겹쳐 쌓으면 확실히 무너집니다** (`H03 −0.220`, `C13 −0.188`,
`C09 −0.176`). bbox 가 깨지는 기계적 실패라 데이터가 바뀌어도 유지됩니다.

**④ mosaic 계열은 한동안 측정 자체가 되지 않았다**

02번에서 `Y08 mosaic` · `Y09 mixup` · `Y10 cutmix` · `Y14 셋 조합` 의 지표가
**소수점 여섯 자리까지 동일**했습니다. 원인은 `close_mosaic = EPOCHS` 설정이었고,
고친 뒤 재측정하니 mosaic 이 **1위 증강**으로 올라왔습니다 ([6장](#6-겪은-문제와-해결)).

**⑤ 최종 설정**

05·06-1·06-2 세 노트북의 결과를 취합해 결정했습니다.

```
증강            Y08 yolo_mosaic     평균 Δ +0.0415 (3회 측정, 개선비율 100%)
하이퍼파라미터   auto               튜닝값은 6회 모두 auto 보다 나쁨 (평균 Δ −0.0115)
```

---

## 6. 겪은 문제와 해결

`models/yolo/99_summary/troubleshooting.csv` 에 기록된 내용입니다.

| 구분 | 문제 | 해결 | 효과 |
|---|---|---|---|
| 설계 | 86클래스는 클래스당 평균 89장뿐이라 학습 근거 부족 | 배출 방법이 같은 소분류를 묶어 17클래스로 재편 (클래스당 448장) | 가장 큰 성능 향상 |
| 설정 | `close_mosaic=10` + `epochs=10` → mosaic 이 전 구간 꺼짐 | `CLOSE_MOSAIC_EPOCHS = round(EPOCHS * 0.2)` 로 비율 계산 | mosaic 이 1위 증강으로 확인됨 |
| 배포 | `weights/best.pt` 가 COCO 80클래스 사전학습 모델이었음 | 17클래스 모델로 교체 + 학습 스크립트가 자동 배포 | 서비스 예측이 정상화 |
| 데이터 | 라벨에 존재하지 않는 class 76 이 남아 학습 중단 | manifest·클래스 매핑 대조 후 올바른 id 로 수정 | 학습 재개 |
| 실험 | Optuna 중단 시 trial 이 `RUNNING` 으로 남아 재시작 불가 | 끊긴 trial 을 `FAIL` 처리하고 미시도 출발점만 재예약 | DB 삭제 없이 이어서 탐색 |
| 실험 | top-2 하이퍼파라미터 선택이 같은 trial 을 두 번 고름 | trial 기준 중복 제거 후 상위 2개 선택 | 교차 실험 8개 중 2개 중복 학습 방지 |
| 증강 | 신문지는 이미 4배 증강된 상태라 추가 증강 시 과증강 | 별도 모듈의 `YOLODataset` 서브클래스로 신문지만 증강 우회 | worker 프로세스까지 정상 적용 |
| 환경 | PowerShell 파이프가 UTF-8 출력을 cp949 로 잘못 해석 | 파이썬이 로그 파일을 직접 UTF-8 로 기록 | 20시간치 로그 보존 |

### `close_mosaic` 문제 상세

가장 오래 결론을 왜곡했던 문제라 따로 남깁니다.

`close_mosaic=N` 은 **"마지막 N epoch 동안 mosaic 을 끈다"** 는 뜻입니다.
`epochs=10` 에 `close_mosaic=10` 이면:

```python
# ultralytics/engine/trainer.py:485
if epoch == (self.epochs - self.args.close_mosaic):   # 10 - 10 = 0
    self._close_dataloader_mosaic()                   # 첫 epoch 부터 발동
```

그리고 그 함수는 mosaic 만 끄지 않습니다.

```python
# ultralytics/data/dataset.py:364
def close_mosaic(self, hyp):
    hyp.mosaic = 0.0
    hyp.copy_paste = 0.0
    hyp.mixup = 0.0      # mixup 도
    hyp.cutmix = 0.0     # cutmix 도 같이
```

그래서 네 설정이 전부 "증강 없음"으로 붕괴해 같은 값을 냈습니다.
지금은 `round(EPOCHS * 0.2)` 로 계산합니다 (20 epoch → 4).

---

## 7. 숫자를 읽을 때의 규칙

**이 프로젝트는 진행 중에 클래스 체계가 한 번, 데이터 규모가 여러 번 바뀌었습니다.**
서로 다른 노트북의 mAP 를 나란히 놓고 비교하면 잘못된 결론이 나옵니다.

| 노트북 | 클래스 | 학습 이미지 | 검증 이미지 |
|---|---:|---:|---:|
| 00, 01 | 86 | 7,623 | 2,201 |
| 02 | 17 | 7,624 | 2,201 |
| 04, 05 | 17 | 15,516 | 2,201 |
| 06-1, 06-2 | 17 | **미기록** | — |
| 07 | 17 | **144,315** | **10,548** |

**비교해도 되는 것**

- 같은 노트북 안의 실험끼리
- 00 ↔ 01 (같은 데이터·클래스·epoch)

**비교하면 안 되는 것**

- 86클래스(00·01)와 17클래스(02 이후) — 02번에서 mAP 가 0.38 → 0.83 으로 뛴 것은
  성능 개선이 아니라 **클래스를 합쳐 문제를 쉽게 만든 결과**입니다.
- 04번 `0.8670` 과 07번 `0.8639` — 07번은 학습 데이터가 9배, 검증셋이 5배 큽니다.
  **훨씬 어려운 조건에서 비슷한 점수를 냈으므로 07번이 실질적으로 더 강합니다.**

**그 밖의 주의**

- **단일 시드 순위는 신뢰하지 마세요.** 이 데이터셋의 시드 편차는 `±0.02` 수준인데
  증강 기법 간 차이는 `0.004` 였습니다. 판단은 3시드 평균으로 합니다.
- **`test` 분할이 없습니다.** 모든 수치는 val 기준이므로 엄밀히는 "검증 성능"입니다.
- **클래스 불균형이 남아 있습니다.** train 최다 유리병 11,978 vs 최소 신문지 1,736
  (6.9배). 특히 **신문지는 val 이 16장(객체 21개)뿐**이라 그 클래스의 AP 는
  통계적으로 의미가 약합니다.
- **06-1·06-2 는 학습 이미지 수가 기록되지 않았습니다.** 앞으로는 실험 결과에
  `train_images` 를 반드시 남기세요 — 07번 `final_result.csv` 는 남기고 있어서
  사후 분석이 가능했습니다.

---

## 신문지 증강 A/B 실험

같은 데이터·같은 설정으로 **변수 하나만 바꿔** 20 epoch 씩 두 번 학습했습니다.

```python
# ai/notebooks/07_final_training.py
EXCLUDE_NEWSPAPER_FROM_AUG = True    # 1차 — 신문지만 학습 중 증강에서 제외
EXCLUDE_NEWSPAPER_FROM_AUG = False   # 2차 — 다른 클래스와 동일하게 증강
```

나머지는 전부 동일합니다 (`Y08 mosaic=0.7` / `close_mosaic=4` / `optimizer=auto` /
`epochs=20` / `batch=8` / `seed=42` / train 144,315 / val 10,548).

### 결과 — 2차(증강 포함)가 낫습니다

| 지표 | 1차 `newsNoAug` | 2차 `newsAug` | 차이 |
|---|---|---|---|
| **mAP50-95** | 0.8638 | **0.8676** | **+0.0038** |
| mAP50 | 0.9173 | **0.9226** | +0.0053 |
| Precision | 0.8911 | **0.8987** | +0.0076 |
| Recall | 0.8816 | **0.8971** | +0.0155 |

클래스별로는 **12개 개선 / 5개 악화**, 예측대로 신문지가 가장 크게 올랐습니다.

| 클래스 | 1차 | 2차 | 차이 |
|---|---|---|---|
| **종이류/신문지** | 0.4396 | **0.4765** | **+0.0369** |
| 종이류/종이 | 0.7094 | 0.7237 | +0.0143 |
| 도기류/도기 | 0.9394 | 0.9463 | +0.0069 |
| … | | | |
| 형광등/형광등 | 0.9017 | 0.8945 | −0.0072 |
| 고철류/비철금속 | 0.6855 | 0.6796 | −0.0060 |

**신문지를 뺀 16개 클래스 평균은 +0.0017** 로, 우려했던 "다른 클래스 손해"는 없었습니다.

### 해석할 때 주의

- **전체 +0.0038 은 seed 편차(std 0.0085) 범위 안**입니다. 단일 수치로는 유의하다고
  말하기 어렵고, **4개 지표가 모두 오르고 12/17 클래스가 개선된 방향의 일관성**이 근거입니다.
- 신문지 +0.0369 는 06-1 실험에서 기대했던 폭(0.41 → 0.77)에 한참 못 미칩니다.
  그 실험은 신문지가 58장뿐이던 시절이라 1,736장 규모에 그대로 적용한 것이 무리였습니다.
- **신문지 val 은 16장**이라 이 클래스의 수치 자체가 흔들릴 수 있습니다.

### 결론

"이미 오프라인에서 4배 증강했으니 추가 증강은 과증강"이라는 1차의 판단은
**틀렸습니다.** 신문지도 다른 클래스와 동일하게 증강하는 것이 낫습니다.

`selective_aug.py` 는 삭제하지 않고 남겨 둡니다. 특정 클래스만 증강에서 빼는 기능
자체는 유효하고, 이 A/B 의 1차 조건을 재현하려면 필요합니다.

---

## 재현 방법

```bash
# 1. 전처리 — data/processed 생성
uv run python ai/preprocessing/01_common_detection_preprocess_flexible_damage.py

# 2. 최종 학습 (약 20시간)
#    현재 설정은 EXCLUDE_NEWSPAPER_FROM_AUG = False (2차, 권장)
#    1차 조건을 재현하려면 07_final_training.py:290 을 True 로 바꾸세요.
#    run 이름에 newsAug / newsNoAug 태그가 자동으로 붙어 결과가 섞이지 않습니다.
uv run --no-sync python ai/notebooks/07_final_training.py --log train.log

# 2-1. 중간에 멈췄다면 마무리만
uv run --no-sync python ai/notebooks/07_finalize.py --deploy

# 3. 결과 정리 그래프
#    ai/notebooks/99_results_summary.ipynb 를 커널 "Python 3.13 (recycling_ssg)" 로 실행
```

노트북 커널은 프로젝트 venv 여야 합니다.

```
C:\AIchallengers\recycling_ssg_project\recycling_ssg\.venv\Scripts\python.exe
```
