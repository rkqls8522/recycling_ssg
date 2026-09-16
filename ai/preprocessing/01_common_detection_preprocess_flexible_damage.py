# -*- coding: utf-8 -*-
"""
recycling_ssg 공통 Object Detection 전처리 스크립트
- 입력: data/train100val/Training, data/train100val/Validation, data/train100val/data.yaml
- 출력: data/processed/
- USE_DAMAGED_DATA=False: 원형(clean) 데이터만 전처리, 클래스별 최대 100장
- USE_DAMAGED_DATA=True: clean+damaged 합계 클래스별 100장 목표
- damaged 사용 시 clean 80 + damaged 20을 우선 목표로 하고 부족분은 서로 보충
- damaged는 일부/상당/완전파손에서 가능한 한 균등 샘플링
- bbox clip 기준은 MAX_BBOX_CLIP_RATIO 변수로 조절
- SHA-1은 manifests/image_manifest.csv 에 관리
- EXPORT_FORMATS = ['YOLO', 'COCO'] 구조
- canonical_id 기반 클래스 매핑
"""

# # recycling_ssg 공통 Object Detection 전처리
# 
# 이 노트북은 **YOLO + Faster R-CNN 공통 전처리**용입니다.
# 
# ## 입력
# - `data/train100val/Training/`
# - `data/train100val/Validation/`
# - `data/train100val/data.yaml`
# 
# ## 출력
# - `data/processed/images/train`, `data/processed/images/val`
# - `data/processed/labels/train`, `data/processed/labels/val` (YOLO)
# - `data/processed/coco/instances_train.json`, `instances_val.json` (COCO/Faster R-CNN)
# - `data/processed/annotations/class_mapping.json`
# - `data/processed/annotations/common_annotations.json`
# - `data/processed/manifests/image_manifest.csv`
# - `data/processed/manifests/sampling_summary.csv`
# - `data/processed/manifests/sampling_shortage.csv`
# - `data/processed/data.yaml`
# 
# ## 현재 Training 샘플링 정책
# - `USE_DAMAGED_DATA=False`: clean만 사용, 클래스당 최대 100장
# - `USE_DAMAGED_DATA=True`: clean + damaged 합계 클래스당 100장 목표
# - 파손 포함 시 우선 목표는 clean 80 + damaged 20
# - damaged가 20장보다 부족하면 남는 자리를 clean으로 보충
# - clean이 80장보다 부족하면 남는 자리를 damaged로 보충
# - damaged는 `일부파손 / 상당파손 / 완전파손`에서 최대한 균등하게 선택
# - clean+damaged 전체 후보가 100장 미만이면 가능한 데이터만 사용하고 shortage 보고서에 기록
# - bbox가 이미지 밖으로 나간 비율이 `MAX_BBOX_CLIP_RATIO` 미만일 때만 clip 후 사용
# - 서로 다른 클래스가 한 이미지에 존재하면 이미지 전체 제외
# - SHA-1으로 exact duplicate / Train-Val leakage 검사
# - 이미지는 resize/re-encoding 없이 그대로 복사
# 
# `EXPORT_FORMATS = ["YOLO", "COCO"]` 구조이므로 향후 RetinaNet, SSD 등도 exporter 또는 Dataset loader만 추가하는 방식으로 확장할 수 있습니다.

from __future__ import annotations

import hashlib
import json
import random
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np
import pandas as pd
import yaml

# ## 0. 사용자 설정

# bbox가 이미지 밖으로 나간 비율이 이 값보다 '작을 때만' clip 후 사용합니다.
# 예: 0.10 -> 10% 미만만 허용, 10% 이상이면 해당 이미지 전체 제외
MAX_BBOX_CLIP_RATIO = 0.10

# 한 클래스당 Training 목표 이미지 수입니다.
TRAIN_IMAGES_PER_CLASS = 100

# ------------------------------------------------------------
# 핵심 스위치
# False: 원형(clean) 데이터만 스캔/전처리합니다.
# True : 원형 + 파손 데이터를 함께 스캔/전처리합니다.
# ------------------------------------------------------------
USE_DAMAGED_DATA = False

# 파손 데이터를 함께 사용할 때의 '선호 목표'입니다.
# 우선 clean 80 + damaged 20을 맞추고, 한쪽이 부족하면 다른 쪽이 보충합니다.
PREFERRED_DAMAGE_IMAGES_PER_CLASS = 20

# 파손 데이터는 아래 3단계에서 최대한 균등하게 뽑습니다.
DAMAGE_VARIANTS = [
    "damaged/일부파손",
    "damaged/상당파손",
    "damaged/완전파손",
]

CLEAN_VARIANT = "clean"

# 현재는 YOLO와 COCO를 동시에 export.
# 향후 새 exporter를 등록한 뒤 여기에 이름만 추가하면 됩니다.
EXPORT_FORMATS = ["YOLO", "COCO"]

# 같은 후보 집합에서 매번 같은 이미지가 선택되도록 고정합니다.
RANDOM_SEED = 42

# Train/Validation에 SHA-1이 완전히 같은 이미지가 있으면 Validation 쪽을 제외합니다.
# "drop_val" 또는 "error"
CROSS_SPLIT_DUPLICATE_POLICY = "drop_val"

# 같은 split 내부의 exact duplicate(SHA-1 동일)는 1장만 후보로 남깁니다.
DROP_WITHIN_SPLIT_DUPLICATES = True

# 한 이미지 안에 서로 다른 86개 클래스가 2개 이상 존재하면 이미지 전체를 제외합니다.
DROP_MULTI_CLASS_IMAGES = True

# 같은 클래스 bbox가 여러 개 있어도 유지합니다.
# 다만 그중 하나라도 bbox 품질검사를 통과하지 못하면 이미지 전체를 제외합니다.
DROP_IMAGE_IF_ANY_INVALID_BBOX = True

# True이면 clean(+damaged)을 합쳐서도 100장을 못 채우는 클래스가 하나라도 있으면 오류를 냅니다.
# 현재 데이터처럼 일부 클래스 자체가 100장 미만일 수 있으므로 기본값은 False입니다.
# False이면 가능한 만큼 생성하고 manifests/sampling_shortage.csv에 부족분을 기록합니다.
STRICT_TRAIN_QUOTA = False

# 기존 processed 결과를 지우고 새로 생성할지 여부
OVERWRITE_OUTPUT = True

# ## 1. 프로젝트 경로

# 이 파일은 recycling_ssg/ai/preprocessing/ 아래에 위치합니다.
# 따라서 parents[2]가 프로젝트 루트(recycling_ssg)입니다.
PROJECT_ROOT = Path(__file__).resolve().parents[2]

