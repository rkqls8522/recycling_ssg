"""Pure-logic tests for the main-object selection + Top-K candidate scoring
heuristics in inference.py. None of these require the actual YOLO
checkpoint to be loadable -- ultralytics is only imported lazily inside
VisionModel._try_load()/_predict_capturing_raw()."""

from __future__ import annotations

import torch

from vision.core.config import settings
from vision.inference import _Detection, _select_main_object, _top_k_from_raw_scores


def test_select_main_object_prefers_large_central_confident_box():
    noise = _Detection(0.01, 0.01, 0.08, 0.08, conf=0.06, cls=5)  # tiny, corner, low-conf
    main = _Detection(0.2, 0.2, 0.8, 0.8, conf=0.85, cls=22)  # large, centered, confident
    chosen = _select_main_object([noise, main])
    assert chosen is main


def _raw_prediction(num_classes: int, num_anchors: int, anchor_scores: dict[int, list[float]]) -> torch.Tensor:
    """Build a synthetic (1, 4+num_classes, num_anchors) raw prediction
    tensor with all-zero boxes, and the given per-class score list placed at
    each of ``anchor_scores``' anchor indices."""
    raw = torch.zeros((1, 4 + num_classes, num_anchors))
    for anchor_idx, scores in anchor_scores.items():
        raw[0, 4 : 4 + num_classes, anchor_idx] = torch.tensor(scores)
    return raw


def test_top_k_from_raw_scores_returns_exactly_top_k_sorted_descending(monkeypatch):
    monkeypatch.setattr(settings, "top_k", 3)
    # class 4 highest, then 1, then 0; classes 2/3 lower still.
    raw = _raw_prediction(5, num_anchors=2, anchor_scores={1: [0.2, 0.05, 0.01, 0.001, 0.9]})

    candidates = _top_k_from_raw_scores(raw, anchor_idx=1)

    assert [c["class_id"] for c in candidates] == [4, 0, 1]
    scores = [c["score"] for c in candidates]
    assert scores == sorted(scores, reverse=True)


def test_top_k_from_raw_scores_ignores_confidence_magnitude(monkeypatch):
    """Even when the model is extremely confident about one class (every
    other class near-zero), the result must still have exactly top_k
    entries -- there is no threshold that could drop the weaker ones."""
    monkeypatch.setattr(settings, "top_k", 3)
    raw = _raw_prediction(5, num_anchors=1, anchor_scores={0: [0.0001, 0.0002, 0.0000, 0.9999, 0.00005]})

    candidates = _top_k_from_raw_scores(raw, anchor_idx=0)

    assert len(candidates) == 3
    assert candidates[0]["class_id"] == 3
    assert candidates[0]["score"] == 0.9999


def test_top_k_from_raw_scores_reads_only_the_given_anchor():
    raw = _raw_prediction(
        4,
        num_anchors=2,
        anchor_scores={0: [0.9, 0.1, 0.1, 0.1], 1: [0.1, 0.1, 0.1, 0.9]},
    )

    candidates = _top_k_from_raw_scores(raw, anchor_idx=1)

    assert candidates[0]["class_id"] == 3
