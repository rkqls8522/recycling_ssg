
import os
import json
from google import genai
from google.genai import types
from dotenv import load_dotenv
from rag.configs.config import load_config
from rag.src.agents.state import VerificationSubState
from rag.src.retrieval.retriever import get_retriever
from rag.src.prompts.templates import get_generate_prompt, get_judge_prompt

load_dotenv()
config = load_config()
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
client = genai.Client(api_key=GOOGLE_API_KEY)

MAX_SUB_RETRY = 2
model_name = config['llm']


# retrieve node
def retrive_node(state: VerificationSubState) -> VerificationSubState:
    retriver = get_retriever()
    query = f"{state['sub_item']}의 {state['category']} {state['sub_item']} 분리 배출 방법"
    docs = retriver.invoke(query)

    state["regulation_text"] = docs

    return state


# generage node
def generate_node(state: VerificationSubState) -> VerificationSubState:
    llm = client.models.generate_content(
    model=model_name,
    config=types.GenerateContentConfig(
        temperature=0.7,
        top_p=0.95,
        max_output_tokens=1024,
        ),
    )
    
    prompt = get_generate_prompt(state)
    response = llm.invoke(prompt)
    state["generated_answer"] = response.content

    return state


# judge node
def judge_node(state: VerificationSubState) -> VerificationSubState:
    prompt = get_judge_prompt(state)
    verdict = json.loads(llm.invoke(prompt).content)

    state["is_valid"] = verdict["is_valid"]
    state["failure_reason"] = verdict.get("failure_reason", "")

    if not state["is_valid"]:
        state["retry_count"] = state.get("retry_count", 0) + 1

    return state


def route_after_judge(state: VerificationSubState) -> str:
    if state["is_valid"] or state["retry_count"] >= MAX_SUB_RETRY:
        return "end"
    return "retry"
