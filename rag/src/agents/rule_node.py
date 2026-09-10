from state import AgentState
from configs.config import load_config
from prompts.templates import get_rule_prompt

config = load_config()
k=config["retriever_k"]

# 공통 법령
def get_baseline(vectorstore, category: str, sub_item:str):
    filter_dict = {"type":"baseline", "category": category, "sub_item": sub_item}
    results = vectorstore.similarity_search(
        query = sub_item, # filter로 이미 좁혀지기 때문에 query는 형식적
        k=k,
        filter=filter_dict
    )

    return results[0] if results else None    


# 지자체별 규칙
def get_exception(vectorstore, category: str, sub_item:str, region:str):
    filter_dict = {"category": category, "sub_item": sub_item, "region": region}
    results = vectorstore.similarity_search(
        query = sub_item, # filter로 이미 좁혀지기 때문에 query는 형식적
        k=k,
        filter=filter_dict
    )

    return results[0] if results else None
    

def make_rule_node(vectorstore):
    def rule_node(state: AgentState):
        category = state['category']
        sub_item = state['sub_item']
        region = state['state']

        exception_doc = get_exception(vectorstore, category, sub_item, region)
        if exception_doc:
            meta = exception_doc.metadata
            answer = get_rule_prompt(
                region = meta['region'],
                category = meta['category'],
                sub_item= meta['sub_item'],
                rule = exception_doc.page_content,
                exception_type=meta.get("exception_type")
            )
        else: 
            baseline_doc = get_baseline(vectorstore, category, sub_item)
            answer = get_rule_prompt(
                region = "공통 기준",
                category = category,
                sub_item= sub_item,
                rule = baseline_doc.page_content if baseline_doc else "관련 규정을 찾을 수 없습니다."
            )

        return {"answer":answer}
    
    return rule_node