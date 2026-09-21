import time
from pydantic import BaseModel, Field
from rag.src.agents.state import AgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from rag.src.prompts.templates import get_llm_prompt
from rag.configs.config import load_config


class ClassifyResult(BaseModel):
    major_category: str = Field(description="대분류")
    minor_category: str = Field(description="소분류")


config = load_config()
MODEL_NAME = config["llm"]

llm = ChatGoogleGenerativeAI(
    model=MODEL_NAME,
    temperature=0.2,
    max_output_tokens=1024
).with_structured_output(ClassifyResult)

prompt = get_llm_prompt()

def llm_classify_node(state: AgentState):
    start = time.time()
    print(f"✅ [classify] 시작 (retry_count={state.get('retry_count', 0)})")

    img_url = state["img_url"]
    failure_reason = state.get('failure_reason', "")

    failure_reason_section = (
        f"\n[참고] 이전 분류 시도가 다음 이유로 반려되었습니다: {failure_reason}\n"
        f"이 점을 고려해서 다시 분류하세요.\n"
        if failure_reason else ""
    )

    classify_chain = prompt | llm
    result: ClassifyResult = classify_chain.invoke({
        'img_url': img_url,
        'failure_reason_section': failure_reason_section,
    })


    print(f"✅[classify] 완료: {result.major_category}/{result.minor_category} ({time.time() - start:.1f}초)")


    return {'major_category': result.major_category, 'minor_category': result.minor_category}