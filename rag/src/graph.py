# LangGraph 그래프 조립 (노드 연결)

from langgraph.graph import StateGraph, START, END
from src.agents.rag_reasoning import AgentState, make_retrieve_node, make_generate_node


def build_graph(retriever, llm_config:dict):
    graph_builder = StateGraph(AgentState)

    graph_builder.add_node('retrieve', make_retrieve_node(retriever))
    graph_builder.add_node('generate', make_generate_node(llm_config))

    graph_builder.add_edge(START, 'retrieve')
    graph_builder.add_edge('retrieve', 'generate')
    graph_builder.add_edge('generate', END)

    return graph_builder.compile()