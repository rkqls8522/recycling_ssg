"""YOLO detection wrapper: single inference pass -> main-object selection ->
Top-K candidate scores for that object (섹션 13.1, SR-04~SR-07).

Design notes
------------
Standard Ultralytics YOLO keeps only the best class per surviving box after
NMS, so a single ``model.predict()`` call does not directly give a
class-probability distribution for one object -- by the time a box comes
back, every other class has already been thrown away by
``argmax``/thresholding. Requiring a *guaranteed* Top-K (SR-06/SR-07) even
when the model is extremely confident about one class (e.g. 0.95, with every
other class under 0.01%) rules out any approach based on a confidence floor:
no floor is low enough to reliably surface classes that faint.

Instead we reach one layer below Ultralytics' post-processing:

1. Run detection normally (``settings.low_confidence_floor``, per-class
   NMS) and pick the "main object" box: the detection maximizing
   ``confidence * area * (1 - distance_from_image_center)`` -- i.e. a
   confident, large, centered box, matching how users are expected to
   photograph a single item (SR-05).
2. While that single ``model.predict()`` call runs, ``_predict_capturing_raw``
   temporarily wraps ``ultralytics.utils.nms.non_max_suppression`` to also
   hand back (a) the raw pre-NMS prediction tensor -- shape
   ``(1, 4 + num_classes, num_anchors)``, per-class scores already
   sigmoid-activated by the detection head -- and (b) which raw anchor index
   NMS kept for each surviving box, in the same order as the boxes
   themselves. This changes nothing about detection/NMS itself; it only
   exposes data Ultralytics already computes internally and normally
   discards.
3. Look up the main box's own anchor index and read *every* class's raw
   score at that single anchor directly out of the raw tensor, then take the
   top ``settings.top_k`` by score -- with no threshold at all, so the
   result always has exactly ``top_k`` entries regardless of how confident
   the model is. These are the object's Top-K 후보 리스트.
4. If literally nothing is detected even at the low floor, no main object
   exists -> :class:`NoMainObjectError` (mapped to 422 VISION_NO_MAIN_OBJECT).
"""

from __future__ import annotations

import io
import logging
import threading
import time

import torch
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
            results, raw_prediction, keep_idx = _predict_capturing_raw(self._model, pil_image)
            detections = _extract_detections(results)
            if not detections:
                raise NoMainObjectError("no detections above low confidence floor")
            main_box = _select_main_object(detections)
            anchor_idx = int(keep_idx[detections.index(main_box)].item())
            candidates = _top_k_from_raw_scores(raw_prediction, anchor_idx)
        inference_ms = (time.perf_counter() - start) * 1000

        return candidates, inference_ms, main_box


def _predict_capturing_raw(model, pil_image) -> tuple[list, torch.Tensor, torch.Tensor]:
    """Run ``model.predict()`` once, capturing the raw pre-NMS prediction
    tensor and the raw anchor index NMS kept for each surviving box.

    Works by temporarily wrapping ``ultralytics.utils.nms.non_max_suppression``
    (called internally by ``model.predict()``) to also request
    ``return_idxs=True`` and stash both its input tensor and its second
    (indices) return value in a closure, then restoring the original
    function. Detection/NMS behavior is completely unchanged -- only what we
    additionally read off is different. Safe to call concurrently only under
    ``VisionModel._lock`` (module-global patch).
    """
    from ultralytics.utils import nms as ultra_nms

    captured: dict = {}
    original_nms = ultra_nms.non_max_suppression

    def _patched(prediction, *args, **kwargs):
        # Mirror non_max_suppression's own unwrapping (e.g. validation-mode
        # models return (inference_out, loss_out)) so the captured tensor is
        # always the plain (batch, 4+nc, num_anchors) prediction.
        captured["raw"] = prediction[0] if isinstance(prediction, (list, tuple)) else prediction
        kwargs["return_idxs"] = True
        output, keep_idxs = original_nms(prediction, *args, **kwargs)
        captured["keep_idx"] = keep_idxs[0]
        return output

    ultra_nms.non_max_suppression = _patched
    try:
        results = model.predict(
            source=pil_image,
            conf=settings.low_confidence_floor,
            iou=settings.nms_iou,
            agnostic_nms=False,
            max_det=settings.max_detections,
            verbose=False,
        )
    finally:
        ultra_nms.non_max_suppression = original_nms

    return results, captured["raw"], captured["keep_idx"]


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


def _top_k_from_raw_scores(raw_prediction: torch.Tensor, anchor_idx: int) -> list[dict]:
    """Rank every class by its raw (pre-NMS, sigmoid-activated) score at one
    specific anchor and return the top ``settings.top_k``. Unlike NMS-survived
    boxes, this has no confidence threshold, so it always returns exactly
    ``top_k`` candidates -- even when the model is so confident that no other
    class would ever clear any reasonable floor."""
    num_classes = raw_prediction.shape[1] - 4
    class_scores = raw_prediction[0, 4 : 4 + num_classes, anchor_idx]
    k = min(settings.top_k, num_classes)
    top_scores, top_classes = torch.topk(class_scores, k)

    candidates = []
    for score, class_id in zip(top_scores.tolist(), top_classes.tolist(), strict=True):
        major, minor = category_label(class_id)
        candidates.append(
            {
                "class_id": class_id,
                "category": f"{major}_{minor}",
                "score": round(score, 4),
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