# 실제 프로젝트 구조 기준 입력 경로
SOURCE_ROOT = PROJECT_ROOT / "data" / "train100val"
TRAIN_ROOT = SOURCE_ROOT / "Training"
VAL_ROOT = SOURCE_ROOT / "Validation"
SOURCE_DATA_YAML = SOURCE_ROOT / "data.yaml"

# 출력은 data/processed 아래에 생성
OUTPUT_ROOT = PROJECT_ROOT / "data" / "processed"
IMAGES_OUT = OUTPUT_ROOT / "images"
ANNOTATIONS_OUT = OUTPUT_ROOT / "annotations"
MANIFESTS_OUT = OUTPUT_ROOT / "manifests"
COCO_OUT = OUTPUT_ROOT / "coco"
YOLO_LABELS_OUT = OUTPUT_ROOT / "labels"
YOLO_DATA_YAML = OUTPUT_ROOT / "data.yaml"

# 실행 직후 실제 사용 경로 확인
print("=" * 70)
print("[PATH CHECK]")
print("PROJECT_ROOT     :", PROJECT_ROOT)
print("SOURCE_ROOT      :", SOURCE_ROOT)
print("TRAIN_ROOT       :", TRAIN_ROOT)
print("VAL_ROOT         :", VAL_ROOT)
print("SOURCE_DATA_YAML :", SOURCE_DATA_YAML)
print("OUTPUT_ROOT      :", OUTPUT_ROOT)
print("=" * 70)

required_paths = {
    "Training": TRAIN_ROOT,
    "Validation": VAL_ROOT,
    "data.yaml": SOURCE_DATA_YAML,
}
missing = [f"{name}: {path}" for name, path in required_paths.items() if not path.exists()]
if missing:
    raise FileNotFoundError(
        "필수 입력 경로를 찾지 못했습니다.\n"
        + "\n".join(missing)
        + "\n\n현재 프로젝트 구조 기준 입력 폴더는 "
          "recycling_ssg/data/train100val 입니다."
    )

# ## 2. 86개 canonical class 정의

# ============================================================
# 2. 86개 canonical class 정의
#    data/train100val/data.yaml을 단일 기준(source of truth)으로 사용
# ============================================================

def load_canonical_classes(data_yaml_path: Path) -> list[str]:
    if not data_yaml_path.exists():
        raise FileNotFoundError(f"기존 data.yaml을 찾지 못했습니다: {data_yaml_path}")

    with data_yaml_path.open("r", encoding="utf-8-sig") as f:
        payload = yaml.safe_load(f)

    names = payload.get("names")
    if names is None:
        raise ValueError("data.yaml에 names가 없습니다.")

    if isinstance(names, list):
        class_names = [str(x).strip() for x in names]
    elif isinstance(names, dict):
        normalized = {int(k): str(v).strip() for k, v in names.items()}
        expected_ids = list(range(len(normalized)))
        if sorted(normalized) != expected_ids:
            raise ValueError(
                "data.yaml의 class id가 0부터 연속적이지 않습니다: "
                f"{sorted(normalized)[:10]} ..."
            )
        class_names = [normalized[i] for i in expected_ids]
    else:
        raise TypeError("data.yaml names는 list 또는 dict여야 합니다.")

    if len(class_names) != 86:
        raise ValueError(f"클래스 수가 86개가 아닙니다: {len(class_names)}")
    if len(set(class_names)) != 86:
        raise ValueError("data.yaml names에 중복 클래스명이 있습니다.")

    return class_names


CLASS_NAMES = load_canonical_classes(SOURCE_DATA_YAML)
CLASS_TO_CANONICAL_ID = {name: idx for idx, name in enumerate(CLASS_NAMES)}
CANONICAL_ID_TO_CLASS = {idx: name for idx, name in enumerate(CLASS_NAMES)}

# 원본 폴더/JSON의 대분류 표기 차이만 정규화합니다.
# 소분류는 절대 병합하지 않습니다.
MAJOR_NAME_NORMALIZATION = {
    "나무류": "나무",
    "비닐류": "비닐",
    "스티로폼류": "스티로폼",
    "유리병류": "유리병",
    "페트병류": "페트병",
    "종이": "종이류",
    "캔": "캔류",
    "플라스틱": "플라스틱류",
}


def normalize_major(name: str) -> str:
    name = str(name).strip()
    return MAJOR_NAME_NORMALIZATION.get(name, name)


def make_class_name(major: str, detail: str) -> str:
    return f"{normalize_major(major)}/{str(detail).strip()}"


CLASS_MAPPING = {
    "schema_version": "1.0",
    "num_classes": 86,
    "canonical_id_range": [0, 85],
    "id_policy": {
        "canonical": "0..85",
        "yolo": "canonical_id",
        "coco_category_id": "canonical_id + 1",
        "torchvision_faster_rcnn": "0=background, object label=canonical_id+1",
    },
    "classes": [
        {
            "canonical_id": canonical_id,
            "class_name": class_name,
            "major_category": class_name.split("/", 1)[0],
            "minor_category": class_name.split("/", 1)[1],
            "yolo_id": canonical_id,
            "coco_category_id": canonical_id + 1,
            "torchvision_id": canonical_id + 1,
        }
        for canonical_id, class_name in enumerate(CLASS_NAMES)
    ],
}

# ## 3. 공통 유틸리티

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def sha1_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def read_image_unicode(path: Path):
    data = np.fromfile(str(path), dtype=np.uint8)
    if data.size == 0:
        return None
    return cv2.imdecode(data, cv2.IMREAD_COLOR)


def load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8-sig") as f:
        return json.load(f)


def get_first(mapping: dict, keys: tuple[str, ...], default=None):
    for key in keys:
        if key in mapping:
            return mapping[key]
    return default


def point_xy(point):
    if isinstance(point, dict):
        x = get_first(point, ("x", "X"))
        y = get_first(point, ("y", "Y"))
        if x is None or y is None:
            raise ValueError("polygon_point_missing_xy")
        return float(x), float(y)

    if isinstance(point, (list, tuple)) and len(point) >= 2:
        return float(point[0]), float(point[1])

    raise ValueError("unsupported_polygon_point")


def polygon_points_to_xyxy(points):
    xy = [point_xy(p) for p in points]
    if len(xy) < 2:
        raise ValueError("polygon_too_few_points")
    xs = [p[0] for p in xy]
    ys = [p[1] for p in xy]
    return min(xs), min(ys), max(xs), max(ys)


def bounding_to_xyxy(bounding: dict):
    x1 = get_first(bounding, ("x1", "X1"))
    y1 = get_first(bounding, ("y1", "Y1"))
    x2 = get_first(bounding, ("x2", "X2"))
    y2 = get_first(bounding, ("y2", "Y2"))

    if None not in (x1, y1, x2, y2):
        return float(x1), float(y1), float(x2), float(y2), "BOX"

    points = get_first(bounding, ("PolygonPoint", "POLYGONPOINT", "polygonPoint"))
    if points:
        px1, py1, px2, py2 = polygon_points_to_xyxy(points)
        return px1, py1, px2, py2, "POLYGON->BOX"

    raise ValueError("bbox_coordinates_missing")


