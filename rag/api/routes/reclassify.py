from fastapi import APIRouter
from rag.src.graph.main_graph import handle_not_in_list
from ..schemas import ReclassifyRequest, ReclassifyResponse

router = APIRouter()

# 여기없음" 플로우 전용: classify -> judge 재분류 루프를 실행하고,
# 검증을 통과하면 disposal_lookup까지 마친 결과를 반환한다.
# judge 루프를 재시도 횟수만큼 소진하면 needs_retake=True로 응답한다.

@router.post("/reclassify", response_model=ReclassifyResponse)
def reclassify(payload: ReclassifyRequest) -> ReclassifyResponse:
    return handle_not_in_list(
        img_url=payload.img_url,
        user_region=payload.user_region.model_dump(),
    )
