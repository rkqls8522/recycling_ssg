"""YOLO detection wrapper: single inference pass -> main-object selection ->
Top-K candidate scores for that object (섹션 13.1, SR-04~SR-07).

Design notes
------------
Standard Ultralytics YOLO keeps only the best class per surviving box after
NMS, so a single ``model.predict()`` call does not directly give a
class-probability distribution for one object. To still produce a
meaningful Top-K *for the same spatial object* without a second model head,
we run detection at a low confidence floor (``settings.low_confidence_floor``)
with per-class (non-agnostic) NMS, which lets *several different classes*
independently survive NMS for the same overlapping region when the model is
genuinely unsure between them. We then:

1. Pick the "main object" box: the detection maximizing
   ``confidence * area * (1 - distance_from_image_center)`` -- i.e. a
   confident, large, centered box, matching how users are expected to
   photograph a single item (SR-05).
2. Collect every other detected box whose IoU with the main box is >=
   ``settings.candidate_iou_match`` (i.e. "the same object"), keep the max
   confidence per class_id, sort descending, and take the top K -- this is
   the object's Top-K 후보 score list (SR-06/SR-07).
3. If literally nothing is detected even at the low floor, no main object
   exists -> :class:`NoMainObjectError` (mapped to 422 VISION_NO_MAIN_OBJECT).
"""

from __future__ import annotations

import io
import logging
import threading
import time

from PIL import Image, UnidentifiedImageError

from vision.core.config import settings
from vision.core.taxonomy import category_label

logger = logging.getLogger(__name__)


class ImageDecodeError(Exception):
    pass


class NoMainObjectError(Exception):
    pass


class ModelNotReadyError(Exception):
    pass


class _Detection:
    __slots__ = ("cls", "conf", "x1", "x2", "y1", "y2")

    def __init__(self, x1: float, y1: float, x2: float, y2: float, conf: float, cls: int) -> None:
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.conf = conf
        self.cls = cls

    @property
    def area(self) -> float:
        return max(0.0, self.x2 - self.x1) * max(0.0, self.y2 - self.y1)

    @property
    def center(self) -> tuple[float, float]:
        return (self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2


def _iou(a: _Detection, b: _Detection) -> float:
    ix1, iy1 = max(a.x1, b.x1), max(a.y1, b.y1)
    ix2, iy2 = min(a.x2, b.x2), min(a.y2, b.y2)
    inter_w, inter_h = max(0.0, ix2 - ix1), max(0.0, iy2 - iy1)
    inter = inter_w * inter_h
    union = a.area + b.area - inter
    return inter / union if union > 0 else 0.0


class VisionModel:
    """Lazily-loaded, thread-safe singleton around the Ultralytics YOLO
    checkpoint. Loading failures degrade gracefully (VISION_MODEL_NOT_READY)
    instead of crashing the whole service."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._model = None
        self._load_error: str | None = None
        self._try_load()

    def _try_load(self) -> None:
        model_path = settings.resolved_model_path
        if not model_path.exists():
            self._load_error = f"model checkpoint not found: {model_path}"
            logger.error(self._load_error)
            return
        try:
            from ultralytics import YOLO

            self._model = YOLO(str(model_path))
            logger.info("YOLO model loaded from %s", model_path)
        except Exception as exc:
            self._load_error = f"failed to load YOLO model: {exc}"
            logger.exception(self._load_error)
            self._model = None

    @property
    def is_ready(self) -> bool:
        return self._model is not None

    def reload_if_needed(self) -> None:
        if self._model is None:
            with self._lock:
                if self._model is None:
                    self._try_load()

    def predict(self, image_bytes: bytes) -> tuple[list[dict], float, _Detection]:
        """Returns (candidate_score_dicts, inference_ms, main_box) for the
        chosen main object, or raises NoMainObjectError / ImageDecodeError /
        ModelNotReadyError."""
        self.reload_if_needed()
        if self._model is None:
            raise ModelNotReadyError(self._load_error or "model not loaded")

        try:
            pil_image = Image.open(io.BytesIO(image_bytes))
            pil_image.load()
            pil_image = pil_image.convert("RGB")
        except (UnidentifiedImageError, OSError, ValueError) as exc:
            raise ImageDecodeError(str(exc)) from exc

        start = time.perf_counter()
        with self._lock:
            results = self._model.predict(
                source=pil_image,
                conf=settings.low_confidence_floor,
                iou=settings.nms_iou,
                agnostic_nms=False,
                max_det=settings.max_detections,
                verbose=False,
            )
        inference_ms = (time.perf_counter() - start) * 1000

        detections = _extract_detections(results)
        if not detections:
            raise NoMainObjectError("no detections above low confidence floor")

        main_box = _select_main_object(detections)
        candidates = _build_candidates(detections, main_box)
        return candidates, inference_ms, main_box


def _extract_detections(results) -> list[_Detection]:
    detections: list[_Detection] = []
    if not results:
        return detections
    result = results[0]
    boxes = getattr(result, "boxes", None)
    if boxes is None or len(boxes) == 0:
        return detections

    xyxyn = boxes.xyxyn.tolist()
    confs = boxes.conf.tolist()
    classes = boxes.cls.tolist()
    for (x1, y1, x2, y2), conf, cls in zip(xyxyn, confs, classes, strict=False):
        detections.append(_Detection(x1, y1, x2, y2, float(conf), int(cls)))
    return detections


def _select_main_object(detections: list[_Detection]) -> _Detection:
    def score(d: _Detection) -> float:
        cx, cy = d.center
        dist = ((cx - 0.5) ** 2 + (cy - 0.5) ** 2) ** 0.5
        return d.conf * d.area * (1 - min(dist, 1.0))

    return max(detections, key=score)


def _build_candidates(detections: list[_Detection], main_box: _Detection) -> list[dict]:
    best_conf_by_class: dict[int, float] = {}
    for d in detections:
        if _iou(d, main_box) >= settings.candidate_iou_match:
            best_conf_by_class[d.cls] = max(best_conf_by_class.get(d.cls, 0.0), d.conf)

    # main_box's own class is always included (IoU with itself == 1.0).
    best_conf_by_class[main_box.cls] = max(best_conf_by_class.get(main_box.cls, 0.0), main_box.conf)

    ranked = sorted(best_conf_by_class.items(), key=lambda kv: kv[1], reverse=True)
    ranked = ranked[: settings.top_k]

    candidates = []
    for class_id, conf in ranked:
        major, minor = category_label(class_id)
        candidates.append(
            {
                "class_id": class_id,
                "category": f"{major}_{minor}",
                "score": round(conf, 4),
            }
        )
    return candidates


_model_singleton: VisionModel | None = None
_singleton_lock = threading.Lock()


def get_model() -> VisionModel:
    global _model_singleton
    if _model_singleton is None:
        with _singleton_lock:
            if _model_singleton is None:
                _model_singleton = VisionModel()
    return _model_singleton