def clip_bbox_if_allowed(x1, y1, x2, y2, width, height):
    """
    원 bbox 면적 중 이미지 밖으로 잘려나가는 비율을 계산합니다.

    사용 조건:
      clip_ratio < MAX_BBOX_CLIP_RATIO

    예: MAX_BBOX_CLIP_RATIO=0.10이면
      9.9%  -> clip 후 사용
      10.0% -> 제외
      15.0% -> 제외

    요청에 따라 clip 여부/원본 bbox/최종 bbox/clip_ratio 자체는
    결과 metadata에 저장하지 않습니다.
    """
    x1, y1, x2, y2 = map(float, (x1, y1, x2, y2))

    if x2 <= x1 or y2 <= y1:
        raise ValueError("invalid_bbox_non_positive_original_size")

    original_area = (x2 - x1) * (y2 - y1)

    cx1 = float(np.clip(x1, 0, width))
    cy1 = float(np.clip(y1, 0, height))
    cx2 = float(np.clip(x2, 0, width))
    cy2 = float(np.clip(y2, 0, height))

    if cx2 <= cx1 or cy2 <= cy1:
        raise ValueError("bbox_outside_image")

    clipped_area = (cx2 - cx1) * (cy2 - cy1)
    clip_ratio = max(0.0, 1.0 - clipped_area / original_area)

    if clip_ratio >= MAX_BBOX_CLIP_RATIO:
        raise ValueError("bbox_clip_ratio_exceeds_threshold")

    return cx1, cy1, cx2, cy2


def xyxy_to_yolo(x1, y1, x2, y2, width, height):
    xc = ((x1 + x2) / 2.0) / width
    yc = ((y1 + y2) / 2.0) / height
    bw = (x2 - x1) / width
    bh = (y2 - y1) / height
    return xc, yc, bw, bh


def xyxy_to_coco(x1, y1, x2, y2):
    return [x1, y1, x2 - x1, y2 - y1]

# ## 4. Training / Validation 데이터 소스 검색

def discover_label_image_pairs(base_dir: Path):
    """
    base_dir 아래에서
      *_라벨링데이터
      *_원천데이터
    폴더 쌍을 자동 탐색합니다.
    """
    pairs = []
    label_dirs = sorted(
        p for p in base_dir.rglob("*")
        if p.is_dir() and p.name.endswith("_라벨링데이터")
    )

    for label_dir in label_dirs:
        prefix = label_dir.name[: -len("_라벨링데이터")]
        image_dir = label_dir.parent / f"{prefix}_원천데이터"
        if image_dir.exists():
            pairs.append((label_dir, image_dir))

    return pairs


def build_source_pairs() -> list[dict]:
    pairs: list[dict] = []

    # 원형 전용 모드에서는 damaged 폴더를 아예 읽지 않습니다.
    train_variants = [CLEAN_VARIANT]
    if USE_DAMAGED_DATA:
        train_variants.extend(DAMAGE_VARIANTS)

    for variant in train_variants:
        variant_root = TRAIN_ROOT / Path(variant)
        if not variant_root.exists():
            raise FileNotFoundError(f"Training variant가 없습니다: {variant_root}")

        discovered = discover_label_image_pairs(variant_root)
        if not discovered:
            raise FileNotFoundError(
                f"라벨링/원천 데이터 폴더 쌍을 찾지 못했습니다: {variant_root}"
            )

        for label_dir, image_dir in discovered:
            pairs.append({
                "split": "train",
                "variant": variant,
                "label_dir": label_dir,
                "image_dir": image_dir,
            })

    val_pairs = discover_label_image_pairs(VAL_ROOT)
    if not val_pairs:
        raise FileNotFoundError(
            f"Validation 라벨링/원천 데이터 폴더 쌍을 찾지 못했습니다: {VAL_ROOT}"
        )

    for label_dir, image_dir in val_pairs:
        pairs.append({
            "split": "val",
            "variant": "validation",
            "label_dir": label_dir,
            "image_dir": image_dir,
        })

    return pairs


def relative_stem_key(path: Path, root: Path) -> str:
    return path.relative_to(root).with_suffix("").as_posix().casefold()


def build_image_index(image_root: Path):
    index = {}
    collisions = defaultdict(list)

    for path in image_root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue

        key = relative_stem_key(path, image_root)
        if key in index:
            collisions[key].append(path)
        else:
            index[key] = path

    if collisions:
        examples = list(collisions.items())[:10]
        raise ValueError(f"동일 상대경로 stem 이미지 충돌: {examples}")

    return index


def build_sample_table(source_pairs: list[dict]) -> tuple[pd.DataFrame, list[dict]]:
    sample_rows = []
    pairing_issues = []

    for pair in source_pairs:
        label_dir = pair["label_dir"]
        image_dir = pair["image_dir"]
        image_index = build_image_index(image_dir)

        json_paths = sorted(
            p for p in label_dir.rglob("*")
            if p.is_file() and p.suffix.lower() == ".json"
        )

        for json_path in json_paths:
            key = relative_stem_key(json_path, label_dir)
            image_path = image_index.get(key)

            if image_path is None:
                pairing_issues.append({
                    "split": pair["split"],
                    "variant": pair["variant"],
                    "json_path": str(json_path),
                    "reason": "missing_image",
                })
                continue

            rel = json_path.relative_to(label_dir)
            if len(rel.parts) < 3:
                pairing_issues.append({
                    "split": pair["split"],
                    "variant": pair["variant"],
                    "json_path": str(json_path),
                    "reason": "path_too_short_for_class",
                })
                continue

            folder_major = normalize_major(rel.parts[0])
            folder_detail = str(rel.parts[1]).strip()
            folder_class_name = f"{folder_major}/{folder_detail}"

            sample_rows.append({
                "split": pair["split"],
                "variant": pair["variant"],
                "json_path": json_path,
                "image_path": image_path,
                "folder_class_name": folder_class_name,
            })

    return pd.DataFrame(sample_rows), pairing_issues

# ## 5. 공통 annotation 품질 검사

def extract_bounds(payload: dict) -> list[dict]:
    bounds = get_first(payload, ("Bounding", "bounding", "BOUNDING"), default=[])
    return bounds or []


def bounding_class_name(bounding: dict) -> str:
    major = get_first(bounding, ("CLASS", "Class", "class"), default="UNKNOWN")
    detail = get_first(bounding, ("DETAILS", "Details", "details"), default="UNKNOWN")
    return make_class_name(major, detail)


