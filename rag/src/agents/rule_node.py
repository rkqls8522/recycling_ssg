from state import AgentState

def make_rule_node():
    def rule_node(state: AgentState):
        return {"category",state['category'], 
                "sub_item",state['sub_item'],
                "is_rag_result", False}
    
    return rule_node