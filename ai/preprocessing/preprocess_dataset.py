"""
생활폐기물 객체 탐지 데이터 전처리 실행 파일

[파일 목적]
AI Hub 생활폐기물 이미지와 JSON annotation을 검사하고 표준화한 뒤,
모델 학습에 사용할 COCO 객체 탐지 형식으로 변환한다.

팀원은 DATA_DIR만 자신의 데이터 폴더 경로로 변경하여 실행할 수 있다.
원본 이미지와 원본 JSON 파일은 수정하거나 삭제하지 않는다.


[주요 처리 작업]

1. 데이터 폴더 검사
   - Training·Validation의 images·labels 폴더 존재 여부 확인
   - 하위 폴더를 포함하여 이미지와 JSON 파일 수집

2. 이미지와 JSON 연결
   - 이미지와 JSON의 상대경로 및 파일명을 기준으로 연결
   - 이미지 또는 JSON이 없는 항목 집계

3. 이미지 로딩 및 해상도 확인
   - OpenCV를 사용하여 한글 경로 이미지 로딩
   - EXIF 자동 회전을 무시하고 실제 저장 방향으로 이미지 읽기
   - 실제 이미지 너비와 높이를 Bounding Box 검증에 사용

4. Annotation 표준화
   - BOX annotation 좌표를 공통 형식으로 변환
   - POLYGON annotation을 최소 Bounding Box로 변환
   - 좌표를 x1, y1, x2, y2 형식으로 통일

5. Bounding Box 유효성 검사
   - 숫자로 변환할 수 없는 좌표 검사
   - NaN 및 무한대 좌표 검사
   - 좌표 순서와 면적 검사
   - 이미지 범위를 벗어난 Bounding Box 제외

6. 클래스 정책 적용
   - 대분류 이름을 최종 분류 체계로 통합
   - 캔류의 일부 세부 품목을 '캔'으로 통합
   - 형광등 세부 품목을 '전구'와 '형광등'으로 통합
   - '기타', '기타술병', '기타의류'는 유지
   - 원본 표기인 '포장제', '장남감'은 수정하지 않고 유지

7. 제외 정책 적용
   - 전자제품 객체 제외
   - 가구 또는 가구류 객체 제외
   - 최종 분류표에 정의되지 않은 객체 제외
   - 제외 정책은 이미지가 아닌 객체 단위로 적용
   - 정상 객체가 남아 있는 이미지는 최종 데이터에 유지

8. 클래스 ID 부여
   - 최종 세부 클래스명을 기준으로 클래스 ID 생성
   - 모델 클래스 ID를 0부터 연속적으로 부여
   - Training과 Validation에 동일한 전체 클래스 매핑 적용

9. 전처리 결과 저장
   - 최종 annotation 저장
   - 클래스 ID 매핑을 JSON과 CSV로 저장
   - 제외 객체와 제외 사유 저장
   - 표준화 오류와 처리 결과 요약 저장

10. COCO 형식 변환
    - Training과 Validation을 각각 COCO 형식으로 변환
    - Bounding Box를 [x, y, width, height] 형식으로 저장
    - 모델 class_id 0~N-1을 COCO category_id 1~N으로 변환
    - 이미지 경로는 각 images 폴더 아래의 상대경로로 저장

11. COCO 정합성 검사
    - 이미지·annotation·category ID 중복 검사
    - 존재하지 않는 이미지 및 category 참조 검사
    - Bounding Box 너비와 높이 유효성 검사
    - Training과 Validation의 categories 일치 여부 검사

12. 실행 결과 출력
    - 표준화 객체와 오류 개수 출력
    - 제외 객체의 클래스, 세부 품목, 사유와 이미지 경로 출력
    - 최종 객체·대분류·세부 클래스 수 출력
    - Training·Validation COCO 이미지 및 객체 수 출력
    - 결과 저장 폴더와 저장 파일 목록 출력


[입력 데이터 구조]

DATA_DIR/
├── Training/
│   ├── images/
│   └── labels/
└── Validation/
    ├── images/
    └── labels/


[출력 데이터 구조]

outputs/
├── preprocessed/
│   ├── final_annotations.json
│   ├── class_id_mapping.json
│   ├── class_id_mapping.csv
│   ├── excluded_objects.csv
│   ├── preprocessing_summary.json
│   └── preprocessing_errors.json
└── coco/
    ├── instances_train.json
    └── instances_val.json


[필수 패키지]
- numpy
- opencv-python


[실행 방법]

uv run python ai/preprocessing/preprocess_dataset.py


[주의사항]
- DATA_DIR은 Training과 Validation 폴더가 있는 최상위 경로로 설정한다.
- 원본 이미지와 JSON 파일은 변경하지 않는다.
- COCO JSON에는 이미지 파일이 포함되지 않으므로 학습 시 원본 이미지도 필요하다.
- final_annotations.json에는 절대경로가 포함되므로 팀 학습에는 COCO 상대경로를 우선 사용한다.
- YOLO 학습에는 별도의 YOLO annotation 형식 변환이 필요하다.
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import cv2
import numpy as np


# ============================================================
# 사용자 설정: DATA_DIR만 수정한다.
# ============================================================
DATA_DIR = Path(r"C:\Users\ran\Desktop\recycling_ssg\data2") ##### 파일경로 수정 ######

# 결과는 이 Python 파일과 같은 위치의 outputs 폴더에 저장한다.
SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "outputs"

TRAIN_IMAGE_DIR = DATA_DIR / "Training" / "images"
TRAIN_LABEL_DIR = DATA_DIR / "Training" / "labels"
VAL_IMAGE_DIR = DATA_DIR / "Validation" / "images"
VAL_LABEL_DIR = DATA_DIR / "Validation" / "labels"

PREPROCESSED_DIR = OUTPUT_DIR / "preprocessed"
COCO_DIR = OUTPUT_DIR / "coco"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


# ============================================================
# 최종 클래스 정책
# ============================================================
CLASS_NAME_MAPPING = {
    "고철류": "고철류",
    "나무": "나무",
    "나무류": "나무",
    "도기류": "도기류",
    "비닐": "비닐",
    "비닐류": "비닐",
    "스티로폼": "스티로폼",
    "스티로폼류": "스티로폼",
    "유리병": "유리병",
    "유리병류": "유리병",
    "의류": "의류",
    "종이": "종이류",
    "종이류": "종이류",
    "캔": "캔류",
    "캔류": "캔류",
    "페트병": "페트병",
    "페트병류": "페트병",
    "플라스틱": "플라스틱류",
    "플라스틱류": "플라스틱류",
    "형광등": "형광등",
}

ALLOWED_DETAILS = {
    "고철류": {"고철", "골프채", "기타", "비철금속", "전기프라이팬", "주전자", "철옷걸이", "프라이팬"},
    "나무": {"기타", "나무행거", "도마", "액자", "장식품", "주걱", "주방용품", "포장재"},
    "도기류": {"그릇류", "기타", "뚝배기", "받침", "병", "장식품", "주전자", "컵", "항아리", "화분"},
    "비닐": {"과자봉지", "기타", "리필용기", "봉투", "에어캡", "일회용덮개", "포장제"},
    "스티로폼": {"네모트레이", "보호재", "스티로폼", "포장용기"},
    "유리병": {"기타", "기타술병", "맥주병", "물병", "박카스병", "소주병", "음료수병", "주방용기"},
    "의류": {"기타", "기타의류", "레깅스", "면의류", "상의", "외투", "원피스", "하의", "합성섬유"},
    "종이류": {"기타", "노트", "상자류", "신문지", "신발상자", "음료수곽", "종이봉투", "책자", "포장상자"},
    "캔류": {"기타", "캔", "스팸류", "통조림캔"},
    "페트병": {"기타", "일회용음료수잔", "페트병"},
    "플라스틱류": {"기타", "대용량플라스틱통", "밀폐용기", "바구니", "욕실용품", "장남감"},
    "형광등": {"전구", "형광등"},
}


def to_float(value: Any) -> float | None:
    """문자열 또는 숫자를 유한한 float로 변환한다."""
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def extract_polygon_points(value: Any) -> list[tuple[float, float]]:
    """여러 PolygonPoint 표현에서 (x, y) 좌표를 재귀적으로 추출한다."""
    points: list[tuple[float, float]] = []
    if value is None:
        return points

    if isinstance(value, dict):
        lowered = {str(key).lower(): key for key in value}
        if "x" in lowered and "y" in lowered:
            xs, ys = value[lowered["x"]], value[lowered["y"]]
            if isinstance(xs, list) and isinstance(ys, list):
                for x, y in zip(xs, ys):
                    xf, yf = to_float(x), to_float(y)
                    if xf is not None and yf is not None:
                        points.append((xf, yf))
            else:
                xf, yf = to_float(xs), to_float(ys)
                if xf is not None and yf is not None:
                    points.append((xf, yf))
        else:
            for nested in value.values():
                points.extend(extract_polygon_points(nested))
        return points

    if isinstance(value, (list, tuple)):
        if (
            len(value) >= 2
            and not isinstance(value[0], (list, tuple, dict))
            and not isinstance(value[1], (list, tuple, dict))
        ):
            xf, yf = to_float(value[0]), to_float(value[1])
            if xf is not None and yf is not None:
                points.append((xf, yf))
        else:
            for nested in value:
                points.extend(extract_polygon_points(nested))
        return points

    if isinstance(value, str):
        numbers = [float(number) for number in re.findall(r"-?\d+(?:\.\d+)?", value)]
        for index in range(0, len(numbers) - 1, 2):
            points.append((numbers[index], numbers[index + 1]))
    return points


def polygon_to_bbox(value: Any) -> tuple[dict[str, float] | None, list[tuple[float, float]]]:
    """Polygon의 모든 점을 포함하는 최소 Bounding Box를 만든다."""
    points = extract_polygon_points(value)
    if len(points) < 3:
        return None, points
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return {"x1": min(xs), "y1": min(ys), "x2": max(xs), "y2": max(ys)}, points


def read_image_ignore_orientation(image_path: Path) -> np.ndarray | None:
    """한글 경로를 지원하고 EXIF 자동 회전을 무시해 이미지를 읽는다."""
    try:
        encoded = np.fromfile(str(image_path), dtype=np.uint8)
        return cv2.imdecode(encoded, cv2.IMREAD_COLOR | cv2.IMREAD_IGNORE_ORIENTATION)
    except (OSError, ValueError, cv2.error):
        return None


def collect_files(image_dir: Path, label_dir: Path) -> tuple[list[Path], list[Path]]:
    """하위 폴더를 포함하여 이미지 파일과 JSON 라벨 파일을 수집한다."""
    images = sorted(path for path in image_dir.rglob("*") if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS)
    labels = sorted(path for path in label_dir.rglob("*.json") if path.is_file())
    return images, labels


def check_required_directories() -> None:
    """Training·Validation의 images·labels 폴더가 모두 있는지 확인한다."""
    missing = [path for path in (TRAIN_IMAGE_DIR, TRAIN_LABEL_DIR, VAL_IMAGE_DIR, VAL_LABEL_DIR) if not path.is_dir()]
    if missing:
        raise FileNotFoundError("필수 데이터 폴더가 없습니다:\n" + "\n".join(f"- {path}" for path in missing))


def standardize_split(dataset: str, image_dir: Path, label_dir: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    """이미지·JSON을 연결하고 BOX와 POLYGON을 공통 BBox로 표준화한다."""
    image_files, json_files = collect_files(image_dir, label_dir)
    image_keys = {path.relative_to(image_dir).with_suffix("") for path in image_files}
    json_keys = {path.relative_to(label_dir).with_suffix("") for path in json_files}
    images_without_json = image_keys - json_keys
    json_without_images = json_keys - image_keys

    standardized: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    counts = {"images": len(image_files), "json": len(json_files), "box": 0, "polygon": 0}

    for position, image_path in enumerate(image_files, start=1):
        if position == 1 or position % 500 == 0 or position == len(image_files):
            print(f"[{dataset}] 처리 진행: {position:,}/{len(image_files):,}")

        relative_path = image_path.relative_to(image_dir)
        json_path = (label_dir / relative_path).with_suffix(".json")
        if not json_path.exists():
            continue

        image = read_image_ignore_orientation(image_path)
        if image is None:
            errors.append({"dataset": dataset, "image_path": str(image_path), "reason": "이미지를 읽을 수 없음"})
            continue
        image_height, image_width = image.shape[:2]

        try:
            with json_path.open("r", encoding="utf-8-sig") as file:
                label_data = json.load(file)
        except (OSError, json.JSONDecodeError, UnicodeError) as error:
            errors.append({"dataset": dataset, "json_path": str(json_path), "reason": f"JSON 읽기 오류: {error}"})
            continue

        bounding_objects = label_data.get("Bounding", [])
        if not isinstance(bounding_objects, list):
            errors.append({"dataset": dataset, "json_path": str(json_path), "reason": "Bounding이 list가 아님"})
            continue

        for object_index, obj in enumerate(bounding_objects):
            drawing = str(obj.get("Drawing", "")).strip().upper()
            polygon_points = None
            if drawing == "BOX":
                counts["box"] += 1
                bbox = {name: to_float(obj.get(name)) for name in ("x1", "y1", "x2", "y2")}
                if any(value is None for value in bbox.values()):
                    errors.append({"dataset": dataset, "json_path": str(json_path), "object_index": object_index, "reason": "BOX 좌표 변환 실패"})
                    continue
            elif drawing == "POLYGON":
                counts["polygon"] += 1
                bbox, polygon_points = polygon_to_bbox(obj.get("PolygonPoint"))
                if bbox is None:
                    errors.append({"dataset": dataset, "json_path": str(json_path), "object_index": object_index, "reason": "Polygon 변환 실패"})
                    continue
            else:
                errors.append({"dataset": dataset, "json_path": str(json_path), "object_index": object_index, "reason": f"알 수 없는 Drawing: {drawing}"})
                continue

            x1, y1, x2, y2 = (float(bbox[key]) for key in ("x1", "y1", "x2", "y2"))
            if not (0 <= x1 < x2 <= image_width and 0 <= y1 < y2 <= image_height):
                errors.append({"dataset": dataset, "json_path": str(json_path), "object_index": object_index, "reason": "이미지 범위 밖 또는 면적 0 BBox", "bbox": [x1, y1, x2, y2], "image_size": [image_width, image_height]})
                continue

            bbox_width, bbox_height = x2 - x1, y2 - y1
            standardized.append({
                "dataset": dataset,
                "image_path": str(image_path.resolve()),
                "json_path": str(json_path.resolve()),
                "file_name": image_path.name,
                "relative_path": relative_path.as_posix(),
                "object_index": object_index,
                "image_width": image_width,
                "image_height": image_height,
                "class_name": obj.get("CLASS"),
                "details": obj.get("DETAILS"),
                "damage": obj.get("DAMAGE"),
                "direction": obj.get("Direction"),
                "object_size_label": obj.get("Object Size"),
                "day_night": label_data.get("DAY/NIGHT"),
                "place": label_data.get("PLACE"),
                "original_drawing_type": drawing,
                "polygon_points": polygon_points,
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "bbox_width": bbox_width,
                "bbox_height": bbox_height,
                "bbox_area": bbox_width * bbox_height,
                "bbox_area_ratio": (bbox_width * bbox_height) / (image_width * image_height),
            })

    counts["images_without_json"] = len(images_without_json)
    counts["json_without_images"] = len(json_without_images)
    return standardized, errors, counts


def map_detail(class_name: str, details: str) -> str:
    """캔류와 형광등의 여러 세부 품목을 최종 세부 클래스로 통합한다."""
    if class_name == "캔류" and details in {"맥주캔", "음료수캔", "참기름캔", "커피캔", "캔"}:
        return "캔"
    if class_name == "형광등":
        if details in {"LED전구", "백열전구", "전구"}:
            return "전구"
        if details in {"안정기내장형", "직관형", "콤팩트형", "환형", "기타", "형광등"}:
            return "형광등"
    return details


def apply_class_policy(annotations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """전자제품·가구를 제외하고 합의된 최종 클래스 정책을 적용한다."""
    included, excluded = [], []
    for item in annotations:
        original_class = str(item.get("class_name", "")).strip()
        original_details = str(item.get("details", "")).strip()
        if original_class == "전자제품":
            excluded.append({**item, "reason": "전자제품 제외"})
            continue
        if original_class in {"가구", "가구류"} or original_details in {"가구", "가구류"}:
            excluded.append({**item, "reason": "가구·가구류 제외"})
            continue
        final_class = CLASS_NAME_MAPPING.get(original_class)
        if final_class is None:
            excluded.append({**item, "reason": f"정의되지 않은 대분류: {original_class}"})
            continue
        final_details = map_detail(final_class, original_details)
        if final_details not in ALLOWED_DETAILS[final_class]:
            excluded.append({**item, "reason": f"정의되지 않은 세부 품목: {original_class}_{original_details}"})
            continue

        result = deepcopy(item)
        result["original_class_name"] = original_class
        result["original_details"] = original_details
        result["class_name"] = final_class
        result["details"] = final_details
        result["detail_class_name"] = f"{final_class}_{final_details}"
        included.append(result)
    return included, excluded


def assign_class_ids(annotations: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """최종 세부 클래스명을 정렬한 뒤 0부터 연속된 모델 클래스 ID를 부여한다."""
    class_names = sorted({item["detail_class_name"] for item in annotations})
    mapping = {name: index for index, name in enumerate(class_names)}
    results = []
    for item in annotations:
        result = deepcopy(item)
        result["class_id"] = mapping[result["detail_class_name"]]
        results.append(result)
    records = [{"class_id": class_id, "class_name": name.split("_", 1)[0], "details": name.split("_", 1)[1], "detail_class_name": name} for name, class_id in mapping.items()]
    return results, sorted(records, key=lambda record: record["class_id"])


def save_json(data: Any, path: Path) -> None:
    """처리 중 파일 손상을 줄이기 위해 임시 파일을 거쳐 JSON을 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as file:
        json.dump(data, file, ensure_ascii=False, indent=2)
    temporary.replace(path)