def preprocess_candidates(samples_df: pd.DataFrame):
    manifest_rows: list[dict] = []
    accepted_records: list[dict] = []

    for row in samples_df.itertuples(index=False):
        image_path = Path(row.image_path)
        json_path = Path(row.json_path)

        manifest = {
            "split": row.split,
            "variant": row.variant,
            "source_image": str(image_path),
            "source_json": str(json_path),
            "output_image": "",
            "sha1": "",
            "width": None,
            "height": None,
            "class_name": "",
            "canonical_id": None,
            "object_count": 0,
            "is_within_split_duplicate": False,
            "is_cross_split_duplicate": False,
            "status": "excluded",
            "exclude_reason": "",
        }

        try:
            manifest["sha1"] = sha1_file(image_path)

            image = read_image_unicode(image_path)
            if image is None:
                raise ValueError("decode_failed")

            height, width = image.shape[:2]
            manifest["width"] = int(width)
            manifest["height"] = int(height)

            payload = load_json(json_path)
            bounds = extract_bounds(payload)
            if not bounds:
                raise ValueError("no_bounding_annotations")

            annotation_class_names = [bounding_class_name(b) for b in bounds]
            unique_classes = sorted(set(annotation_class_names))

            if DROP_MULTI_CLASS_IMAGES and len(unique_classes) != 1:
                raise ValueError("multiple_different_classes")

            if len(unique_classes) == 0:
                raise ValueError("no_annotation_class")

            class_name = unique_classes[0]
            manifest["class_name"] = class_name

            if class_name not in CLASS_TO_CANONICAL_ID:
                raise ValueError("unknown_class")

            if class_name != row.folder_class_name:
                raise ValueError("folder_json_class_mismatch")

            canonical_id = CLASS_TO_CANONICAL_ID[class_name]
            manifest["canonical_id"] = canonical_id

            final_boxes = []
            bbox_errors = []

            for object_index, bounding in enumerate(bounds):
                try:
                    # 안전하게 객체별 class도 다시 확인
                    object_class_name = bounding_class_name(bounding)
                    if object_class_name != class_name:
                        raise ValueError("object_class_mismatch")

                    x1, y1, x2, y2, source_geometry = bounding_to_xyxy(bounding)
                    x1, y1, x2, y2 = clip_bbox_if_allowed(
                        x1, y1, x2, y2,
                        width=width,
                        height=height,
                    )

                    final_boxes.append({
                        "object_index": object_index,
                        "canonical_id": canonical_id,
                        "class_name": class_name,
                        "bbox_xyxy": [x1, y1, x2, y2],
                        "source_geometry": source_geometry,
                    })

                except Exception as e:
                    bbox_errors.append(str(e))

            if bbox_errors and DROP_IMAGE_IF_ANY_INVALID_BBOX:
                raise ValueError("invalid_bbox")

            if not final_boxes:
                raise ValueError("no_valid_bbox_after_preprocessing")

            manifest["object_count"] = len(final_boxes)
            manifest["status"] = "candidate"

            accepted_records.append({
                "split": row.split,
                "variant": row.variant,
                "source_image": image_path,
                "source_json": json_path,
                "sha1": manifest["sha1"],
                "width": int(width),
                "height": int(height),
                "class_name": class_name,
                "canonical_id": canonical_id,
                "annotations": final_boxes,
            })

        except Exception as e:
            manifest["status"] = "excluded"
            manifest["exclude_reason"] = str(e)

        manifest_rows.append(manifest)

    return accepted_records, pd.DataFrame(manifest_rows)

# ## 6. SHA-1 exact duplicate 검사

def apply_sha1_duplicate_policy(records: list[dict], manifest_df: pd.DataFrame):
    records = list(records)

    # 6-1. 같은 split 내부 exact duplicate 제거
    if DROP_WITHIN_SPLIT_DUPLICATES:
        candidate_mask = manifest_df["status"].eq("candidate")
        candidate_df = manifest_df[candidate_mask].copy()

        duplicated_groups = (
            candidate_df.groupby(["split", "sha1"], dropna=False)
            .size()
            .loc[lambda s: s > 1]
        )

        for (split, sha1), _count in duplicated_groups.items():
            group = manifest_df[
                manifest_df["split"].eq(split)
                & manifest_df["sha1"].eq(sha1)
                & manifest_df["status"].eq("candidate")
            ].sort_values(["variant", "source_image"])

            # 첫 번째 1장만 남기고 나머지는 제외
            drop_indices = list(group.index[1:])
            if drop_indices:
                manifest_df.loc[group.index, "is_within_split_duplicate"] = True
                manifest_df.loc[drop_indices, "status"] = "excluded"
                manifest_df.loc[drop_indices, "exclude_reason"] = "within_split_exact_duplicate"

    # 6-2. Train-Val exact duplicate 검사
    candidate_df = manifest_df[manifest_df["status"].eq("candidate")].copy()
    sha_splits = candidate_df.groupby("sha1")["split"].agg(lambda s: sorted(set(s)))

    cross_split_sha1 = {
        sha for sha, splits in sha_splits.items()
        if set(splits) == {"train", "val"}
    }

    if cross_split_sha1:
        manifest_df.loc[
            manifest_df["sha1"].isin(cross_split_sha1),
            "is_cross_split_duplicate",
        ] = True

        if CROSS_SPLIT_DUPLICATE_POLICY == "error":
            raise ValueError(
                f"Train/Validation exact duplicate가 발견되었습니다: {len(cross_split_sha1)} SHA-1 groups"
            )

        if CROSS_SPLIT_DUPLICATE_POLICY == "drop_val":
            mask = (
                manifest_df["sha1"].isin(cross_split_sha1)
                & manifest_df["split"].eq("val")
                & manifest_df["status"].eq("candidate")
            )
            manifest_df.loc[mask, "status"] = "excluded"
            manifest_df.loc[mask, "exclude_reason"] = "cross_split_exact_duplicate_drop_val"
        else:
            raise ValueError(
                f"지원하지 않는 CROSS_SPLIT_DUPLICATE_POLICY: {CROSS_SPLIT_DUPLICATE_POLICY}"
            )

    status_lookup = {
        (row.source_image, row.sha1): row.status
        for row in manifest_df.itertuples(index=False)
    }

    records = [
        r for r in records
        if status_lookup.get((str(r["source_image"]), r["sha1"])) == "candidate"
    ]

    return records, manifest_df

# ## 7. 클래스별 Training 샘플링

# ============================================================
# 7. 클래스별 Training 샘플링
#
# USE_DAMAGED_DATA=False
#   - clean만 사용
#   - 클래스별 최대 TRAIN_IMAGES_PER_CLASS장
#
# USE_DAMAGED_DATA=True
#   - clean + damaged 합계 TRAIN_IMAGES_PER_CLASS장 목표
#   - 우선 clean 80 + damaged 20 목표
#   - damaged 부족 -> clean으로 보충
#   - clean 부족   -> damaged로 보충
#   - damaged는 일부/상당/완전파손에서 최대한 균등 선택
# ============================================================

