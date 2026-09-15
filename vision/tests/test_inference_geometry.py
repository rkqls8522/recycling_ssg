"""Pure-logic tests for the main-object selection + Top-K candidate scoring
heuristics in inference.py. None of these require the actual YOLO
checkpoint to be loadable -- ultralytics is only imported lazily inside
VisionModel._try_load()."""

from __future__ import annotations

from vision.inference import _build_candidates, _Detection, _iou, _select_main_object


def test_iou_identical_boxes_is_one():
    box = _Detection(0.1, 0.1, 0.5, 0.5, conf=0.9, cls=1)
    assert _iou(box, box) == 1.0


def test_iou_disjoint_boxes_is_zero():
    a = _Detection(0.0, 0.0, 0.1, 0.1, conf=0.9, cls=1)
    b = _Detection(0.5, 0.5, 0.6, 0.6, conf=0.9, cls=2)
    assert _iou(a, b) == 0.0


def test_iou_partial_overlap():
    a = _Detection(0.0, 0.0, 0.4, 0.4, conf=0.9, cls=1)
    b = _Detection(0.2, 0.2, 0.6, 0.6, conf=0.9, cls=2)
    # intersection: 0.2x0.2=0.04, union: 0.16+0.16-0.04=0.28
    assert abs(_iou(a, b) - (0.04 / 0.28)) < 1e-6


def test_select_main_object_prefers_large_central_confident_box():
    noise = _Detection(0.01, 0.01, 0.08, 0.08, conf=0.06, cls=5)  # tiny, corner, low-conf
    main = _Detection(0.2, 0.2, 0.8, 0.8, conf=0.85, cls=22)  # large, centered, confident
    chosen = _select_main_object([noise, main])
    assert chosen is main


def test_build_candidates_includes_main_class_and_overlapping_classes_sorted():
    main = _Detection(0.2, 0.2, 0.8, 0.8, conf=0.81, cls=22)
    overlapping_alt = _Detection(0.21, 0.21, 0.79, 0.79, conf=0.12, cls=15)  # same region, other class
    far_away = _Detection(0.0, 0.0, 0.05, 0.05, conf=0.9, cls=99)  # different object entirely

    candidates = _build_candidates([main, overlapping_alt, far_away], main)

    class_ids = [c["class_id"] for c in candidates]
    assert class_ids[0] == 22  # highest score first
    assert 15 in class_ids
    assert 99 not in class_ids  # IoU too low with main box, excluded
    scores = [c["score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_build_candidates_dedupes_by_class_keeping_max_confidence():
    main = _Detection(0.2, 0.2, 0.8, 0.8, conf=0.5, cls=22)
    same_class_higher_conf = _Detection(0.22, 0.22, 0.78, 0.78, conf=0.9, cls=22)

    candidates = _build_candidates([main, same_class_higher_conf], main)

    assert len(candidates) == 1
    assert candidates[0]["class_id"] == 22
    assert candidates[0]["score"] == 0.9
