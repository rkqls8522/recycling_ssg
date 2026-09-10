# LangGraph 그래프 조립 (노드 연결)

from langgraph.graph import StateGraph, START, END
from src.agents.confidence_router import confidence_router
from src.agents.rule_node import make_rule_node
from src.agents.classify_node import make_classify_node
from src.agents.rag_node import AgentState, make_retrieve_node, make_generate_node


def build_graph(retriever, llm_config:dict):
    graph_builder = StateGraph(AgentState)

    graph_builder.add_node(confidence_router())
    graph_builder.add_node(make_rule_node())
    graph_builder.add_node(make_classify_node())
    graph_builder.add_node('retrive', make_retrieve_node(retriever))
    graph_builder.add_node('generate', make_generate_node(llm_config))
    

    graph_builder.add_edge(START, 'retrieve')
    graph_builder.add_edge('retrieve', 'generate')
    graph_builder.add_edge('generate', END)

    return graph_builder.compile()