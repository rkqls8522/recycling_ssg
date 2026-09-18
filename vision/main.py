"""Vision Server -- Backend-only internal API (섹션 13).

Implements the 2 AI endpoints from the spec:
  POST /internal/v1/predict   YOLO 중앙 객체 탐지 + Top-K 후보
  GET  /internal/v1/classes   현재 로드된 모델의 taxonomy

Never exposed to the Frontend directly -- only the Backend calls this,
over a private network in production (섹션 13 보안 note).
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from vision.core.config import settings
from vision.core.errors import VisionError, register_exception_handlers
from vision.core.middleware import RequestIDMiddleware
from vision.core.taxonomy import category_label, load_waste_classes
from vision.inference import (
    ImageDecodeError,
    ModelNotReadyError,
    NoMainObjectError,
    get_model,
)
from vision.schemas import (
    BBoxOut,
    CandidateScoreOut,
    ClassEntryOut,
    ClassesResponse,
    HealthResponse,
    InternalMetaOut,
    PredictResponse,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    model = get_model()
    if model.is_ready:
        logger.info("Vision model ready at startup (%s)", settings.resolved_model_path)
    else:
        logger.warning(
            "Vision model NOT ready at startup -- /internal/v1/predict will return "
            "503 VISION_MODEL_NOT_READY until %s exists and loads successfully.",
            settings.resolved_model_path,
        )
    yield


app = FastAPI(title="recycling_ssg Vision Server", version="1.0.0", lifespan=lifespan)

app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],  # never called directly from a browser
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    model = get_model()
    return HealthResponse(
        status="ok",
        model_loaded=model.is_ready,
        model_version=settings.model_version if model.is_ready else None,
    )


@app.post("/internal/v1/predict", response_model=PredictResponse)
def predict(image: UploadFile = File(...)) -> PredictResponse:
    content_type = (image.content_type or "").lower()
    if content_type not in settings.allowed_image_content_type_set:
        raise VisionError(
            status_code=415,
            code="IMAGE_TYPE_UNSUPPORTED",
            message="지원하지 않는 이미지 형식입니다.",
        )

    file_bytes = image.file.read()
    if not file_bytes:
        raise VisionError(status_code=400, code="IMAGE_EMPTY", message="업로드된 이미지가 비어 있습니다.")
    if len(file_bytes) > settings.max_image_size_bytes:
        raise VisionError(
            status_code=413,
            code="IMAGE_TOO_LARGE",
            message="업로드 가능한 이미지 크기를 초과했습니다.",
        )

    model = get_model()
    try:
        candidates, inference_ms, main_box = model.predict(file_bytes)
    except ImageDecodeError as exc:
        raise VisionError(
            status_code=400, code="IMAGE_DECODE_FAILED", message="이미지를 읽을 수 없습니다."
        ) from exc
    except NoMainObjectError as exc:
        raise VisionError(
            status_code=422,
            code="VISION_NO_MAIN_OBJECT",
            message="화면 중앙에서 메인 객체를 찾지 못했습니다.",
        ) from exc
    except ModelNotReadyError as exc:
        raise VisionError(
            status_code=503,
            code="VISION_MODEL_NOT_READY",
            message="이미지 분석 모델이 준비되지 않았습니다.",
        ) from exc

    top1 = candidates[0]
    major, minor = category_label(top1["class_id"])

    return PredictResponse(
        major_category=major,
        minor_category=minor,
        candidate_scores=[CandidateScoreOut(**c) for c in candidates],
        internal_meta=InternalMetaOut(
            bbox=BBoxOut(x1=main_box.x1, y1=main_box.y1, x2=main_box.x2, y2=main_box.y2),
            model_version=settings.model_version,
            inference_ms=round(inference_ms, 2),
        ),
    )


@app.get("/internal/v1/classes", response_model=ClassesResponse)
def classes() -> ClassesResponse:
    model = get_model()
    if not model.is_ready:
        raise VisionError(
            status_code=503,
            code="VISION_MODEL_NOT_READY",
            message="이미지 분석 모델이 준비되지 않았습니다.",
        )

    taxonomy = load_waste_classes()
    entries = [
        ClassEntryOut(class_id=class_id, major_category=major, minor_category=minor)
        for class_id, (major, minor) in sorted(taxonomy.items())
    ]
    return ClassesResponse(model_version=settings.model_version, classes=entries)
