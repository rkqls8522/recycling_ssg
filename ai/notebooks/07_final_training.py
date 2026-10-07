#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""07. 최종 학습 — 20 epoch (터미널 실행용 스크립트)

원래 07_final_training.ipynb 를 터미널용으로 옮긴 것이며, 노트북판은 정리하고
이 스크립트만 남겼습니다. 편집기 없이 돌아가므로 VSCode 가 죽어도
학습이 끊기지 않습니다.

    cd <프로젝트 루트>
    .venv/Scripts/python.exe ai/notebooks/07_final_training.py 2>&1 | tee train.log

## 왜 전부 main() 안에 있는가

Windows 의 DataLoader worker 는 fork 가 아니라 spawn 이라, 자식 프로세스가
이 파일을 **다시 import** 합니다. 실행 코드를 모듈 최상위에 두면 worker 마다
스크립트 전체가 다시 돌아 프로세스가 폭주합니다. 그래서 모든 코드는 main()
안에 두고 `if __name__ == "__main__"` 로 감쌉니다.

## 노트북과 다른 점

- 그래프를 화면에 띄우지 않고 report/ 아래에 파일로만 저장합니다 (Agg 백엔드).
- display() 는 print() 로 대체됩니다.
- 경로 기준이 '현재 작업 디렉터리'가 아니라 '이 파일의 위치'입니다.
  덕분에 어느 폴더에서 실행해도 동작합니다.