def deterministic_sample(records: list[dict], n: int, seed: int) -> list[dict]:
    if n <= 0:
        return []
    items = sorted(records, key=lambda r: str(r["source_image"]))
    rng = random.Random(seed)
    if n >= len(items):
        return items.copy()
    return rng.sample(items, n)


def balanced_damage_sample(
    damage_pools: dict[str, list[dict]],
    n: int,
    canonical_id: int,
    seed: int,
) -> list[dict]:
    """
    일부/상당/완전파손에서 가능한 한 균등하게 n장을 선택합니다.

    모든 variant에 데이터가 충분하면 n=20일 때 7/7/6 형태가 됩니다.
    특정 variant가 부족하면 남은 variant들이 최대한 균등하게 보충합니다.
    """
    if n <= 0:
        return []

    # variant마다 독립적으로 deterministic shuffle
    shuffled: dict[str, list[dict]] = {}
    for i, variant in enumerate(DAMAGE_VARIANTS):
        items = sorted(damage_pools.get(variant, []), key=lambda r: str(r["source_image"]))
        rng = random.Random(seed + i * 1009)
        items = items.copy()
        rng.shuffle(items)
        shuffled[variant] = items

    selected: list[dict] = []
    selected_counts = {variant: 0 for variant in DAMAGE_VARIANTS}
    positions = {variant: 0 for variant in DAMAGE_VARIANTS}

    # 동률일 때 항상 같은 단계만 우선되지 않도록 클래스마다 시작 순서를 회전
    start = canonical_id % len(DAMAGE_VARIANTS)
    rotated = DAMAGE_VARIANTS[start:] + DAMAGE_VARIANTS[:start]
    tie_rank = {variant: i for i, variant in enumerate(rotated)}

    while len(selected) < n:
        available_variants = [
            variant
            for variant in DAMAGE_VARIANTS
            if positions[variant] < len(shuffled[variant])
        ]
        if not available_variants:
            break

        # 현재까지 덜 뽑힌 파손 단계부터 선택
        variant = min(
            available_variants,
            key=lambda v: (selected_counts[v], tie_rank[v]),
        )
        selected.append(shuffled[variant][positions[variant]])
        positions[variant] += 1
        selected_counts[variant] += 1

    return selected


def select_balanced_training_records(
    records: list[dict],
    manifest_df: pd.DataFrame,
):
    train_records = [r for r in records if r["split"] == "train"]
    val_records = [r for r in records if r["split"] == "val"]

    selected_train: list[dict] = []
    shortage_rows: list[dict] = []
    summary_rows: list[dict] = []

    # candidate train은 일단 quota 미선택 상태로 표시
    train_candidate_mask = (
        manifest_df["split"].eq("train")
        & manifest_df["status"].eq("candidate")
    )
    manifest_df.loc[train_candidate_mask, "status"] = "not_selected_by_quota"
    manifest_df.loc[train_candidate_mask, "exclude_reason"] = ""

    preferred_damage = PREFERRED_DAMAGE_IMAGES_PER_CLASS if USE_DAMAGED_DATA else 0
    preferred_clean = TRAIN_IMAGES_PER_CLASS - preferred_damage

    for canonical_id, class_name in enumerate(CLASS_NAMES):
        class_records = [r for r in train_records if r["canonical_id"] == canonical_id]
        clean_pool = [r for r in class_records if r["variant"] == CLEAN_VARIANT]

        if USE_DAMAGED_DATA:
            damage_pools = {
                variant: [r for r in class_records if r["variant"] == variant]
                for variant in DAMAGE_VARIANTS
            }
        else:
            damage_pools = {variant: [] for variant in DAMAGE_VARIANTS}

        clean_available = len(clean_pool)
        damage_available = sum(len(pool) for pool in damage_pools.values())
        class_seed = RANDOM_SEED + canonical_id * 10007

        if not USE_DAMAGED_DATA:
            # ------------------------------------------------
            # 원형 전용: damaged는 아예 사용하지 않음
            # ------------------------------------------------
            clean_count = min(TRAIN_IMAGES_PER_CLASS, clean_available)
            damage_count = 0
        else:
            # ------------------------------------------------
            # 파손 포함: 80 clean + 20 damaged를 우선 목표로 함
            # ------------------------------------------------
            clean_count = min(preferred_clean, clean_available)
            damage_count = min(preferred_damage, damage_available)

            remaining = TRAIN_IMAGES_PER_CLASS - clean_count - damage_count

            # damaged가 부족한 경우 clean의 80장 초과 여유분으로 먼저 보충
            if remaining > 0:
                clean_extra_capacity = clean_available - clean_count
                add_clean = min(remaining, clean_extra_capacity)
                clean_count += add_clean
                remaining -= add_clean

            # clean이 부족한 경우 damaged의 20장 초과 여유분으로 보충
            if remaining > 0:
                damage_extra_capacity = damage_available - damage_count
                add_damage = min(remaining, damage_extra_capacity)
                damage_count += add_damage
                remaining -= add_damage

        selected_clean = deterministic_sample(
            clean_pool,
            clean_count,
            class_seed + 1,
        )
        selected_damage = balanced_damage_sample(
            damage_pools,
            damage_count,
            canonical_id,
            class_seed + 100,
        ) if USE_DAMAGED_DATA else []

        selected_class = selected_clean + selected_damage
        selected_train.extend(selected_class)

        # 총 100장을 못 채운 경우에만 실제 shortage로 기록
        total_shortage = TRAIN_IMAGES_PER_CLASS - len(selected_class)
        if total_shortage > 0:
            shortage_rows.append({
                "canonical_id": canonical_id,
                "class_name": class_name,
                "mode": "clean_plus_damaged" if USE_DAMAGED_DATA else "clean_only",
                "required_total": TRAIN_IMAGES_PER_CLASS,
                "available_total": clean_available + damage_available,
                "selected_total": len(selected_class),
                "shortage": total_shortage,
            })

        actual_damage_counts = Counter(r["variant"] for r in selected_damage)
        summary_rows.append({
            "canonical_id": canonical_id,
            "class_name": class_name,
            "use_damaged_data": USE_DAMAGED_DATA,
            "target_total": TRAIN_IMAGES_PER_CLASS,
            "preferred_clean": preferred_clean,
            "preferred_damaged": preferred_damage,
            "clean_available": clean_available,
            "clean_selected": len(selected_clean),
            "damage_available_total": damage_available,
            "damage_selected_total": len(selected_damage),
            "damaged_일부파손": actual_damage_counts.get("damaged/일부파손", 0),
            "damaged_상당파손": actual_damage_counts.get("damaged/상당파손", 0),
            "damaged_완전파손": actual_damage_counts.get("damaged/완전파손", 0),
            "train_selected_total": len(selected_class),
            "target_met": len(selected_class) == TRAIN_IMAGES_PER_CLASS,
        })

    # 선택된 train만 selected 상태로 변경
    selected_keys = {
        (str(r["source_image"]), r["sha1"])
        for r in selected_train
    }

    for idx, row in manifest_df.iterrows():
        if row["split"] != "train":
            continue
        key = (row["source_image"], row["sha1"])
        if key in selected_keys:
            manifest_df.at[idx, "status"] = "selected"
            manifest_df.at[idx, "exclude_reason"] = ""

    # Validation은 quota 없이 품질검사를 통과한 전체 candidate를 사용
    val_candidate_mask = (
        manifest_df["split"].eq("val")
        & manifest_df["status"].eq("candidate")
    )
    manifest_df.loc[val_candidate_mask, "status"] = "selected"

    sampling_summary_df = pd.DataFrame(summary_rows)
    shortage_df = pd.DataFrame(shortage_rows)

    if STRICT_TRAIN_QUOTA and not shortage_df.empty:
        print("\n[ERROR] 아래 클래스는 clean(+damaged)을 합쳐도 100장을 충족하지 못합니다.")
        print(shortage_df.to_string(index=False))
        raise ValueError(
            "STRICT_TRAIN_QUOTA=True인데 일부 클래스가 클래스당 100장 quota를 충족하지 못했습니다."
        )

    if not shortage_df.empty:
        print("\n[WARN] 아래 클래스는 전체 사용 가능한 데이터가 부족해 100장을 채우지 못했습니다.")
        print(shortage_df.to_string(index=False))

    final_records = selected_train + val_records
    return final_records, manifest_df, sampling_summary_df, shortage_df

