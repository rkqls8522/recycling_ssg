#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""07 학습을 도중에 멈췄을 때, 남아 있는 best.pt 로 마무리만 수행한다.

07_final_training.py 를 20 epoch 다 돌리면 평가·리포트·가중치 배포까지 자동으로
끝납니다. 그런데 Ctrl+C 로 중단하면 그 뒷부분이 실행되지 않습니다.
이 스크립트는 그 뒷부분만 따로 수행합니다.

best.pt 는 Ultralytics 가 매 epoch 갱신합니다.
  - last.pt : 매 epoch 저장 (이어하기용)
  - best.pt : val mAP50-95 가 기록을 경신한 epoch 에만 저장
따라서 중간에 멈춰도 그때까지 가장 좋았던 가중치가 남아 있습니다.

사용법
    uv run --no-sync python ai/notebooks/07_finalize.py
    uv run --no-sync python ai/notebooks/07_finalize.py --deploy      # weights/best.pt 교체까지
    uv run --no-sync python ai/notebooks/07_finalize.py --weights <경로>
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.font_manager as fm
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml
from ultralytics import YOLO

PROJECT_ROOT = Path(__file__).resolve().parent
EXPERIMENT_ROOT = (PROJECT_ROOT / "../models/yolo/07_final_training").resolve()
RUNS_DIR = EXPERIMENT_ROOT / "runs"
REPORT_ROOT = EXPERIMENT_ROOT / "report"
SUMMARY_DIR = REPORT_ROOT / "summary"
PER_CLASS_DIR = REPORT_ROOT / "per_class"
FINAL_DIR = REPORT_ROOT / "final_best"

IMGSZ = 640
BATCH = 8
WORKERS = 4
NEWSPAPER_CLASS_ID = 10


def set_korean_font() -> None:
    installed = {font.name for font in fm.fontManager.ttflist}
    for name in ["Malgun Gothic", "AppleGothic", "NanumGothic", "Noto Sans CJK KR"]:
        if name in installed:
            plt.rcParams["font.family"] = name
            break
    plt.rcParams["axes.unicode_minus"] = False


