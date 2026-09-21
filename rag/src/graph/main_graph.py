from langgraph.graph import StateGraph, END
from rag.src.agents.state import  AgentState
from rag.src.agents.llm_classify_node import llm_classify_node
from rag.src.agents.judge_node import judge_node
from rag.src.agents.disposal_lookup_node import disposal_lookup_node


def request_retake_node(state:AgentState):
   return {}

MAX_CLASSIFY_RETRIES = 2
def route_after_judge(state: AgentState) -> str:
    if state.get("is_valid"):
        return "disposal_lookup"
    if state.get("retry_count", 0) >= MAX_CLASSIFY_RETRIES:
        return "request_retake"
    return "classify"


# "여기없음" 플로우 전용 그래프 (classify -> judge -> disposal_lookup)
graph = StateGraph(AgentState)
graph.add_node("classify", llm_classify_node)
graph.add_node("judge", judge_node)
graph.add_node("disposal_lookup", disposal_lookup_node)
graph.add_node("request_retake", request_retake_node)

graph.set_entry_point("classify")
graph.add_edge("classify", "disposal_lookup")
# graph.add_edge("classify", "judge")
# graph.add_conditional_edges("judge", route_after_judge, {
#     "disposal_lookup": "disposal_lookup",
#     "classify": "classify",
#     "request_retake": "request_retake",
# })
graph.add_edge("disposal_lookup", END)
graph.add_edge("request_retake", END)

app = graph.compile()


# vision 모델이 이미 분류 성공한 경우 : 그래프 없이 바로 조회
def handle_direct_classification(major_category: str, minor_category: str, user_region: dict) -> dict:
    state = {
        "major_category": major_category,
        "minor_category": minor_category,
        "user_region": user_region,
    }
    return disposal_lookup_node(state)


# "여기없음" 선택된 경우 : classify -> judge 루프 그래프 실행
def handle_not_in_list(img_url: str, user_region: dict) -> dict:
    graph_state = {
        "major_category": "",
        "minor_category": "",
        "img_url": img_url,
        "user_region": user_region,
        "item_list": [],
        "failure_reason": "",
        "retry_count": 0,
    }
    result = app.invoke(graph_state)

    disposal_result = result.get("disposal_result")
    return {
        "major_category": result.get("major_category"),
        "minor_category": result.get("minor_category"),
        "disposal_result": disposal_result,
        "needs_retake": disposal_result is None,
    }