# ## 8. 출력 파일 준비 및 이미지 복사

def prepare_output_dirs():
    """
    data/processed 자체를 통째로 삭제하지 않습니다.
    OVERWRITE_OUTPUT=True일 때 이 전처리 코드가 생성하는 하위 결과만 정리합니다.
    """
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)

    generated_dirs = [
        IMAGES_OUT,
        ANNOTATIONS_OUT,
        MANIFESTS_OUT,
        COCO_OUT,
        YOLO_LABELS_OUT,
    ]
    generated_files = [YOLO_DATA_YAML]

    if OVERWRITE_OUTPUT:
        for path in generated_dirs:
            if path.exists():
                shutil.rmtree(path)
        for path in generated_files:
            if path.exists():
                path.unlink()

    for path in [
        IMAGES_OUT / "train",
        IMAGES_OUT / "val",
        ANNOTATIONS_OUT,
        MANIFESTS_OUT,
    ]:
        path.mkdir(parents=True, exist_ok=True)


def assign_output_images(records: list[dict], manifest_df: pd.DataFrame):
    basename_counts = Counter(Path(r["source_image"]).name for r in records)

    def output_image_name(record) -> str:
        source = Path(record["source_image"])
        basename = source.name
        if basename_counts[basename] == 1:
            return basename

        short_hash = hashlib.sha1(str(source).encode("utf-8")).hexdigest()[:10]
        return f"{short_hash}__{basename}"

    for record in records:
        split = record["split"]
        name = output_image_name(record)
        dst = IMAGES_OUT / split / name

        # resize/re-encoding 없이 원본 파일 그대로 복사
        shutil.copy2(record["source_image"], dst)

        record["output_image"] = name
        record["output_relpath"] = f"images/{split}/{name}"

        mask = (
            manifest_df["source_image"].eq(str(record["source_image"]))
            & manifest_df["sha1"].eq(record["sha1"])
            & manifest_df["status"].eq("selected")
        )
        manifest_df.loc[mask, "output_image"] = record["output_relpath"]
        manifest_df.loc[mask, "status"] = "included"

    return records, manifest_df

# ## 9. 공통 annotation / class mapping / SHA-1 manifest 저장

def save_common_outputs(
    records: list[dict],
    manifest_df: pd.DataFrame,
    sampling_summary_df: pd.DataFrame,
    shortage_df: pd.DataFrame,
):
    class_mapping_path = ANNOTATIONS_OUT / "class_mapping.json"
    common_annotations_path = ANNOTATIONS_OUT / "common_annotations.json"
    image_manifest_path = MANIFESTS_OUT / "image_manifest.csv"
    sampling_summary_path = MANIFESTS_OUT / "sampling_summary.csv"
    shortage_path = MANIFESTS_OUT / "sampling_shortage.csv"

    with class_mapping_path.open("w", encoding="utf-8") as f:
        json.dump(CLASS_MAPPING, f, ensure_ascii=False, indent=2)

    common_payload = {
        "schema_version": "1.0",
        "bbox_format": "xyxy_absolute_pixels",
        "num_classes": 86,
        "train_sampling": {
            "images_per_class_target": TRAIN_IMAGES_PER_CLASS,
            "use_damaged_data": USE_DAMAGED_DATA,
            "preferred_clean_per_class": (
                TRAIN_IMAGES_PER_CLASS - PREFERRED_DAMAGE_IMAGES_PER_CLASS
                if USE_DAMAGED_DATA else TRAIN_IMAGES_PER_CLASS
            ),
            "preferred_damaged_per_class": (
                PREFERRED_DAMAGE_IMAGES_PER_CLASS if USE_DAMAGED_DATA else 0
            ),
            "fallback_policy": (
                "clean<->damaged mutual top-up to total target"
                if USE_DAMAGED_DATA else "clean only"
            ),
            "damage_variants": DAMAGE_VARIANTS if USE_DAMAGED_DATA else [],
            "random_seed": RANDOM_SEED,
        },
        "images": [
            {
                "split": r["split"],
                "variant": r["variant"],
                "file_name": r["output_relpath"],
                "width": r["width"],
                "height": r["height"],
                "sha1": r["sha1"],
                "class_name": r["class_name"],
                "canonical_id": r["canonical_id"],
                "annotations": r["annotations"],
            }
            for r in records
        ],
    }

    with common_annotations_path.open("w", encoding="utf-8") as f:
        json.dump(common_payload, f, ensure_ascii=False, indent=2)

    # SHA-1은 image_manifest.csv 한 파일에서 전체 관리
    manifest_df = manifest_df.sort_values(
        ["split", "canonical_id", "variant", "status", "source_image"],
        na_position="last",
    ).reset_index(drop=True)
    manifest_df.to_csv(image_manifest_path, index=False, encoding="utf-8-sig")

    sampling_summary_df.to_csv(sampling_summary_path, index=False, encoding="utf-8-sig")
    shortage_df.to_csv(shortage_path, index=False, encoding="utf-8-sig")

    print(f"class_mapping.json     -> {class_mapping_path}")
    print(f"common_annotations.json -> {common_annotations_path}")
    print(f"image_manifest.csv      -> {image_manifest_path}")
    print(f"sampling_summary.csv    -> {sampling_summary_path}")

