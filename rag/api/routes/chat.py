from fastapi import APIRouter
from rag.src.agents.chatbot_node import chatbot_node
from ..schemas import ChatNodeRequest, ChatNodeResponse

router = APIRouter()


# 챗봇 노드(node4): 이미 분류/저장된 major_category/minor_category 기준으로
# national_rule/region_rule을 조회해 답변 근거로 쓰고, 사용자의 자유 질문
#(user_message)은 검색이 아니라 답변 생성에만 사용한다.
@router.post("/chat_node", response_model=ChatNodeResponse)
def chat_node(payload: ChatNodeRequest) -> ChatNodeResponse:
    result = chatbot_node(
        major_category=payload.major_category,
        minor_category=payload.minor_category,
        user_region=payload.user_region.model_dump(),
        user_message=payload.message,
    )
    return ChatNodeResponse(**result)
