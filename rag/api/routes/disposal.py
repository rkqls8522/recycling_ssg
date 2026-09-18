from fastapi import APIRouter
from rag.src.agents.disposal_loopup_node import disposal_lookup_node
from ..schemas import ClassificationResultWithDisposal, ClassificationResult

router = APIRouter()

@router.post("/rule_node", response_model=ClassificationResultWithDisposal)
def get_disposal_info(payload: ClassificationResult) -> ClassificationResultWithDisposal:
    state = payload.model_dump()
    updated_state = disposal_lookup_node(state)
    return updated_state