# ## 10. Exporter: YOLO

def export_yolo(records: list[dict]):
    for split in ("train", "val"):
        (YOLO_LABELS_OUT / split).mkdir(parents=True, exist_ok=True)

    for r in records:
        label_path = YOLO_LABELS_OUT / r["split"] / f"{Path(r['output_image']).stem}.txt"
        lines = []

        for ann in r["annotations"]:
            x1, y1, x2, y2 = ann["bbox_xyxy"]
            xc, yc, bw, bh = xyxy_to_yolo(
                x1, y1, x2, y2,
                width=r["width"],
                height=r["height"],
            )

            coords = np.array([xc, yc, bw, bh], dtype=float)
            if not np.all((coords >= 0) & (coords <= 1)):
                raise ValueError(f"YOLO bbox normalized range 오류: {r['source_image']}")
            if bw <= 0 or bh <= 0:
                raise ValueError(f"YOLO bbox size 오류: {r['source_image']}")

            yolo_id = ann["canonical_id"]
            lines.append(f"{yolo_id} {xc:.8f} {yc:.8f} {bw:.8f} {bh:.8f}")

        label_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    data_yaml = {
        "path": str(OUTPUT_ROOT.resolve()),
        "train": "images/train",
        "val": "images/val",
        "names": {idx: name for idx, name in enumerate(CLASS_NAMES)},
    }

    with YOLO_DATA_YAML.open("w", encoding="utf-8") as f:
        yaml.safe_dump(data_yaml, f, allow_unicode=True, sort_keys=False)

    print(f"YOLO export 완료 -> {YOLO_DATA_YAML}")

# ## 11. Exporter: COCO (Faster R-CNN / RetinaNet 등에서 활용 가능)

def export_coco(records: list[dict]):
    COCO_OUT.mkdir(parents=True, exist_ok=True)

    categories = [
        {
            "id": canonical_id + 1,
            "name": class_name,
            "supercategory": class_name.split("/", 1)[0],
        }
        for canonical_id, class_name in enumerate(CLASS_NAMES)
    ]

    for split in ("train", "val"):
        split_records = [r for r in records if r["split"] == split]
        coco_images = []
        coco_annotations = []
        annotation_id = 1

        for image_id, r in enumerate(split_records, start=1):
            coco_images.append({
                "id": image_id,
                "file_name": f"{split}/{r['output_image']}",
                "width": r["width"],
                "height": r["height"],
            })

            for ann in r["annotations"]:
                x1, y1, x2, y2 = ann["bbox_xyxy"]
                bbox = xyxy_to_coco(x1, y1, x2, y2)

                coco_annotations.append({
                    "id": annotation_id,
                    "image_id": image_id,
                    "category_id": ann["canonical_id"] + 1,
                    "bbox": bbox,
                    "area": bbox[2] * bbox[3],
                    "iscrowd": 0,
                })
                annotation_id += 1

        payload = {
            "images": coco_images,
            "annotations": coco_annotations,
            "categories": categories,
        }

        out_path = COCO_OUT / f"instances_{split}.json"
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        print(
            f"COCO {split} export 완료: "
            f"images={len(coco_images)}, annotations={len(coco_annotations)} -> {out_path}"
        )


# 새 모델/새 annotation format이 필요할 때 함수만 추가하고 여기에 등록합니다.
EXPORTERS = {
    "YOLO": export_yolo,
    "COCO": export_coco,
}

# ## 12. 최종 검증

def validate_outputs(records: list[dict], manifest_df: pd.DataFrame):
    train_records = [r for r in records if r["split"] == "train"]

    # 클래스별 Training은 100장을 초과하면 안 됩니다.
    train_counts = Counter(r["canonical_id"] for r in train_records)
    over_counts = {
        CANONICAL_ID_TO_CLASS[class_id]: train_counts.get(class_id, 0)
        for class_id in range(86)
        if train_counts.get(class_id, 0) > TRAIN_IMAGES_PER_CLASS
    }
    if over_counts:
        raise ValueError(f"Training 클래스별 100장 초과 오류: {over_counts}")

    # 원형 전용 모드에서는 damaged가 단 한 장도 포함되면 안 됩니다.
    if not USE_DAMAGED_DATA:
        damaged_in_clean_only = [
            r for r in train_records
            if r["variant"] in DAMAGE_VARIANTS
        ]
        if damaged_in_clean_only:
            raise ValueError(
                f"USE_DAMAGED_DATA=False인데 damaged 데이터가 포함되었습니다: "
                f"{len(damaged_in_clean_only)}장"
            )

    # STRICT 모드에서는 모든 클래스가 정확히 100장이어야 합니다.
    if STRICT_TRAIN_QUOTA:
        wrong_counts = {
            CANONICAL_ID_TO_CLASS[class_id]: train_counts.get(class_id, 0)
            for class_id in range(86)
            if train_counts.get(class_id, 0) != TRAIN_IMAGES_PER_CLASS
        }
        if wrong_counts:
            raise ValueError(f"Training 클래스별 100장 검증 실패: {wrong_counts}")

    # canonical id 범위
    invalid_ids = [
        r for r in records
        if r["canonical_id"] not in range(86)
    ]
    if invalid_ids:
        raise ValueError("canonical_id 범위 오류")

    # 출력 이미지 존재
    for r in records:
        path = OUTPUT_ROOT / r["output_relpath"]
        if not path.exists():
            raise FileNotFoundError(f"출력 이미지 누락: {path}")

    # YOLO image-label 1:1
    if "YOLO" in EXPORT_FORMATS:
        for split in ("train", "val"):
            image_stems = {
                p.stem for p in (IMAGES_OUT / split).glob("*") if p.is_file()
            }
            label_stems = {
                p.stem for p in (YOLO_LABELS_OUT / split).glob("*.txt")
            }
            if image_stems != label_stems:
                raise ValueError(
                    f"YOLO image/label mismatch ({split}): "
                    f"missing_labels={len(image_stems - label_stems)}, "
                    f"missing_images={len(label_stems - image_stems)}"
                )

    # COCO category id 범위
    if "COCO" in EXPORT_FORMATS:
        for split in ("train", "val"):
            path = COCO_OUT / f"instances_{split}.json"
            with path.open("r", encoding="utf-8") as f:
                coco = json.load(f)

            if len(coco["categories"]) != 86:
                raise ValueError(f"COCO category 수 오류: {split}")

            valid_ids = set(range(1, 87))
            used_ids = {ann["category_id"] for ann in coco["annotations"]}
            if not used_ids.issubset(valid_ids):
                raise ValueError(f"COCO category id 범위 오류: {split}")

    included = manifest_df[manifest_df["status"].eq("included")]
    print("\n최종 포함 이미지 수")
    print(included.groupby("split").size().to_string())
    print("\nFINAL VALIDATION: PASSED")