def save_csv(records: list[dict[str, Any]], path: Path, fieldnames: list[str]) -> None:
    """Excel에서도 한글이 깨지지 않도록 UTF-8 BOM 형식으로 CSV를 저장한다."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)


def convert_to_coco(annotations: list[dict[str, Any]], class_records: list[dict[str, Any]], dataset: str) -> dict[str, Any]:
    """표준화된 객체 정보를 COCO 객체 탐지 형식으로 변환한다."""
    split_items = [item for item in annotations if item["dataset"].lower() == dataset.lower()]
    by_image: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in split_items:
        by_image[item["image_path"]].append(item)
    image_paths = sorted(by_image, key=lambda path: by_image[path][0]["relative_path"])
    image_ids = {path: index for index, path in enumerate(image_paths, start=1)}

    images = []
    coco_annotations = []
    for image_path in image_paths:
        first = by_image[image_path][0]
        images.append({"id": image_ids[image_path], "file_name": first["relative_path"], "width": int(first["image_width"]), "height": int(first["image_height"])})
        for item in by_image[image_path]:
            width, height = item["x2"] - item["x1"], item["y2"] - item["y1"]
            coco_annotations.append({
                "id": len(coco_annotations) + 1,
                "image_id": image_ids[image_path],
                "category_id": int(item["class_id"]) + 1,
                "bbox": [item["x1"], item["y1"], width, height],
                "area": width * height,
                "iscrowd": 0,
                "segmentation": [],
            })

    categories = [{"id": int(record["class_id"]) + 1, "name": record["detail_class_name"], "supercategory": record["class_name"], "model_class_id": int(record["class_id"])} for record in class_records]
    return {
        "info": {"description": f"Recycling Waste Detection - {dataset}", "version": "1.0", "created_at": datetime.now().isoformat(timespec="seconds")},
        "licenses": [],
        "images": images,
        "annotations": coco_annotations,
        "categories": categories,
    }


def validate_coco(coco: dict[str, Any]) -> bool:
    """COCO의 ID 중복, 참조 관계 및 Bounding Box 크기를 검사한다."""
    image_ids = [item["id"] for item in coco["images"]]
    annotation_ids = [item["id"] for item in coco["annotations"]]
    category_ids = [item["id"] for item in coco["categories"]]
    return (
        len(image_ids) == len(set(image_ids))
        and len(annotation_ids) == len(set(annotation_ids))
        and len(category_ids) == len(set(category_ids))
        and all(item["image_id"] in set(image_ids) and item["category_id"] in set(category_ids) and item["bbox"][2] > 0 and item["bbox"][3] > 0 for item in coco["annotations"])
    )


def print_excluded_objects(excluded_objects: list[dict[str, Any]]) -> None:
    """최종 클래스 정책으로 제외된 객체와 제외 사유를 터미널에 출력한다."""
    print("\n[제외 객체 상세 목록]")

    if not excluded_objects:
        print("제외된 객체가 없습니다.")
        return

    print(f"제외 객체 수: {len(excluded_objects):,}개")

    for index, item in enumerate(excluded_objects, start=1):
        print(f"\n제외 객체 {index}")
        print(f"  데이터셋: {item.get('dataset', '확인 불가')}")
        print(f"  대분류: {item.get('class_name', '확인 불가')}")
        print(f"  세부 품목: {item.get('details', '확인 불가')}")
        print(f"  제외 사유: {item.get('reason', '확인 불가')}")
        print(f"  이미지 경로: {item.get('image_path', '확인 불가')}")


def main() -> None:
    """전체 전처리, 클래스 정책 적용, 결과 저장 및 COCO 검증을 순서대로 실행한다."""
    print("[생활폐기물 데이터 전처리 시작]")
    print("데이터 경로:", DATA_DIR.resolve())
    check_required_directories()
    PREPROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    COCO_DIR.mkdir(parents=True, exist_ok=True)

    train_objects, train_errors, train_counts = standardize_split("Training", TRAIN_IMAGE_DIR, TRAIN_LABEL_DIR)
    val_objects, val_errors, val_counts = standardize_split("Validation", VAL_IMAGE_DIR, VAL_LABEL_DIR)
    standardized = train_objects + val_objects
    errors = train_errors + val_errors
    final_annotations, excluded = apply_class_policy(standardized)
    final_annotations, class_records = assign_class_ids(final_annotations)

    used_ids = sorted({item["class_id"] for item in final_annotations})
    if used_ids != list(range(len(class_records))):
        raise ValueError("최종 클래스 ID가 연속적이지 않습니다.")

    train_coco = convert_to_coco(final_annotations, class_records, "Training")
    val_coco = convert_to_coco(final_annotations, class_records, "Validation")
    if not validate_coco(train_coco) or not validate_coco(val_coco):
        raise ValueError("COCO 정합성 검사에 실패했습니다.")
    if train_coco["categories"] != val_coco["categories"]:
        raise ValueError("Training과 Validation categories가 다릅니다.")

    mapping = {record["detail_class_name"]: record["class_id"] for record in class_records}
    save_json({"metadata": {"image_count": len({item["image_path"] for item in final_annotations}), "object_count": len(final_annotations), "major_class_count": len({item["class_name"] for item in final_annotations}), "detail_class_count": len(class_records)}, "class_id_mapping": mapping, "annotations": final_annotations}, PREPROCESSED_DIR / "final_annotations.json")
    save_json({"class_count": len(class_records), "classes": class_records}, PREPROCESSED_DIR / "class_id_mapping.json")
    save_csv(class_records, PREPROCESSED_DIR / "class_id_mapping.csv", ["class_id", "class_name", "details", "detail_class_name"])
    excluded_records = [{"dataset": item.get("dataset"), "image_path": item.get("image_path"), "class_name": item.get("class_name"), "details": item.get("details"), "reason": item.get("reason")} for item in excluded]
    save_csv(excluded_records, PREPROCESSED_DIR / "excluded_objects.csv", ["dataset", "image_path", "class_name", "details", "reason"])
    save_json({"created_at": datetime.now().isoformat(timespec="seconds"), "input": {"Training": train_counts, "Validation": val_counts}, "standardization_error_count": len(errors), "excluded_object_count": len(excluded), "final_object_count": len(final_annotations), "final_class_count": len(class_records)}, PREPROCESSED_DIR / "preprocessing_summary.json")
    save_json(errors, PREPROCESSED_DIR / "preprocessing_errors.json")
    save_json(train_coco, COCO_DIR / "instances_train.json")
    save_json(val_coco, COCO_DIR / "instances_val.json")

    # 제외된 객체가 무엇인지 실행 결과에서 바로 확인한다.
    # 같은 내용은 outputs/preprocessed/excluded_objects.csv에도 저장된다.
    print_excluded_objects(excluded)

    print("\n[전처리 완료]")
    print(f"표준화 객체: {len(standardized):,}")
    print(f"표준화 오류: {len(errors):,}")
    print(f"정책 제외 객체: {len(excluded):,}")
    print(f"최종 객체: {len(final_annotations):,}")
    print(f"최종 대분류: {len({item['class_name'] for item in final_annotations}):,}")
    print(f"최종 세부 클래스: {len(class_records):,}")
    print(f"Training COCO: 이미지 {len(train_coco['images']):,}, 객체 {len(train_coco['annotations']):,}")
    print(f"Validation COCO: 이미지 {len(val_coco['images']):,}, 객체 {len(val_coco['annotations']):,}")
    print("COCO 검증: True")
    print("저장 폴더:", OUTPUT_DIR.resolve())
        # 생성된 결과 파일의 이름과 전체 경로를 출력한다.
    saved_files = [
        PREPROCESSED_DIR / "final_annotations.json",
        PREPROCESSED_DIR / "class_id_mapping.json",
        PREPROCESSED_DIR / "class_id_mapping.csv",
        PREPROCESSED_DIR / "excluded_objects.csv",
        PREPROCESSED_DIR / "preprocessing_summary.json",
        PREPROCESSED_DIR / "preprocessing_errors.json",
        COCO_DIR / "instances_train.json",
        COCO_DIR / "instances_val.json",
    ]

    print("\n[저장 파일 목록]")

    for file_path in saved_files:
        if file_path.exists():
            file_size_mb = file_path.stat().st_size / (1024 ** 2)

            print(f"- {file_path.name}")
            print(f"  경로: {file_path.resolve()}")
            print(f"  크기: {file_size_mb:.2f} MB")
        else:
            print(f"- {file_path.name}: 저장되지 않음")


if __name__ == "__main__":
    main()
