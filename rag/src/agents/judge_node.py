import time
from pydantic import BaseModel, Field
from rag.src.agents.state import AgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from rag.src.prompts.templates import get_judge_prompt
from rag.configs.config import load_config

MAX_CLASSIFY_RETRIES = 2

class ClassifyJudgeResult(BaseModel):
    is_valid: bool = Field(description="major_category/minor_category 라벨이 이미지 내용과 실제로 일치하면 true")
    reason: str = Field(description="불일치 시 구체적 사유, 일치하면 빈 문자열")

config = load_config()
MODEL_NAME = config["llm"]

llm = ChatGoogleGenerativeAI(
    model=MODEL_NAME,
    temperature=0,
    max_output_tokens=1024
).with_structured_output(ClassifyJudgeResult)

prompt = get_judge_prompt()

def judge_node(state: AgentState):
    start = time.time()
    print(f"✅[judge] 시작: {state['major_category']}/{state['minor_category']} 검증 중")

    judge_chain = prompt | llm
    result: ClassifyJudgeResult = judge_chain.invoke({
        "img_url": state["img_url"],
        "major_category": state["major_category"],
        "minor_category": state["minor_category"],
    })

    print(f"✅ [judge] 완료: is_valid={result.is_valid} ({time.time() - start:.1f}초)")



    if result.is_valid:
        return {"is_valid": True, "failure_reason": ""}

    return {
        "is_valid": False,
        "failure_reason": result.reason,
        "retry_count": state.get("retry_count", 0) + 1,
    }