# ## 13. Main

def main():
    print("=" * 90)
    print("recycling_ssg common detection preprocessing")
    print("=" * 90)
    print(f"PROJECT_ROOT               : {PROJECT_ROOT}")
    print(f"SOURCE_ROOT                : {SOURCE_ROOT}")
    print(f"TRAIN_ROOT                 : {TRAIN_ROOT}")
    print(f"VAL_ROOT                   : {VAL_ROOT}")
    print(f"OUTPUT_ROOT                : {OUTPUT_ROOT}")
    print(f"MAX_BBOX_CLIP_RATIO        : {MAX_BBOX_CLIP_RATIO}")
    print(f"TRAIN_IMAGES_PER_CLASS     : {TRAIN_IMAGES_PER_CLASS}")
    print(f"USE_DAMAGED_DATA           : {USE_DAMAGED_DATA}")
    print(f"PREFERRED_CLEAN_PER_CLASS  : {TRAIN_IMAGES_PER_CLASS - PREFERRED_DAMAGE_IMAGES_PER_CLASS if USE_DAMAGED_DATA else TRAIN_IMAGES_PER_CLASS}")
    print(f"PREFERRED_DAMAGE_PER_CLASS : {PREFERRED_DAMAGE_IMAGES_PER_CLASS if USE_DAMAGED_DATA else 0}")
    print(f"DAMAGE_VARIANTS            : {DAMAGE_VARIANTS if USE_DAMAGED_DATA else []}")
    print(f"EXPORT_FORMATS             : {EXPORT_FORMATS}")
    print(f"RANDOM_SEED                : {RANDOM_SEED}")

    # 설정 검증
    if not (0 <= MAX_BBOX_CLIP_RATIO <= 1):
        raise ValueError("MAX_BBOX_CLIP_RATIO는 0~1 범위여야 합니다.")
    if PREFERRED_DAMAGE_IMAGES_PER_CLASS < 0:
        raise ValueError("PREFERRED_DAMAGE_IMAGES_PER_CLASS는 0 이상이어야 합니다.")
    if PREFERRED_DAMAGE_IMAGES_PER_CLASS > TRAIN_IMAGES_PER_CLASS:
        raise ValueError(
            "PREFERRED_DAMAGE_IMAGES_PER_CLASS가 TRAIN_IMAGES_PER_CLASS보다 클 수 없습니다."
        )

    unknown_formats = sorted(set(EXPORT_FORMATS) - set(EXPORTERS))
    if unknown_formats:
        raise ValueError(f"등록되지 않은 exporter: {unknown_formats}")

    # 1) source 탐색
    source_pairs = build_source_pairs()
    print(f"\n[1/8] source folder pairs: {len(source_pairs)}")
    print(pd.DataFrame(source_pairs)[["split", "variant", "label_dir", "image_dir"]].to_string(index=False))

    # 2) JSON-image pairing
    samples_df, pairing_issues = build_sample_table(source_pairs)
    print(f"\n[2/8] paired samples: {len(samples_df)}")
    print(f"      pairing issues: {len(pairing_issues)}")

    # 3) bbox/class/image 공통 품질검사
    records, manifest_df = preprocess_candidates(samples_df)
    print(f"\n[3/8] quality candidates: {(manifest_df['status'] == 'candidate').sum()}")
    print(f"      excluded          : {(manifest_df['status'] == 'excluded').sum()}")

    # pairing issue도 image_manifest.csv와 같은 관리 흐름에 합칩니다.
    if pairing_issues:
        pairing_manifest = pd.DataFrame([
            {
                "split": x["split"],
                "variant": x["variant"],
                "source_image": "",
                "source_json": x["json_path"],
                "output_image": "",
                "sha1": "",
                "width": None,
                "height": None,
                "class_name": "",
                "canonical_id": None,
                "object_count": 0,
                "is_within_split_duplicate": False,
                "is_cross_split_duplicate": False,
                "status": "excluded",
                "exclude_reason": x["reason"],
            }
            for x in pairing_issues
        ])
        manifest_df = pd.concat([manifest_df, pairing_manifest], ignore_index=True)

    # 4) SHA-1 duplicate 처리
    records, manifest_df = apply_sha1_duplicate_policy(records, manifest_df)
    print(f"\n[4/8] after SHA-1 duplicate policy: {len(records)} candidates")

    # 5) 설정 모드에 따른 클래스별 최대 100장 샘플링
    records, manifest_df, sampling_summary_df, shortage_df = select_balanced_training_records(
        records,
        manifest_df,
    )

    train_selected = [r for r in records if r["split"] == "train"]
    val_selected = [r for r in records if r["split"] == "val"]
    print(f"\n[5/8] selected train: {len(train_selected)}")
    print(f"      selected val  : {len(val_selected)}")
    print("\nTraining sampling summary:")
    print(sampling_summary_df.to_string(index=False))

    # 6) 출력 폴더 준비 + 이미지 원본 그대로 복사
    prepare_output_dirs()
    records, manifest_df = assign_output_images(records, manifest_df)
    print(f"\n[6/8] copied images: {len(records)}")

    # 7) 공통 metadata 저장 + exporter 실행
    save_common_outputs(records, manifest_df, sampling_summary_df, shortage_df)

    for export_format in EXPORT_FORMATS:
        print("\n" + "=" * 90)
        print(f"EXPORT: {export_format}")
        EXPORTERS[export_format](records)
    print("\n[7/8] exports completed")

    # 8) 최종 검증
    validate_outputs(records, manifest_df)
    print("\n[8/8] all done")


if __name__ == "__main__":
    main()

# ## 최종 폴더 구조
# 
# ```text
# data/
# ├─ train100val/                 # 입력 (수정하지 않음)
# │  ├─ Training/
# │  ├─ Validation/
# │  └─ data.yaml
# │
# └─ processed/                    # 출력
#    ├─ images/
#    │  ├─ train/
#    │  └─ val/
#    ├─ labels/                    # YOLO
#    │  ├─ train/
#    │  └─ val/
#    ├─ coco/
#    │  ├─ instances_train.json
#    │  └─ instances_val.json
#    ├─ annotations/
#    │  ├─ class_mapping.json
#    │  └─ common_annotations.json
#    ├─ manifests/
#    │  ├─ image_manifest.csv
#    │  ├─ sampling_summary.csv
#    │  └─ sampling_shortage.csv
#    └─ data.yaml
# ```

