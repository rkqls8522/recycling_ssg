# 4번 노드의 sub graph 연결

from langgraph.graph import StateGraph, END
from src.agents.state import VerificationSubState
from src.agents.rag_node import retrive_node, generate_node, judge_node, route_after_judge

def build_sub_graph():
    sub_graph_builder = StateGraph(VerificationSubState)

    # 노드 등록
    sub_graph_builder.add_node('retrieve', retrive_node)
    sub_graph_builder.add_node('generate', generate_node)
    sub_graph_builder.add_node('judge', judge_node)

    # 엣지 등록 retrieve -> generate -> judge
    sub_graph_builder.add_edge('retrieve', 'generate')
    sub_graph_builder.add_edge('generate', 'judge')

    sub_graph_builder.add_conditional_edges("judge", route_after_judge, {
      "retry" : "generate",
      "end" : END  
    })

    # 시작점
    sub_graph_builder.set_entry_point("retrieve")

    return sub_graph_builder.compile()

