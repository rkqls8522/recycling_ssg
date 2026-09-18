from pydantic import BaseModel, Field
from rag.src.agents.state import AgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from rag.src.prompts.templates import get_llm_prompt
from rag.configs.config import load_config


class ClassifyResult(BaseModel):
    category: str = Field(description="대분류")
    sub_item: str = Field(description="소분류")


config = load_config()
MODEL_NAME = config["llm"]

llm = ChatGoogleGenerativeAI(
    model=MODEL_NAME,
    temperature=0.2,
    max_output_tokens=300
).with_structured_output(ClassifyResult)

prompt = get_llm_prompt()

def llm_classify_node(state: AgentState):
    img_url = state["img_url"]
    failure_reason = state.get('failure_reason', "")

    if failure_reason:
        failure_reason_section = (
            f"\n[참고] 이전 분류 시도가 다음 이유로 반려되었습니다: {failure_reason}\n"
            f"이 점을 고려해서 다시 분류하세요.\n"
        )
    else:
        failure_reason_section = ""

    classify_chain = prompt | llm
    result: ClassifyResult = classify_chain.invoke({
        'img_url': img_url,
        'failure_reason_section': failure_reason_section,
    })

    return {'category': result.category, 'sub_item': result.sub_item}