def find_latest_best() -> Path:
    """가장 최근에 갱신된 best.pt 를 찾습니다."""
    candidates = sorted(
        RUNS_DIR.glob("*/weights/best.pt"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise FileNotFoundError(
            f"best.pt 를 찾지 못했습니다: {RUNS_DIR}\n"
            "07_final_training.py 를 한 번이라도 학습 단계까지 돌렸는지 확인하세요."
        )
    return candidates[0]


def epochs_done(save_dir: Path) -> int:
    """results.csv 의 줄 수가 곧 완료한 epoch 수입니다."""
    history = save_dir / "results.csv"
    if not history.exists():
        return 0
    return len(pd.read_csv(history))


def main() -> None:
    parser = argparse.ArgumentParser(description="07 학습 마무리 (평가·리포트·배포)")
    parser.add_argument("--weights", default=None, help="사용할 best.pt 경로 (기본: 가장 최근 것)")
    parser.add_argument(
        "--deploy",
        action="store_true",
        help="weights/best.pt 를 이 모델로 교체합니다 (기존 파일은 백업).",
    )
    args = parser.parse_args()

    for path in [SUMMARY_DIR, PER_CLASS_DIR, FINAL_DIR]:
        path.mkdir(parents=True, exist_ok=True)

    best_pt = Path(args.weights).resolve() if args.weights else find_latest_best()
    save_dir = best_pt.parent.parent

    runtime_yaml = SUMMARY_DIR / "runtime_processed.yaml"
    if not runtime_yaml.exists():
        raise FileNotFoundError(
            f"{runtime_yaml} 가 없습니다. 07_final_training.py 를 먼저 실행하세요."
        )

    config = yaml.safe_load(runtime_yaml.read_text(encoding="utf-8"))
    names_raw = config["names"]
    class_names = (
        {int(k): str(v) for k, v in names_raw.items()}
        if isinstance(names_raw, dict)
        else {i: str(v) for i, v in enumerate(names_raw)}
    )

    done = epochs_done(save_dir)
    print("=" * 78)
    print("07 마무리")
    print("=" * 78)
    print(f"  가중치     : {best_pt}")
    print(f"  run 폴더   : {save_dir.name}")
    print(f"  완료 epoch : {done}")
    print(f"  데이터     : {runtime_yaml}")
    print()

    model = YOLO(str(best_pt))
    metrics = model.val(
        data=str(runtime_yaml),
        split="val",
        imgsz=IMGSZ,
        batch=BATCH,
        workers=WORKERS,
        plots=True,
        verbose=False,
    )

    precision = float(getattr(metrics.box, "mp", np.nan))
    recall = float(getattr(metrics.box, "mr", np.nan))
    f1 = (
        2 * precision * recall / (precision + recall)
        if np.isfinite(precision) and np.isfinite(recall) and (precision + recall) > 0
        else np.nan
    )

    # --- 클래스별 성능 -------------------------------------------------
    maps = np.asarray(metrics.box.maps, dtype=float)
    per_class = pd.DataFrame(
        {
            "class_id": range(len(maps)),
            "class_name": [class_names.get(i, f"class_{i}") for i in range(len(maps))],
            "mAP50_95": maps,
        }
    )
    per_class_path = PER_CLASS_DIR / f"{save_dir.name}_finalize.csv"
    per_class.to_csv(per_class_path, index=False, encoding="utf-8-sig")

    set_korean_font()
    ordered = per_class.sort_values("mAP50_95")
    figure, axis = plt.subplots(figsize=(11, 7))
    colors = [
        "tab:orange" if class_id == NEWSPAPER_CLASS_ID else "tab:blue"
        for class_id in ordered["class_id"]
    ]
    axis.barh(ordered["class_name"], ordered["mAP50_95"], color=colors)
    axis.axvline(
        float(metrics.box.map),
        color="red",
        linestyle="--",
        linewidth=1,
        label=f"전체 mAP50-95 {metrics.box.map:.4f}",
    )
    axis.set_xlabel("mAP50-95")
    axis.set_title(f"클래스별 성능 — {save_dir.name} ({done} epoch)\n(주황: 증강에서 제외한 신문지)")
    axis.legend()
    for y_position, value in enumerate(ordered["mAP50_95"]):
        axis.text(value, y_position, f" {value:.3f}", va="center", fontsize=8)
    plt.tight_layout()
    figure_path = SUMMARY_DIR / "per_class_finalize.png"
    plt.savefig(figure_path, dpi=150, bbox_inches="tight")
    plt.close()

    # --- 요약 ----------------------------------------------------------
    row = {
        "run_name": save_dir.name,
        "best_pt": str(best_pt),
        "completed_epochs": done,
        "finalized_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mAP50": float(metrics.box.map50),
        "mAP75": float(metrics.box.map75),
        "mAP50_95": float(metrics.box.map),
    }
    summary_path = SUMMARY_DIR / "final_result.csv"
    pd.DataFrame([row]).to_csv(summary_path, index=False, encoding="utf-8-sig")

    print()
    print("결과")
    for key, value in row.items():
        print(f"  {key:<18} {value}")
    print()
    print("저장:", summary_path)
    print("저장:", per_class_path)
    print("저장:", figure_path)

    shutil.copy2(best_pt, FINAL_DIR / "best.pt")
    print("저장:", FINAL_DIR / "best.pt")

    # --- 배포 ----------------------------------------------------------
    if args.deploy:
        target = (PROJECT_ROOT / "../../weights/best.pt").resolve()
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            backup = target.with_suffix(f".pt.backup_{time.strftime('%Y%m%d_%H%M%S')}")
            shutil.copy2(target, backup)
            print("기존 가중치 백업:", backup)
        shutil.copy2(best_pt, target)
        print("배포 완료:", target)
        print(f"  mAP50-95 = {metrics.box.map:.4f} / 클래스 {len(class_names)}개")
    else:
        print()
        print("weights/best.pt 는 건드리지 않았습니다. 교체하려면 --deploy 를 붙이세요.")


if __name__ == "__main__":
    main()
