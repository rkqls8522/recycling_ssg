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
