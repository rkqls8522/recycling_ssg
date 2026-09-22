from rag.src.agents.state import DisposalResult, AgentState
from rag.src.agents.rule_lookup import find_national_rule, find_region_rule


def disposal_lookup_node(state: AgentState) -> dict:
    major_category = state["major_category"]
    minor_category = state["minor_category"]
    user_region = state["user_region"]

    national_rule = find_national_rule(major_category, minor_category)
    region_rule = find_region_rule(major_category, minor_category, user_region)

    result: DisposalResult = {
        "item": (national_rule or {}).get("item"),
        "major_category": major_category,
        "minor_category": minor_category,
        "national_rule": (
            {"source": national_rule["source"], "method": national_rule["method"]}
            if national_rule else None
        ),
        "region_rule": region_rule,
        "has_region_exception": region_rule is not None,
    }
    return {"disposal_result": result}