"""

from __future__ import annotations

import sys

import matplotlib

# 화면이 없는 터미널에서도 그림을 저장할 수 있게 먼저 지정합니다.
matplotlib.use("Agg")

# 콘솔로 직접 출력할 때는 건드리지 않습니다.
# Windows 의 파이썬은 콘솔 핸들에 WriteConsoleW 를 쓰므로 코드페이지와 무관하게
# 한글이 제대로 나옵니다. 반대로 여기서 UTF-8 로 고정해 버리면 cp949 콘솔에서
# 오히려 깨집니다. 파이프/파일로 나갈 때만 UTF-8 로 맞춥니다.
for _stream in (sys.stdout, sys.stderr):
    try:
        if not _stream.isatty():
            _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


class _Tee:
    """화면과 로그 파일에 동시에 씁니다.

    `python ... | tee train.log` 로 파이프를 태우면 PowerShell 이 중간에서
    바이트를 콘솔 코드페이지(cp949)로 잘못 디코딩해 한글이 깨집니다.
    파이썬이 직접 UTF-8 로 파일에 쓰면 셸 설정과 상관없이 로그가 온전합니다.
    """

    def __init__(self, stream, file_handle):
        self._stream = stream
        self._file = file_handle

    def write(self, text):
        self._stream.write(text)
        self._file.write(text)
        self._file.flush()          # 중간에 죽어도 로그가 남도록 매번 비웁니다
        return len(text)

    def flush(self):
        self._stream.flush()
        self._file.flush()

    def isatty(self):
        # 진행바가 콘솔용으로 그려지도록 원래 스트림의 성질을 그대로 전달합니다.
        return getattr(self._stream, "isatty", lambda: False)()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def display(*args, **kwargs):
    """노트북의 display() 를 대신합니다. DataFrame 은 그대로 출력됩니다."""
    for item in args:
        print(item)
        print()


def _parse_args():
    """실행 옵션.

    parse_known_args 를 쓰는 이유: spawn 된 worker 프로세스의 sys.argv 는
    부모와 다릅니다. 모르는 인자가 있어도 죽지 않아야 합니다.
    """
    import argparse

    parser = argparse.ArgumentParser(description="07. 최종 학습")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="결과 취합·설정 확정·신문지 제외 검증까지만 하고 학습 직전에 멈춥니다.",
    )
    parser.add_argument(
        "--smoke",
        action="store_true",
        help="2 epoch 만 돌려 학습까지 포함한 전체 배선을 빠르게 점검합니다.",
    )
    parser.add_argument(
        "--log",
        metavar="파일",
        default=None,
        help="화면과 함께 이 파일에도 UTF-8 로 기록합니다. "
             "셸 파이프(| tee)보다 안전하니 이 옵션을 쓰세요.",
    )
    return parser.parse_known_args()[0]


_ARGS = _parse_args()


def main():

    # ==========================================================================
    # 07. 최종 학습 — 20 epoch, 최종 데이터셋
    # --------------------------------------------------------------------------
    #
    # 05번(재튜닝 + 증강 재실험)과 06번(파손 데이터 2종)의 결과를 **한 표로 취합해서**
    # 최적의 하이퍼파라미터와 증강 기법을 확정하고, 그 설정으로 최종 데이터셋(약 86GB)을
    # **20 epoch** 학습합니다.
    #
    # ## 이 노트북이 하는 일
    #
    # | 단계 | 내용 |
    # | --- | --- |
    # | 1~5 | 환경 / 경로 / 최종 데이터셋 점검 |
    # | 6 | **05 + 06 결과 취합 → 하이퍼파라미터와 증강 확정** |
    # | 7 | **신문지만 증강 제외** 설정과 검증 |
    # | 8 | 20 epoch 최종 학습 |
    # | 9 | 평가 · 클래스별 성능 · 배포용 가중치 |
    #
    # ## 신문지를 증강에서 빼는 이유
    #
    # 신문지(`class_id = 10`)는 원본 수량이 적어 **오프라인에서 미리 4배로 증강해**
    # 데이터셋에 넣어 두었습니다. 여기에 학습 중 증강까지 걸리면 같은 원본에 변형이
    # 이중으로 쌓여 과증강이 됩니다. 그래서 신문지 이미지만 증강 파이프라인을
    # 우회시키고 나머지 16개 클래스는 정상적으로 증강합니다.
    #
    # 구현은 같은 폴더의 `selective_aug.py` 에 있습니다. 노트북 셀이 아니라 별도
    # 모듈 파일인 이유는, `workers > 0` 일 때 DataLoader worker 가 dataset 을
    # **pickle 로** 받는데 pickle 은 클래스의 *모듈 경로* 를 저장하기 때문입니다.
    # 노트북 셀에서 정의하면 모듈이 `__main__` 이 되어 worker 가 import 하지 못합니다.
    #
    # ## 실행 순서
    #
    # 06번 노트북을 `DATA_IS_ONLY_CLEAN = True` / `False` 로 **두 번 다 돌린 뒤**
    # 이 노트북을 실행하는 것이 가장 좋습니다. 아직 덜 돌렸어도 6단계는
    # **찾은 결과만으로** 동작하며, 어떤 결과가 빠졌는지 표시해 줍니다.
    # ==========================================================================

    # ==========================================================================
    # 1. 라이브러리
    # --------------------------------------------------------------------------
    # ==========================================================================

    # --- [셀 2] --------------------------------------------------------

    import json
    import time
    import random
    import shutil
    import gc
    import sys
    from pathlib import Path

    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    import yaml
    import torch

    from ultralytics import YOLO

    try:
        import ultralytics
        ULTRALYTICS_VERSION = ultralytics.__version__
    except Exception:
        ULTRALYTICS_VERSION = "unknown"

    try:
        from ultralytics.cfg import DEFAULT_CFG_DICT
    except Exception:
        DEFAULT_CFG_DICT = {}


    pd.set_option("display.max_columns", 300)
    pd.set_option("display.max_rows", 500)


    def set_korean_font():
        candidates = ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR"]
        installed = {font.name for font in fm.fontManager.ttflist}

        for name in candidates:
            if name in installed:
                plt.rcParams["font.family"] = name
                break

        plt.rcParams["axes.unicode_minus"] = False


    set_korean_font()

    print("Ultralytics:", ULTRALYTICS_VERSION)
    print("PyTorch    :", torch.__version__)

    # ==========================================================================
    # 2. 경로와 공통 설정
    # --------------------------------------------------------------------------
    #
    # `EPOCHS` 만 20으로 올리는 것이 아니라 **`close_mosaic` 도 같이 올려야** 합니다.
    #
    # `close_mosaic=N` 은 "마지막 N epoch 동안 mosaic/mixup/cutmix 를 끈다"는 뜻입니다.
    # Ultralytics 기본값은 10 이라, 20 epoch 에서 그대로 두면 절반 동안 mosaic 이
    # 꺼집니다. 05/06번에서 쓴 비율(전체의 20% 정도)에 맞춰 **4** 로 둡니다.
    # ==========================================================================

    # --- [셀 4] --------------------------------------------------------
    # 노트북에서는 Path.cwd() 였습니다. 스크립트는 어디서 실행하든
    # 같은 곳을 가리켜야 하므로 이 파일의 위치를 기준으로 삼습니다.
    PROJECT_ROOT = Path(__file__).resolve().parent

    # ------------------------------------------------------------
    # 1) 최종 학습에 쓸 데이터셋 (약 86GB)
    # ------------------------------------------------------------
    # 기본값은 기존과 같은 data/processed 입니다. 최종 데이터셋을 다른 곳에
    # 두었다면 이 한 줄만 바꾸세요.
    PROCESSED_DIR = (PROJECT_ROOT / "../../data/processed").resolve()

    if not PROCESSED_DIR.exists():
        raise FileNotFoundError(f"데이터 폴더가 없습니다: {PROCESSED_DIR}")

    DATA_YAML = PROCESSED_DIR / "data.yaml"

    # ------------------------------------------------------------
    # 2) 05 / 06번 결과를 읽어올 위치
    # ------------------------------------------------------------
    MODELS_DIR = (PROJECT_ROOT / "../models/yolo").resolve()

    # ------------------------------------------------------------
    # 3) 이 노트북의 산출물 위치
    # ------------------------------------------------------------
    EXPERIMENT_ROOT = MODELS_DIR / "07_final_training"

    RUNS_DIR = EXPERIMENT_ROOT / "runs"
    REPORT_ROOT = EXPERIMENT_ROOT / "report"
    SUMMARY_DIR = REPORT_ROOT / "summary"
    PER_CLASS_DIR = REPORT_ROOT / "per_class"
    DECISION_DIR = REPORT_ROOT / "decision"
    FINAL_DIR = REPORT_ROOT / "final_best"

    for path in [EXPERIMENT_ROOT, RUNS_DIR, REPORT_ROOT,
                 SUMMARY_DIR, PER_CLASS_DIR, DECISION_DIR, FINAL_DIR]:
        path.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------
    # 4) 학습 설정
    # ------------------------------------------------------------
    MODEL_NAME = "yolo26n.pt"
    EPOCHS = 20
    IMGSZ = 640
    BATCH = 8
    PATIENCE = 15

    # 전체 epoch 의 20% 구간에서만 multi-image 증강을 끕니다 (05/06번과 같은 비율).
    CLOSE_MOSAIC_EPOCHS = max(1, round(EPOCHS * 0.2))

    WORKERS = 4
    SEED = 42

    RUN_TRAINING = True
    SMOKE_TEST = _ARGS.smoke          # True 로 두면 2 epoch 만 돌려 배선을 점검합니다.

    if SMOKE_TEST:
        EPOCHS = 2
        PATIENCE = 2
        CLOSE_MOSAIC_EPOCHS = 1

    # ------------------------------------------------------------
    # 5) 신문지 증강 제외
    # ------------------------------------------------------------
    # 1차 학습(0.8638)에서는 True 였습니다. 그 결과 신문지 mAP 가 0.4396 으로
    # 최하위였고, 06-1 실험에서 신문지가 오히려 증강 효과를 가장 크게 받는
    # 클래스였던 점을 근거로 이번에는 제외하지 않고 함께 증강합니다.
    EXCLUDE_NEWSPAPER_FROM_AUG = False
    NEWSPAPER_CLASS_ID = 10                 # 종이류/신문지

    # "all" : 이미지의 모든 박스가 신문지일 때만 제외 (권장)
    # "any" : 신문지 박스가 하나라도 있으면 제외
    NEWSPAPER_MATCH_RULE = "all"

    # mosaic/mixup/cutmix 가 '다른 이미지'를 끌어올 때도 신문지를 피할지 여부.
    # True 면 신문지가 다른 이미지의 mosaic 조각으로도 들어가지 않습니다.
    FILTER_NEWSPAPER_FROM_MIX_PARTNERS = True

    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)

    print("PROJECT_ROOT       :", PROJECT_ROOT)
    print("PROCESSED_DIR      :", PROCESSED_DIR)
    print("MODELS_DIR         :", MODELS_DIR)
    print("EXPERIMENT_ROOT    :", EXPERIMENT_ROOT)
    print("MODEL_NAME         :", MODEL_NAME)
    print("EPOCHS             :", EPOCHS)
    print("CLOSE_MOSAIC_EPOCHS:", CLOSE_MOSAIC_EPOCHS)
    print("IMGSZ / BATCH      :", IMGSZ, "/", BATCH)
    print("SMOKE_TEST         :", SMOKE_TEST)
    print("신문지 증강 제외   :", EXCLUDE_NEWSPAPER_FROM_AUG)

    # ==========================================================================
    # 3. GPU 확인
    # --------------------------------------------------------------------------
    # ==========================================================================

    # --- [셀 6] --------------------------------------------------------
    if torch.cuda.is_available():
        DEVICE = 0
        print("GPU        :", torch.cuda.get_device_name(0))
        print("CUDA       :", torch.version.cuda)
        total_gb = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
        print(f"VRAM       : {total_gb:.1f} GB")
    else:
        DEVICE = "cpu"
        print("GPU를 찾지 못했습니다. CPU로 학습하면 매우 느립니다.")

    print("DEVICE     :", DEVICE)

    # ==========================================================================
    # 4. data.yaml 보정
    # --------------------------------------------------------------------------
    #
    # `data.yaml` 의 `path` 가 다른 PC 경로로 적혀 있을 수 있으므로, 원본은 건드리지 않고
    # 현재 경로로 고친 **런타임 사본**을 만들어 학습에 넘깁니다.
    # ==========================================================================

    # --- [셀 8] --------------------------------------------------------
    if not DATA_YAML.exists():
        raise FileNotFoundError(DATA_YAML)

    with open(DATA_YAML, "r", encoding="utf-8") as file:
        dataset_config = yaml.safe_load(file)

    dataset_config["path"] = str(PROCESSED_DIR.resolve())

    RUNTIME_DATA_YAML = SUMMARY_DIR / "runtime_processed.yaml"

    with open(RUNTIME_DATA_YAML, "w", encoding="utf-8") as file:
        yaml.safe_dump(dataset_config, file, allow_unicode=True, sort_keys=False)

    names_raw = dataset_config["names"]

    if isinstance(names_raw, dict):
        CLASS_NAMES = {int(key): str(value) for key, value in names_raw.items()}
    else:
        CLASS_NAMES = {index: str(value) for index, value in enumerate(names_raw)}

    NUM_CLASSES = len(CLASS_NAMES)

    print(RUNTIME_DATA_YAML.read_text(encoding="utf-8"))
    print("클래스 수:", NUM_CLASSES)

    if NEWSPAPER_CLASS_ID not in CLASS_NAMES:
        raise ValueError(
            f"class_id {NEWSPAPER_CLASS_ID} 가 data.yaml 에 없습니다. "
            "NEWSPAPER_CLASS_ID 를 확인하세요."
        )

    print(f"신문지 클래스: {NEWSPAPER_CLASS_ID} = {CLASS_NAMES[NEWSPAPER_CLASS_ID]}")

    # ==========================================================================
    # 5. 최종 데이터셋 점검
    # --------------------------------------------------------------------------
    #
    # 이미지/라벨 개수가 맞는지, 그리고 **지금 보고 있는 것이 정말 최종 데이터셋인지**
    # 확인합니다. 05/06번은 약 7,600장(clean) 규모였으므로, 수치가 그와 비슷하면
    # 아직 최종 데이터셋으로 교체되지 않은 것입니다.
    # ==========================================================================

    # --- [셀 10] --------------------------------------------------------
    TRAIN_IMAGE_DIR = PROCESSED_DIR / "images" / "train"
    VAL_IMAGE_DIR = PROCESSED_DIR / "images" / "val"
    TRAIN_LABEL_DIR = PROCESSED_DIR / "labels" / "train"
    VAL_LABEL_DIR = PROCESSED_DIR / "labels" / "val"

    for path in [TRAIN_IMAGE_DIR, VAL_IMAGE_DIR, TRAIN_LABEL_DIR, VAL_LABEL_DIR]:
        if not path.exists():
            raise FileNotFoundError(path)

    train_images = sorted(path for path in TRAIN_IMAGE_DIR.iterdir() if path.is_file())
    val_images = sorted(path for path in VAL_IMAGE_DIR.iterdir() if path.is_file())
    train_labels = sorted(TRAIN_LABEL_DIR.glob("*.txt"))
    val_labels = sorted(VAL_LABEL_DIR.glob("*.txt"))

    if len(train_images) != len(train_labels):
        raise ValueError("Train image와 label 개수가 다릅니다.")

    if len(val_images) != len(val_labels):
        raise ValueError("Validation image와 label 개수가 다릅니다.")

    if len(val_images) == 0:
        raise ValueError("Validation 이미지가 없습니다.")

    dataset_bytes = sum(path.stat().st_size for path in train_images)
    dataset_bytes += sum(path.stat().st_size for path in val_images)
    DATASET_GB = dataset_bytes / (1024 ** 3)

    print(f"Train images: {len(train_images):,}")
    print(f"Val images  : {len(val_images):,}")
    print(f"이미지 용량 : {DATASET_GB:.1f} GB")

    # 클래스별 이미지 수 (신문지가 실제로 몇 장인지 확인)
    class_counter: dict = {}
    newspaper_only_images = 0

    print(f"라벨 {len(train_labels):,}개를 읽습니다. 1~3분 걸릴 수 있습니다...")

    for index, label_path in enumerate(train_labels, start=1):
        if index % 20000 == 0:
            print(f"  {index:,} / {len(train_labels):,}")

        ids = set()
        for line in label_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                ids.add(int(line.split()[0]))

        for class_id in ids:
            class_counter[class_id] = class_counter.get(class_id, 0) + 1

        if ids == {NEWSPAPER_CLASS_ID}:
            newspaper_only_images += 1

    support_df = pd.DataFrame({
        "class_id": sorted(class_counter),
        "class_name": [CLASS_NAMES.get(index, f"class_{index}") for index in sorted(class_counter)],
        "train_images": [class_counter[index] for index in sorted(class_counter)],
    }).sort_values("train_images")

    display(support_df)

    print()
    print(f"신문지만 들어 있는 train 이미지: {newspaper_only_images:,}장 "
          f"({newspaper_only_images / max(len(train_labels), 1):.2%})")

    if len(train_images) < 20000:
        print()
        print("[확인 필요] train 이미지가 2만 장 미만입니다.")
        print("            05/06번에서 쓰던 clean 데이터(약 7,600장)일 수 있습니다.")
        print("            최종 데이터셋(약 86GB)으로 교체했는지 확인하세요.")

    # ==========================================================================
    # 6. 05 + 06번 결과 취합 — 최적 설정 확정
    # --------------------------------------------------------------------------
    #
    # ## 왜 단순히 "1등 조합"을 쓰면 안 되는가
    #
    # 각 노트북의 1등은 서로 다릅니다.
    #
    # - 05번(10 epoch): `Y14`(mosaic+mixup+cutmix)가 1위
    # - 06-1번(15 epoch): `Y08_hp1`(mosaic + tuned)이 1위
    #
    # epoch 수도 다르고 데이터도 다르므로 **mAP 절대값을 그대로 비교할 수 없습니다.**
    # 그래서 각 실험 묶음 안에서 **기준선 대비 차이(Δ)** 로 바꾼 뒤 평균을 냅니다.
    #
    # ## 두 가지를 따로 집계합니다
    #
    # | 집계 | 기준선 | 묶는 단위 |
    # | --- | --- | --- |
    # | **증강 효과** | 같은 묶음의 `증강 OFF` | (노트북, 하이퍼파라미터)가 같은 행끼리 |
    # | **하이퍼파라미터 효과** | 같은 묶음의 `auto` | (노트북, 증강)이 같은 행끼리 |
    #
    # 이렇게 하면 "증강 때문에 오른 것"과 "하이퍼파라미터 때문에 오른 것"이 섞이지
    # 않습니다. 05번에서 하던 2×2 분해(B00/B01/B02/B03)를 여러 노트북으로 확장한 것과
    # 같습니다.
    # ==========================================================================

    # --- [셀 12] --------------------------------------------------------
    # 취합 대상. 폴더가 없으면 자동으로 건너뜁니다.
    RESULT_SOURCES = [
        {
            "key": "05",
            "label": "05 재튜닝 (10 epoch)",
            "dir": MODELS_DIR / "05_retune_optuna_augmentation",
        },
        {
            "key": "06_1",
            "label": "06-1 clean (15 epoch)",
            "dir": MODELS_DIR / "06_1_only_clean_experiment",
        },
        {
            "key": "06_2",
            "label": "06-2 clean+20% damage (15 epoch)",
            "dir": MODELS_DIR / "06_2_clean+20percent_damaged_mixed_experiment",
        },
    ]

    # True 로 두면 위 세 곳이 모두 있어야 진행합니다.
    # 06번을 아직 다 돌리지 않았다면 False 로 두고, 나중에 다시 실행하세요.
    REQUIRE_ALL_SOURCES = False

    loaded_frames = []
    missing_sources = []

    for source in RESULT_SOURCES:
        results_csv = source["dir"] / "report" / "summary" / "experiment_results.csv"

        if not results_csv.exists():
            missing_sources.append(source["label"])
            continue

        frame = pd.read_csv(results_csv)
        frame = frame[frame["status"].eq("OK")].copy()

        if not len(frame):
            missing_sources.append(source["label"] + " (성공한 행이 없음)")
            continue

        frame["source_key"] = source["key"]
        frame["source_label"] = source["label"]
        loaded_frames.append(frame)

        print(f"불러옴: {source['label']:<34} {len(frame):>3}개 실험")

    if missing_sources:
        print()
        print("아직 없는 결과:")
        for name in missing_sources:
            print("  -", name)

    if REQUIRE_ALL_SOURCES and missing_sources:
        raise FileNotFoundError("REQUIRE_ALL_SOURCES=True 인데 빠진 결과가 있습니다.")

    if not loaded_frames:
        raise FileNotFoundError("취합할 결과가 하나도 없습니다. 05/06번을 먼저 실행하세요.")

    pooled_df = pd.concat(loaded_frames, ignore_index=True)
    print()
    print(f"취합 대상: {len(pooled_df)}개 실험 / {pooled_df['source_key'].nunique()}개 노트북")

    # --- [셀 13] --------------------------------------------------------
    def augmentation_key_of(experiment_id: str) -> str:
        '''행의 '증강 정체성'을 뽑습니다.

        06번은 교차 실험이라 id 가 'Y14_hp1' 처럼 하이퍼파라미터 라벨까지 붙어
        있습니다. 증강만 보려면 앞부분만 써야 05번의 'Y14' 와 같은 것으로 묶입니다.
        '''
        base = str(experiment_id).split("_")[0]

        if base in {"B00", "B03"}:
            return "none"           # 증강 전부 OFF
        if base in {"B01", "B02"}:
            return "yolo_default"   # Ultralytics 기본 증강

        return base                 # Y05 / Y08 / Y14 / C01 ...


    def augmentation_name_of(row) -> str:
        '''표에 보여 줄 증강 이름. id 와 마찬가지로 hp 꼬리표를 떼어냅니다.'''
        key = row["aug_key"]

        if key == "none":
            return "증강 OFF"
        if key == "yolo_default":
            return "YOLO 기본 증강"

        name = str(row.get("name", key))
        for suffix in ("_hp1", "_hp2", "_hpA", "_hpB"):
            name = name.replace(suffix, "")

        return name


    def hyperparameter_signature(raw) -> str:
        '''하이퍼파라미터를 '값' 기준으로 비교할 수 있는 서명으로 바꿉니다.

        05번은 hp_source 가 'optuna_tuned', 06번은 'hp1' 로 **이름이 다르지만**
        실제 값은 같을 수 있습니다. 이름이 아니라 값으로 묶어야 두 노트북의 결과가
        한 표에서 제대로 연결됩니다.
        '''
        if not isinstance(raw, str) or not raw.strip():
            return "auto"

        try:
            params = json.loads(raw)
        except json.JSONDecodeError:
            return "auto"

        if not params:
            return "auto"

        canonical = {
            key: (round(value, 10) if isinstance(value, float) else value)
            for key, value in sorted(params.items())
        }

        return json.dumps(canonical, sort_keys=True, ensure_ascii=False)


    pooled_df["aug_key"] = pooled_df["id"].map(augmentation_key_of)
    pooled_df["aug_name"] = pooled_df.apply(augmentation_name_of, axis=1)
    pooled_df["hp_signature"] = pooled_df["hp_params"].map(hyperparameter_signature)

    # 서명에 사람이 읽을 이름표를 붙입니다 (auto / hpA / hpB ...).
    signature_to_label = {"auto": "auto"}
    next_label = iter("ABCDEFGH")

    for signature in pooled_df["hp_signature"]:
        if signature not in signature_to_label:
            signature_to_label[signature] = "hp" + next(next_label)

    pooled_df["hp_label"] = pooled_df["hp_signature"].map(signature_to_label)

    HP_PARAMS_BY_LABEL = {
        label: (json.loads(signature) if signature != "auto" else {})
        for signature, label in signature_to_label.items()
    }

    print("하이퍼파라미터 후보")
    for label, params in HP_PARAMS_BY_LABEL.items():
        if not params:
            print(f"  {label:<5} : Ultralytics 자동 선택 (optimizer='auto')")
        else:
            brief = ", ".join(
                f"{key}={value:.5g}" if isinstance(value, float) else f"{key}={value}"
                for key, value in params.items()
            )
            print(f"  {label:<5} : {brief}")

    display(
        pooled_df[["source_key", "id", "aug_key", "aug_name", "hp_label", "mAP50_95"]]
        .sort_values(["source_key", "mAP50_95"], ascending=[True, False])
    )

    # ==========================================================================
    # 6-1. 증강 효과 집계
    # --------------------------------------------------------------------------
    #
    # 같은 노트북·같은 하이퍼파라미터 안에서 **증강 OFF 대비 얼마나 올랐는지**만
    # 봅니다. 기준선(증강 OFF)이 없는 묶음은 비교할 수 없으므로 제외합니다.
    # ==========================================================================

    # --- [셀 15] --------------------------------------------------------
    augmentation_delta_rows = []

    for (source_key, hp_label), group in pooled_df.groupby(["source_key", "hp_label"]):
        baseline = group.loc[group["aug_key"].eq("none"), "mAP50_95"]

        if baseline.empty:
            # 이 묶음에는 '증강 OFF' 가 없어 증강 효과를 잴 수 없습니다.
            continue

        baseline_score = float(baseline.mean())

        for _, row in group.iterrows():
            if row["aug_key"] == "none":
                continue

            augmentation_delta_rows.append({
                "source_key": source_key,
                "source_label": row["source_label"],
                "hp_label": hp_label,
                "aug_key": row["aug_key"],
                "aug_name": row["aug_name"],
                "mAP50_95": float(row["mAP50_95"]),
                "baseline": baseline_score,
                "delta": float(row["mAP50_95"]) - baseline_score,
            })

    augmentation_delta_df = pd.DataFrame(augmentation_delta_rows)

    if not len(augmentation_delta_df):
        raise ValueError("증강 효과를 잴 수 있는 묶음이 없습니다 (증강 OFF 기준선 부재).")

    augmentation_summary = (
        augmentation_delta_df
        .groupby(["aug_key", "aug_name"], as_index=False)
        .agg(
            측정횟수=("delta", "size"),
            평균델타=("delta", "mean"),
            최소델타=("delta", "min"),
            최대델타=("delta", "max"),
            개선비율=("delta", lambda values: float((values > 0).mean())),
        )
        .sort_values("평균델타", ascending=False)
        .reset_index(drop=True)
    )

    display(augmentation_summary)

    augmentation_summary.to_csv(
        DECISION_DIR / "augmentation_effect.csv", index=False, encoding="utf-8-sig"
    )
    augmentation_delta_df.to_csv(
        DECISION_DIR / "augmentation_effect_detail.csv", index=False, encoding="utf-8-sig"
    )

    # ==========================================================================
    # 6-2. 하이퍼파라미터 효과 집계
    # --------------------------------------------------------------------------
    #
    # 같은 노트북·같은 증강 안에서 **`auto` 대비 얼마나 올랐는지**를 봅니다.
    #
    # `auto` 는 Ultralytics 가 데이터 규모를 보고 optimizer 와 learning rate 를 스스로
    # 정하는 모드입니다. Optuna 로 찾은 값은 **7,600장 규모에 맞춰 최적화된 값**이라,
    # 데이터가 크게 늘어난 최종 학습에서도 유리할지는 따로 확인해야 합니다.
    # ==========================================================================

    # --- [셀 17] --------------------------------------------------------
    hyperparameter_delta_rows = []

    for (source_key, aug_key), group in pooled_df.groupby(["source_key", "aug_key"]):
        baseline = group.loc[group["hp_label"].eq("auto"), "mAP50_95"]

        if baseline.empty:
            # auto 기준선이 없는 묶음(예: 06번의 Y08_hp1 vs Y08_hp2)은
            # auto 대비 효과를 잴 수 없으므로 건너뜁니다.
            continue

        baseline_score = float(baseline.mean())

        for _, row in group.iterrows():
            if row["hp_label"] == "auto":
                continue

            hyperparameter_delta_rows.append({
                "source_key": source_key,
                "source_label": row["source_label"],
                "aug_key": aug_key,
                "hp_label": row["hp_label"],
                "mAP50_95": float(row["mAP50_95"]),
                "baseline_auto": baseline_score,
                "delta": float(row["mAP50_95"]) - baseline_score,
            })

    hyperparameter_delta_df = pd.DataFrame(hyperparameter_delta_rows)

    if len(hyperparameter_delta_df):
        hyperparameter_summary = (
            hyperparameter_delta_df
            .groupby("hp_label", as_index=False)
            .agg(
                측정횟수=("delta", "size"),
                평균델타=("delta", "mean"),
                최소델타=("delta", "min"),
                최대델타=("delta", "max"),
                개선비율=("delta", lambda values: float((values > 0).mean())),
            )
            .sort_values("평균델타", ascending=False)
            .reset_index(drop=True)
        )

        display(hyperparameter_delta_df.sort_values("delta", ascending=False))
        display(hyperparameter_summary)

        hyperparameter_summary.to_csv(
            DECISION_DIR / "hyperparameter_effect.csv", index=False, encoding="utf-8-sig"
        )
        hyperparameter_delta_df.to_csv(
            DECISION_DIR / "hyperparameter_effect_detail.csv", index=False, encoding="utf-8-sig"
        )

    else:
        hyperparameter_summary = pd.DataFrame(
            columns=["hp_label", "측정횟수", "평균델타", "최소델타", "최대델타", "개선비율"]
        )
        print("auto 와 직접 비교할 수 있는 묶음이 없습니다. auto 를 쓰겠습니다.")

    # ==========================================================================
    # 6-3. 그래프로 확인
    # --------------------------------------------------------------------------
    # ==========================================================================

    # --- [셀 19] --------------------------------------------------------
    set_korean_font()

    figure, axes = plt.subplots(1, 2, figsize=(16, 5.5))

    top_augmentations = augmentation_summary.head(10).iloc[::-1]
    colors = ["tab:green" if value > 0 else "tab:red" for value in top_augmentations["평균델타"]]

    axes[0].barh(top_augmentations["aug_name"], top_augmentations["평균델타"], color=colors)
    axes[0].axvline(0, color="black", linewidth=0.8)
    axes[0].set_title("증강 효과 (증강 OFF 대비 mAP50-95 평균 변화)")
    axes[0].set_xlabel("Δ mAP50-95")

    for y_position, (value, count) in enumerate(
        zip(top_augmentations["평균델타"], top_augmentations["측정횟수"])
    ):
        axes[0].text(value, y_position, f" {value:+.4f} (n={count})",
                     va="center", fontsize=9)

    if len(hyperparameter_summary):
        hp_colors = ["tab:green" if value > 0 else "tab:red"
                     for value in hyperparameter_summary["평균델타"]]
        axes[1].bar(hyperparameter_summary["hp_label"],
                    hyperparameter_summary["평균델타"], color=hp_colors)
        axes[1].axhline(0, color="black", linewidth=0.8)
        axes[1].set_title("하이퍼파라미터 효과 (auto 대비 mAP50-95 평균 변화)")
        axes[1].set_ylabel("Δ mAP50-95")

        for x_position, (value, count) in enumerate(
            zip(hyperparameter_summary["평균델타"], hyperparameter_summary["측정횟수"])
        ):
            axes[1].text(x_position, value, f"{value:+.4f}\n(n={count})",
                         ha="center", va="bottom" if value >= 0 else "top", fontsize=9)
    else:
        axes[1].text(0.5, 0.5, "auto 와 비교 가능한 결과 없음",
                     ha="center", va="center", transform=axes[1].transAxes)
        axes[1].set_axis_off()

    plt.tight_layout()
    plt.savefig(DECISION_DIR / "effect_summary.png", dpi=150, bbox_inches="tight")
    plt.close()

    # ==========================================================================
    # 6-4. 최종 설정 확정
    # --------------------------------------------------------------------------
    #
    # 집계 결과에서 자동으로 고릅니다.
    #
    # - **증강**: 평균 Δ 가 가장 큰 것
    # - **하이퍼파라미터**: 평균 Δ 가 가장 큰 것. 단 **양수일 때만** 씁니다.
    #   전부 음수라면 `auto` 가 더 낫다는 뜻이므로 `auto` 를 씁니다.
    #
    # 아래 `MANUAL_OVERRIDE_*` 에 값을 넣으면 자동 선택을 무시하고 직접 지정할 수
    # 있습니다.
    # ==========================================================================

    # --- [셀 21] --------------------------------------------------------
    # 직접 고르고 싶을 때만 값을 넣으세요. None 이면 위 집계 결과를 따릅니다.
    MANUAL_OVERRIDE_AUG_KEY = None      # 예: "Y14"
    MANUAL_OVERRIDE_HP_LABEL = None     # 예: "auto" 또는 "hpA"

    # --- 증강 선택 ---------------------------------------------------------
    if MANUAL_OVERRIDE_AUG_KEY:
        FINAL_AUG_KEY = MANUAL_OVERRIDE_AUG_KEY
        aug_decision_reason = "사용자가 직접 지정"
    else:
        FINAL_AUG_KEY = augmentation_summary.iloc[0]["aug_key"]
        aug_decision_reason = (
            f"평균 Δ {augmentation_summary.iloc[0]['평균델타']:+.4f} 로 1위 "
            f"(n={int(augmentation_summary.iloc[0]['측정횟수'])})"
        )

    FINAL_AUG_NAME = (
        augmentation_summary.loc[
            augmentation_summary["aug_key"].eq(FINAL_AUG_KEY), "aug_name"
        ].iloc[0]
        if (augmentation_summary["aug_key"] == FINAL_AUG_KEY).any()
        else FINAL_AUG_KEY
    )

    # --- 하이퍼파라미터 선택 -----------------------------------------------
    if MANUAL_OVERRIDE_HP_LABEL:
        FINAL_HP_LABEL = MANUAL_OVERRIDE_HP_LABEL
        hp_decision_reason = "사용자가 직접 지정"

    elif len(hyperparameter_summary) and hyperparameter_summary.iloc[0]["평균델타"] > 0:
        FINAL_HP_LABEL = hyperparameter_summary.iloc[0]["hp_label"]
        hp_decision_reason = (
            f"auto 대비 평균 Δ {hyperparameter_summary.iloc[0]['평균델타']:+.4f} 로 1위"
        )

    else:
        FINAL_HP_LABEL = "auto"
        if len(hyperparameter_summary):
            hp_decision_reason = (
                f"튜닝값이 auto 보다 나은 경우가 없음 "
                f"(최고 평균 Δ {hyperparameter_summary.iloc[0]['평균델타']:+.4f})"
            )
        else:
            hp_decision_reason = "auto 와 비교 가능한 결과 없음"

    FINAL_HP_PARAMS = dict(HP_PARAMS_BY_LABEL.get(FINAL_HP_LABEL, {}))

    print("=" * 78)
    print("최종 설정")
    print("=" * 78)
    print(f"  증강            : {FINAL_AUG_KEY} ({FINAL_AUG_NAME})")
    print(f"     선택 이유    : {aug_decision_reason}")
    print()
    print(f"  하이퍼파라미터  : {FINAL_HP_LABEL}")
    print(f"     선택 이유    : {hp_decision_reason}")

    if FINAL_HP_PARAMS:
        for key, value in FINAL_HP_PARAMS.items():
            print(f"       {key:<15} {value}")
    else:
        print("       optimizer='auto' (Ultralytics 자동 선택)")

    # 고른 조합이 실제로 측정된 적 있는지 알려 줍니다.
    measured = pooled_df[
        pooled_df["aug_key"].eq(FINAL_AUG_KEY) & pooled_df["hp_label"].eq(FINAL_HP_LABEL)
    ]

    print()
    if len(measured):
        print(f"  이 조합은 {len(measured)}번 직접 측정됐습니다 "
              f"(mAP50-95 {measured['mAP50_95'].min():.4f} ~ {measured['mAP50_95'].max():.4f})")
    else:
        print("  [참고] 이 조합 자체를 직접 돌린 적은 없습니다.")
        print("         증강 효과와 하이퍼파라미터 효과를 따로 집계해 조합한 결과입니다.")

    # ==========================================================================
    # 6-5. 증강 설정값 만들기
    # --------------------------------------------------------------------------
    #
    # 증강 이름(`Y08` 등)을 실제 학습 인자로 바꿉니다. 정의는 05/06번과 **같은 값**을
    # 쓰되, `close_mosaic` 만 20 epoch 에 맞춰 다시 계산합니다.
    # ==========================================================================

    # --- [셀 23] --------------------------------------------------------
    NO_AUG = {
        "hsv_h": 0.0, "hsv_s": 0.0, "hsv_v": 0.0,
        "degrees": 0.0, "translate": 0.0, "scale": 0.0,
        "shear": 0.0, "perspective": 0.0,
        "flipud": 0.0, "fliplr": 0.0, "bgr": 0.0,
        "mosaic": 0.0, "mixup": 0.0, "cutmix": 0.0, "copy_paste": 0.0,
        "close_mosaic": 0,
        "augmentations": [],
    }


    def with_no_aug(**changes):
        config = dict(NO_AUG)
        config.update(changes)
        return config


    # 05/06번의 YOLO_AUG_CONFIGS 와 같은 값입니다.
    # close_mosaic 만 이 노트북의 EPOCHS(20) 기준으로 다시 잡습니다.
    AUG_LIBRARY = {
        "hsv": with_no_aug(hsv_h=0.015, hsv_s=0.50, hsv_v=0.35),
        "flip": with_no_aug(fliplr=0.50),
        "rotation": with_no_aug(degrees=10.0),
        "translate": with_no_aug(translate=0.08),
        "scale": with_no_aug(scale=0.25),
        "shear": with_no_aug(shear=2.0),
        "perspective": with_no_aug(perspective=0.0005),
        "mosaic": with_no_aug(mosaic=0.70, close_mosaic=CLOSE_MOSAIC_EPOCHS),
        "mixup": with_no_aug(mixup=0.15, close_mosaic=CLOSE_MOSAIC_EPOCHS),
        "cutmix": with_no_aug(cutmix=0.15, close_mosaic=CLOSE_MOSAIC_EPOCHS),
        "hsv_flip": with_no_aug(hsv_h=0.015, hsv_s=0.50, hsv_v=0.35, fliplr=0.50),
        "geo_combo": with_no_aug(
            degrees=10.0, translate=0.08, scale=0.25,
            shear=2.0, perspective=0.0005, fliplr=0.50,
        ),
        "mosaic_hsv_geo": with_no_aug(
            hsv_h=0.015, hsv_s=0.45, hsv_v=0.30,
            degrees=8.0, translate=0.06, scale=0.20, fliplr=0.50,
            mosaic=0.65, close_mosaic=CLOSE_MOSAIC_EPOCHS,
        ),
        "mosaic_mixup_cutmix": with_no_aug(
            mosaic=0.65, mixup=0.10, cutmix=0.10, close_mosaic=CLOSE_MOSAIC_EPOCHS,
        ),
        "balanced_combo": with_no_aug(
            hsv_h=0.012, hsv_s=0.40, hsv_v=0.30,
            degrees=7.0, translate=0.06, scale=0.18,
            shear=1.0, perspective=0.0003, fliplr=0.45,
            mosaic=0.50, mixup=0.05, cutmix=0.05, close_mosaic=CLOSE_MOSAIC_EPOCHS,
        ),
    }


    def resolve_augmentation(aug_key: str, aug_name: str):
        '''증강 id/이름을 학습 인자로 바꿉니다.

        반환값이 None 이면 "Ultralytics 기본 증강을 그대로 쓴다"는 뜻입니다.
        '''
        if aug_key == "none":
            return dict(NO_AUG)

        if aug_key == "yolo_default":
            return None

        # 실험 이름은 'yolo_mosaic' 처럼 접두사가 붙어 있습니다.
        candidate = str(aug_name)
        for prefix in ("yolo_", "opencv_"):
            if candidate.startswith(prefix):
                candidate = candidate[len(prefix):]
                break

        if candidate in AUG_LIBRARY:
            return dict(AUG_LIBRARY[candidate])

        raise KeyError(
            f"증강 '{aug_key}' / '{aug_name}' 에 해당하는 설정을 AUG_LIBRARY 에서 "
            "찾지 못했습니다. OpenCV 계열(C**)을 고른 경우라면 05번처럼 정적 데이터셋을 "
            "먼저 만들어야 하므로, MANUAL_OVERRIDE_AUG_KEY 로 YOLO 계열을 지정하세요."
        )


    FINAL_AUG_CONFIG = resolve_augmentation(FINAL_AUG_KEY, FINAL_AUG_NAME)

    print(f"최종 증강 설정 ({FINAL_AUG_KEY} / {FINAL_AUG_NAME})")

    if FINAL_AUG_CONFIG is None:
        print("  Ultralytics 기본 증강 사용")
        print(f"  close_mosaic 만 {CLOSE_MOSAIC_EPOCHS} 로 지정합니다.")
    else:
        for key, value in FINAL_AUG_CONFIG.items():
            if value not in (0.0, 0, [], None):
                print(f"  {key:<15} {value}")

    # --- [셀 24] --------------------------------------------------------
    DECISION = {
        "생성시각": time.strftime("%Y-%m-%d %H:%M:%S"),
        "취합한_노트북": sorted(pooled_df["source_label"].unique().tolist()),
        "빠진_결과": missing_sources,
        "증강": {
            "key": FINAL_AUG_KEY,
            "name": FINAL_AUG_NAME,
            "선택이유": aug_decision_reason,
            "학습인자": FINAL_AUG_CONFIG,
        },
        "하이퍼파라미터": {
            "label": FINAL_HP_LABEL,
            "선택이유": hp_decision_reason,
            "params": FINAL_HP_PARAMS,
        },
        "학습": {
            "model": MODEL_NAME,
            "epochs": EPOCHS,
            "imgsz": IMGSZ,
            "batch": BATCH,
            "close_mosaic": CLOSE_MOSAIC_EPOCHS,
            "seed": SEED,
        },
        "데이터": {
            "path": str(PROCESSED_DIR),
            "train_images": len(train_images),
            "val_images": len(val_images),
            "이미지_GB": round(DATASET_GB, 2),
            "클래스수": NUM_CLASSES,
        },
        "신문지_증강제외": {
            "적용": EXCLUDE_NEWSPAPER_FROM_AUG,
            "class_id": NEWSPAPER_CLASS_ID,
            "match": NEWSPAPER_MATCH_RULE,
            "mix_partner_제외": FILTER_NEWSPAPER_FROM_MIX_PARTNERS,
        },
    }

    DECISION_JSON = DECISION_DIR / "final_decision.json"
    DECISION_JSON.write_text(
        json.dumps(DECISION, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    print("확정 내용을 저장했습니다:", DECISION_JSON)
    print(json.dumps(DECISION, ensure_ascii=False, indent=2))

    # ==========================================================================
    # 7. 신문지만 증강에서 제외하기
    # --------------------------------------------------------------------------
    #
    # `selective_aug.py` 의 `SelectiveAugTrainer` 를 `model.train(trainer=...)` 에
    # 넘기면, **train split 의 dataset 만** 교체되어 신문지 이미지가 증강 없이
    # 나갑니다. validation 은 원래부터 증강을 하지 않으므로 그대로입니다.
    #
    # 동작 방식은 두 겹입니다.
    #
    # 1. 신문지 이미지는 `__getitem__` 에서 증강 파이프라인 대신 letterbox 만 거칩니다.
    # 2. mosaic/mixup/cutmix 가 **다른 이미지를 끌어올 때**도 신문지를 뽑지 않습니다.
    #    (이게 없으면 신문지가 다른 이미지의 mosaic 조각으로 들어가 결국 변형됩니다.)
    # ==========================================================================

    # --- [셀 26] --------------------------------------------------------
    # selective_aug.py 는 이 노트북과 같은 폴더에 있습니다.
    NOTEBOOK_DIR = PROJECT_ROOT

    if str(NOTEBOOK_DIR) not in sys.path:
        sys.path.insert(0, str(NOTEBOOK_DIR))

    import selective_aug

    # 커널을 살린 채 selective_aug.py 를 고쳤다면 아래 두 줄로 다시 읽습니다.
    import importlib
    selective_aug = importlib.reload(selective_aug)

    if EXCLUDE_NEWSPAPER_FROM_AUG:
        applied_config = selective_aug.configure(
            class_ids=[NEWSPAPER_CLASS_ID],
            match=NEWSPAPER_MATCH_RULE,
            filter_mix_partners=FILTER_NEWSPAPER_FROM_MIX_PARTNERS,
        )
        TRAINER_CLASS = selective_aug.SelectiveAugTrainer
        print("신문지 증강 제외 설정:", applied_config)
        print("Trainer:", TRAINER_CLASS.__name__)

    else:
        TRAINER_CLASS = None
        print("신문지 증강 제외를 끄고 기본 Trainer 로 학습합니다.")

    # ==========================================================================
    # 7-1. 정말 제외되는지 확인
    # --------------------------------------------------------------------------
    #
    # 학습을 시작하기 전에 **실제 데이터셋을 만들어** 확인합니다.
    #
    # - 신문지 이미지는 같은 index 를 두 번 읽어도 결과가 **완전히 동일**해야 합니다.
    #   (증강이 걸리면 매번 달라집니다.)
    # - 일반 이미지는 두 번 읽으면 **달라야** 합니다. (증강이 살아 있다는 뜻)
    # ==========================================================================

    # --- [셀 28] --------------------------------------------------------
    VERIFY_NEWSPAPER_EXCLUSION = True

    if VERIFY_NEWSPAPER_EXCLUSION and EXCLUDE_NEWSPAPER_FROM_AUG:
        from ultralytics.cfg import get_cfg
        from ultralytics.utils import DEFAULT_CFG

        # 학습 때와 같은 증강 설정으로 확인해야 의미가 있습니다.
        verify_overrides = {"task": "detect", "imgsz": IMGSZ}

        if FINAL_AUG_CONFIG is None:
            verify_overrides["close_mosaic"] = CLOSE_MOSAIC_EPOCHS
        else:
            verify_overrides.update({
                key: value for key, value in FINAL_AUG_CONFIG.items()
                if key in DEFAULT_CFG_DICT
            })

        verify_hyp = get_cfg(DEFAULT_CFG, overrides=verify_overrides)

        verify_dataset = selective_aug.SelectiveAugYOLODataset(
            img_path=str(TRAIN_IMAGE_DIR),
            imgsz=IMGSZ,
            batch_size=BATCH,
            augment=True,
            hyp=verify_hyp,
            rect=False,
            cache=None,
            single_cls=False,
            stride=32,
            pad=0.0,
            prefix="verify: ",
            task="detect",
            classes=None,
            data={"names": CLASS_NAMES, "nc": NUM_CLASSES, "channels": 3},
            fraction=1.0,
        )

        excluded = sorted(verify_dataset.no_aug_indices)

        print(f"전체 train {len(verify_dataset):,}장 중 증강 제외 {len(excluded):,}장")
        print("교체된 transform:", verify_dataset.filtered_transform_names or "(mosaic 계열 없음)")

        if not excluded:
            print()
            print("[경고] 증강 제외 대상이 0장입니다. NEWSPAPER_CLASS_ID 를 확인하세요.")

        else:
            # 제외된 것이 전부 신문지인지
            wrong = [
                index for index in excluded
                if set(int(value) for value in verify_dataset.labels[index]["cls"].reshape(-1))
                != {NEWSPAPER_CLASS_ID}
            ]
            print("제외 대상 중 신문지가 아닌 것:", len(wrong))
            assert not wrong, wrong[:5]

            # 신문지: 두 번 읽어도 동일해야 함
            news_index = excluded[0]
            first = verify_dataset[news_index]["img"]
            second = verify_dataset[news_index]["img"]
            news_identical = bool(torch.equal(first, second))

            # 일반 이미지: 두 번 읽으면 달라야 함 (증강이 살아 있음)
            normal_index = next(
                index for index in range(len(verify_dataset))
                if index not in verify_dataset.no_aug_indices
            )
            changed = sum(
                0 if torch.equal(verify_dataset[normal_index]["img"],
                                 verify_dataset[normal_index]["img"]) else 1
                for _ in range(3)
            )

            print()
            print(f"신문지 idx={news_index}: 2회 호출 결과 동일? {news_identical}  (True 여야 정상)")
            print(f"일반   idx={normal_index}: 3회 비교 중 {changed}회 상이  (1 이상이어야 정상)")

            if FILTER_NEWSPAPER_FROM_MIX_PARTNERS:
                def find_transform(node, name, seen=None):
                    seen = seen if seen is not None else set()
                    if node is None or id(node) in seen:
                        return None
                    seen.add(id(node))
                    if type(node).__name__ == name:
                        return node
                    for child in getattr(node, "transforms", []) or []:
                        found = find_transform(child, name, seen)
                        if found is not None:
                            return found
                    return find_transform(getattr(node, "pre_transform", None), name, seen)

                mosaic = find_transform(verify_dataset.transforms, "FilteredMosaic")

                if mosaic is not None:
                    picked = [index for _ in range(300) for index in mosaic.get_indexes()]
                    leaked = [index for index in picked if index in verify_dataset.no_aug_indices]
                    print(f"mosaic 상대 {len(picked)}회 추첨 중 신문지 {len(leaked)}회 "
                          f"(0이어야 정상)")
                else:
                    print("mosaic 을 쓰지 않는 설정이라 상대 추첨 검사는 건너뜁니다.")

            assert news_identical, "신문지에 증강이 걸리고 있습니다."
            print()
            print("확인 완료: 신문지만 증강에서 빠집니다.")

        del verify_dataset
        gc.collect()

    else:
        print("검증을 건너뜁니다.")

    # ==========================================================================
    # 8. 최종 학습 (20 epoch)
    # --------------------------------------------------------------------------
    #
    # 확정된 하이퍼파라미터 + 증강으로 한 번만 학습합니다.
    #
    # `aug` 를 넘기지 않는 경우(`yolo_default`)에도 `close_mosaic` 은 명시적으로
    # 지정합니다. 그러지 않으면 Ultralytics 기본값 10 이 적용되어 20 epoch 중 절반
    # 동안 mosaic 이 꺼집니다.
    # ==========================================================================

    # --- [셀 30] --------------------------------------------------------
    def supported_train_args(config: dict | None):
        '''현재 Ultralytics 버전이 아는 key만 남깁니다.'''
        if config is None:
            return {}, []

        if not DEFAULT_CFG_DICT:
            return dict(config), []

        supported = set(DEFAULT_CFG_DICT.keys())
        unknown = sorted(set(config.keys()) - supported)
        filtered = {key: value for key, value in config.items() if key in supported}

        return filtered, unknown


    def extract_metrics(metrics):
        box = metrics.box

        precision = float(getattr(box, "mp", np.nan))
        recall = float(getattr(box, "mr", np.nan))

        if np.isfinite(precision) and np.isfinite(recall) and (precision + recall) > 0:
            f1 = 2 * precision * recall / (precision + recall)
        else:
            f1 = np.nan

        speed = getattr(metrics, "speed", {}) or {}

        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "mAP50": float(box.map50),
            "mAP75": float(box.map75),
            "mAP50_95": float(box.map),
            "inference_ms_per_image": speed.get("inference", np.nan),
        }


    def save_per_class_metrics(metrics, run_name):
        maps = np.asarray(metrics.box.maps, dtype=float)

        per_class = pd.DataFrame({
            "class_id": range(len(maps)),
            "class_name": [CLASS_NAMES.get(index, f"class_{index}") for index in range(len(maps))],
            "mAP50_95": maps,
        })

        per_class = per_class.merge(
            support_df[["class_name", "train_images"]], on="class_name", how="left"
        )

        path = PER_CLASS_DIR / f"{run_name}.csv"
        per_class.to_csv(path, index=False, encoding="utf-8-sig")
        return path, per_class

    # --- [셀 31] --------------------------------------------------------
    # 신문지 증강 여부를 run 이름에 넣습니다.
    # 이게 없으면 exist_ok=True 때문에 이전 학습 결과(weights/results.csv/그래프)를
    # 그대로 덮어써 비교가 불가능해집니다.
    NEWSPAPER_TAG = "newsNoAug" if EXCLUDE_NEWSPAPER_FROM_AUG else "newsAug"
    RUN_NAME = f"final_{FINAL_AUG_KEY}_{FINAL_HP_LABEL}_seed{SEED}_e{EPOCHS}_{NEWSPAPER_TAG}"

    # 요약 CSV 도 run 별로 남겨 두 실험을 나란히 비교할 수 있게 합니다.
    RESULTS_CSV = SUMMARY_DIR / f"final_result_{RUN_NAME}.csv"

    train_kwargs = {
        "data": str(RUNTIME_DATA_YAML),
        "epochs": EPOCHS,
        "imgsz": IMGSZ,
        "batch": BATCH,
        "patience": PATIENCE,
        "device": DEVICE,
        "workers": WORKERS,
        "seed": SEED,
        "deterministic": True,
        # aug 를 안 넘겨도 기본값 10 이 적용되지 않도록 먼저 깔아 둡니다.
        "close_mosaic": CLOSE_MOSAIC_EPOCHS,
        "optimizer": "auto",
        "amp": True,
        "cache": False,
        "project": str(RUNS_DIR),
        "name": RUN_NAME,
        "exist_ok": True,
        "plots": True,
        "verbose": True,
    }

    # 확정된 하이퍼파라미터 (auto 면 비어 있어 위의 optimizer='auto' 가 그대로 쓰입니다)
    if FINAL_HP_PARAMS:
        train_kwargs.update(FINAL_HP_PARAMS)

    filtered_aug, unknown_aug = supported_train_args(FINAL_AUG_CONFIG)

    if FINAL_AUG_CONFIG is not None:
        train_kwargs.update(filtered_aug)

    if unknown_aug:
        print("이 버전에서 지원하지 않아 제외한 인자:", unknown_aug)

    print("run 이름:", RUN_NAME)
    print()
    print("학습 인자")
    for key, value in train_kwargs.items():
        print(f"  {key:<15} {value}")

    # ==========================================================================
    # 8-1. 예상 학습 시간
    # --------------------------------------------------------------------------
    #
    # 05/06번의 **실측 속도**로 어림합니다. 데이터가 크게 늘었다면 시간도 그만큼
    # 늘어나므로, 시작하기 전에 감당 가능한지 확인하세요.
    #
    # 너무 길다면 `EPOCHS` 를 줄이거나, `SMOKE_TEST = True` 로 배선만 먼저 점검하세요.
    # ==========================================================================

    # --- [셀 33] --------------------------------------------------------
    # 05/06번을 돌릴 당시의 train 이미지 수입니다.
    # (지금 data/processed 를 최종본으로 교체했다면 그 폴더를 세어도 옛 수치가
    #  나오지 않으므로, 기준값을 여기에 직접 적어 둡니다.)
    REFERENCE_TRAIN_IMAGES = 7623

    speed_reference = pooled_df[
        pooled_df["train_minutes"].notna() & pooled_df["actual_epochs"].notna()
    ].copy()

    if len(speed_reference):
        speed_reference["minutes_per_epoch"] = (
            speed_reference["train_minutes"] / speed_reference["actual_epochs"]
        )

        # 노트북마다 데이터 규모가 같았으므로 중앙값이면 충분합니다.
        minutes_per_epoch = float(speed_reference["minutes_per_epoch"].median())
        scale = len(train_images) / max(REFERENCE_TRAIN_IMAGES, 1)

        estimated_minutes = minutes_per_epoch * scale * EPOCHS

        print(f"기준 속도      : {minutes_per_epoch:.2f} 분/epoch "
              f"(train {REFERENCE_TRAIN_IMAGES:,}장 기준, n={len(speed_reference)})")
        print(f"데이터 배수    : {scale:.1f}배 ({len(train_images):,}장)")
        print(f"예상 소요 시간 : {estimated_minutes / 60:.1f}시간 ({EPOCHS} epoch)")
        print()
        print("※ 어림값입니다. 이미지 해상도, 디스크 속도, early stopping 에 따라 달라집니다.")
        print(f"※ patience={PATIENCE} 이므로 성능이 멈추면 더 일찍 끝날 수 있습니다.")

    else:
        print("속도를 어림할 실측값이 없습니다.")

    # --- [셀 34] --------------------------------------------------------
    if _ARGS.dry_run:
        print()
        print("--dry-run 이므로 학습을 시작하지 않고 종료합니다.")
        print("여기까지 정상이면 설정과 배선에 문제가 없습니다.")
        return

    if RUN_TRAINING:
        gc.collect()
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        model = YOLO(MODEL_NAME)

        start_time = time.perf_counter()

        # TRAINER_CLASS 가 None 이면 Ultralytics 기본 Trainer 가 쓰입니다.
        train_result = model.train(trainer=TRAINER_CLASS, **train_kwargs)

        TRAIN_MINUTES = (time.perf_counter() - start_time) / 60.0

        save_dir = Path(
            getattr(train_result, "save_dir", None) or model.trainer.save_dir
        )
        BEST_PT = save_dir / "weights" / "best.pt"

        if not BEST_PT.exists():
            raise FileNotFoundError(BEST_PT)

        print()
        print(f"학습 완료: {TRAIN_MINUTES:.1f}분")
        print("best.pt :", BEST_PT)

    else:
        save_dir = RUNS_DIR / RUN_NAME
        BEST_PT = save_dir / "weights" / "best.pt"
        TRAIN_MINUTES = np.nan
        print("RUN_TRAINING=False — 기존 결과를 씁니다:", BEST_PT)

    # ==========================================================================
    # 9. 평가와 리포트
    # --------------------------------------------------------------------------
    # ==========================================================================

    # --- [셀 36] --------------------------------------------------------
    best_model = YOLO(str(BEST_PT))

    val_metrics = best_model.val(
        data=str(RUNTIME_DATA_YAML),
        split="val",
        imgsz=IMGSZ,
        batch=BATCH,
        device=DEVICE,
        workers=WORKERS,
        plots=True,
        verbose=False,
    )

    per_class_path, per_class_df = save_per_class_metrics(val_metrics, RUN_NAME)

    history_csv = save_dir / "results.csv"
    actual_epochs = len(pd.read_csv(history_csv)) if history_csv.exists() else np.nan

    final_row = {
        "run_name": RUN_NAME,
        "aug_key": FINAL_AUG_KEY,
        "aug_name": FINAL_AUG_NAME,
        "hp_label": FINAL_HP_LABEL,
        "hp_params": json.dumps(FINAL_HP_PARAMS, ensure_ascii=False),
        "newspaper_excluded": EXCLUDE_NEWSPAPER_FROM_AUG,
        "requested_epochs": EPOCHS,
        "actual_epochs": actual_epochs,
        "close_mosaic": CLOSE_MOSAIC_EPOCHS,
        "train_minutes": TRAIN_MINUTES,
        "train_images": len(train_images),
        "val_images": len(val_images),
        "best_pt": str(BEST_PT),
        "save_dir": str(save_dir),
        "per_class_csv": str(per_class_path),
        **extract_metrics(val_metrics),
    }

    final_df = pd.DataFrame([final_row])
    final_df.to_csv(RESULTS_CSV, index=False, encoding="utf-8-sig")

    display(final_df.T)

    # ==========================================================================
    # 9-1. 클래스별 성능 — 신문지가 어떻게 나왔는지 확인
    # --------------------------------------------------------------------------
    # ==========================================================================

    # --- [셀 38] --------------------------------------------------------
    set_korean_font()

    ordered = per_class_df.sort_values("mAP50_95")

    figure, axis = plt.subplots(figsize=(11, 7))
    colors = [
        "tab:orange" if class_id == NEWSPAPER_CLASS_ID else "tab:blue"
        for class_id in ordered["class_id"]
    ]

    axis.barh(ordered["class_name"], ordered["mAP50_95"], color=colors)
    axis.axvline(float(val_metrics.box.map), color="red", linestyle="--", linewidth=1,
                 label=f"전체 mAP50-95 {val_metrics.box.map:.4f}")
    axis.set_xlabel("mAP50-95")
    axis.set_title(f"클래스별 성능 — {RUN_NAME}\n(주황: 증강에서 제외한 신문지)")
    axis.legend()

    for y_position, value in enumerate(ordered["mAP50_95"]):
        axis.text(value, y_position, f" {value:.3f}", va="center", fontsize=8)

    plt.tight_layout()
    plt.savefig(SUMMARY_DIR / "per_class.png", dpi=150, bbox_inches="tight")
    plt.close()

    display(ordered[["class_id", "class_name", "train_images", "mAP50_95"]])

    # ==========================================================================
    # 9-2. 배포용 가중치 복사
    # --------------------------------------------------------------------------
    #
    # vision 서비스는 `weights/best.pt` 를 읽습니다
    # (`vision/core/config.py` 의 기본값). 아래 셀은 기존 파일을 백업한 뒤 교체합니다.
    #
    # **주의**: 이 모델은 17개 재활용 클래스만 학습했습니다. COCO 80클래스는 인식하지
    # 않습니다.
    # ==========================================================================

    # --- [셀 40] --------------------------------------------------------
    # 1차 학습 모델(0.8638)이 이미 배포되어 있습니다.
    # 두 결과를 비교한 뒤 수동으로 배포하기 위해 자동 배포를 끕니다.
    #   비교:  ai/models/yolo/07_final_training/report/summary/final_result_*.csv
    #   배포:  uv run --no-sync python ai/notebooks/07_finalize.py --deploy
    DEPLOY_WEIGHTS = False

    FINAL_COPY = FINAL_DIR / f"best_{RUN_NAME}.pt"
    shutil.copy2(BEST_PT, FINAL_COPY)
    print("리포트용 사본:", FINAL_COPY)

    if DEPLOY_WEIGHTS:
        deploy_target = (PROJECT_ROOT / "../../weights/best.pt").resolve()
        deploy_target.parent.mkdir(parents=True, exist_ok=True)

        if deploy_target.exists():
            backup = deploy_target.with_suffix(
                f".pt.backup_{time.strftime('%Y%m%d_%H%M%S')}"
            )
            shutil.copy2(deploy_target, backup)
            print("기존 가중치 백업:", backup)

        shutil.copy2(BEST_PT, deploy_target)
        print("배포 완료:", deploy_target)
        print(f"  mAP50-95 = {val_metrics.box.map:.4f} / 클래스 {NUM_CLASSES}개")

    else:
        print("DEPLOY_WEIGHTS=False — weights/best.pt 는 그대로 둡니다.")

    # ==========================================================================
    # 10. 정리
    # --------------------------------------------------------------------------
    #
    # | 항목 | 값 |
    # | --- | --- |
    # | 확정 근거 | `report/decision/final_decision.json` |
    # | 증강 효과 집계 | `report/decision/augmentation_effect.csv` |
    # | 하이퍼파라미터 효과 집계 | `report/decision/hyperparameter_effect.csv` |
    # | 최종 성능 | `report/summary/final_result.csv` |
    # | 클래스별 성능 | `report/per_class/` |
    # | 학습 산출물 | `runs/` 아래 run 이름 폴더 |
    # | 배포 가중치 | `weights/best.pt` |
    #
    # ## 06-2를 나중에 돌렸다면
    #
    # 06번을 `DATA_IS_ONLY_CLEAN = False` 로 한 번 더 돌린 뒤 **6단계만 다시 실행**하면
    # 집계에 자동으로 포함됩니다. 확정 결과가 바뀌면 8단계부터 다시 돌리세요.
    # ==========================================================================


if __name__ == "__main__":
    import time as _time

    _log_handle = None
    if _ARGS.log:
        _log_handle = open(_ARGS.log, "a", encoding="utf-8")
        sys.stdout = _Tee(sys.stdout, _log_handle)
        sys.stderr = _Tee(sys.stderr, _log_handle)
        print(f"로그 파일: {_ARGS.log}")

    _started = _time.time()
    print("=" * 78)
    print("07. 최종 학습 시작:", _time.strftime("%Y-%m-%d %H:%M:%S"))
    print("=" * 78)

    try:
        main()
    finally:
        _elapsed = (_time.time() - _started) / 3600
        print()
        print("=" * 78)
        print(f"종료: {_time.strftime('%Y-%m-%d %H:%M:%S')}  (총 {_elapsed:.2f}시간)")
        print("=" * 78)

        if _log_handle is not None:
            _log_handle.flush()
            _log_handle.close()
