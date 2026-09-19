# recycling_ssg Vision Server

Internal-only FastAPI service implementing the 2 AI endpoints from
`recycling_ssg_API_상세명세서_v6.0.pdf` 섹션 13:

- `POST /internal/v1/predict` -- YOLO 중앙 객체 탐지 + Top-K 후보
- `GET /internal/v1/classes` -- 현재 로드된 모델의 taxonomy
- `GET /health` -- liveness + model-load status

Never call this from the Frontend. Only the Backend
(`backend/services/vision_client.py`) talks to it, and only
`VISION_SERVER_BASE_URL` needs to be reachable from the Backend's network.

It shares the repo's root `uv` workspace virtual environment (the one that
already has `torch`/`ultralytics` installed for training), so no separate
`.venv` is needed here.

## Setup

```bash
cd /c/ai_challingers/recycling_ssg   # repo root, NOT vision/
uv sync --all-packages
cp vision/.env.example vision/.env   # then set MODEL_PATH to your trained best.pt
```

`MODEL_PATH` must point at a checkpoint trained on the project's 17-class
taxonomy (`data/train100val/data.yaml`), e.g. a copy of one of the
`ai/models/yolo/.../runs/<run>/weights/best.pt` experiment outputs. It does
**not** default to the untrained `weights/yolo26n.pt` COCO checkpoint on
purpose -- that model's class indices mean something completely different
and would silently corrupt every `class_id` downstream.

## Run

```bash
uv run uvicorn vision.main:app --reload --port 8100
```

If the model file is missing or fails to load, the service still starts
(so `/health` stays reachable for ops tooling) but `/internal/v1/predict`
and `/internal/v1/classes` respond `503 VISION_MODEL_NOT_READY` until a
valid checkpoint is in place -- the server will pick it up automatically
on the next request (lazy reload), no restart required.

## How "메인 객체" and Top-K candidates are derived

See the module docstring in `inference.py` for the full explanation. In
short: a single low-confidence-floor YOLO pass (`conf=LOW_CONFIDENCE_FLOOR`,
per-class NMS) is used both to locate the most likely main object
(largest, most central, most confident box) and to gather every other
class hypothesis whose box overlaps that same region (IoU >= 
`CANDIDATE_IOU_MATCH`) into the Top-K candidate list. The business-level
0.5 confidence gate (재촬영 여부) is applied by the **Backend**, not here --
this service only reports "no main object at all" (422
`VISION_NO_MAIN_OBJECT`) when nothing is detected even at the low floor.
