from typing_extensions import List, TypedDict, Dict
from langchain_core.documents import Document

class AgentState(TypedDict):
    query: str               # 사용자의 질문
    context : List[Document] # LLM이 답변에 참고할 문서
    category : str     # 대분류
    sub_item : str       # 소분류
    item_list : List[Dict]   # 분류 이미지별 유사도 리스트
    region : str             # 지역명
    retry_count : int        # 3 <-> 4 노드 루프 횟수 
    answer: str 