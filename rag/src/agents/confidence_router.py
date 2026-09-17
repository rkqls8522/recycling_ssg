from rag.src.agents.state import AgentState

# confidence에 따른 분기처리 
def confidence_router(state: AgentState):
    confidence = state["confidence"]

    if confidence >= 0.8 : return "rule_node"
    elif confidence <= 0.3 : return "classify_node"
    else: return "retake_request"