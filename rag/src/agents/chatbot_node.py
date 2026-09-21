from rag.configs.config import load_config
from rag.src.prompts.templates import get_chatbot_prompt
from rag.src.agents.rule_lookup import find_region_rule, find_national_rule
from langchain_google_genai import ChatGoogleGenerativeAI


config = load_config()
prompt = get_chatbot_prompt()
llm = ChatGoogleGenerativeAI(model=config['llm'], temperature=0.3)

def chatbot_node(major_category: str, minor_category: str, user_region: dict, user_message: str) -> dict:
    national_rule = find_national_rule(major_category, minor_category)
    region_rule = find_region_rule(major_category, minor_category, user_region)

    chain = prompt | llm
    result = chain.invoke({
        "major_category": major_category,
        "minor_category": minor_category,
        "national_rule_text": (national_rule or {}).get("method") or "정보 없음",
        "region_rule_text": (region_rule or {}).get("method") or "해당 없음",
        "user_message": user_message,
    })

    return {"answer": result.content}