from typing_extensions import List, TypedDict, Dict
from langchain_core.documents import Document

class AgentState(TypedDict):
    category : str                # 대분류
    sub_item : str                # 소분류
    item_list : List[Dict]        # 분류 이미지별 유사도 리스트
    region : str                  # 지역명
    img_url : str                 # llm 분류위한 이미지 url
    is_rag_result : bool          # 4번 노드에서 판단 위한 값 (loop의 여부)
    final_answer_list : List[str] # 배출 방법
    failure_reason: str

class VerificationSubState(TypedDict):
    category: str                            # 대분류
    sub_item: str                            # 소분류
    region: str                              # 지역명
    regulation_text:List[str]                # LLM이 참고할 문서  
    generated_answer: List[Dict[str, str]]   # 자연어 배출방법 리스트
    is_valid: bool                           # 검증 통과 여부
    failure_reason: str                      # 실패 이유
    retry_count: int                         # generate <-> judge 루프 카운터