
import json
from google import genai
from google.genai import types
from configs.config import load_config
from agents.state import VerificationSubState
from retrieval import get_retriever
from prompts.templates import get_generate_prompt, get_judge_prompt

config = load_config()
client = genai.Client()

MAX_SUB_RETRY = 2
model_name = config['vision_llm']

llm = client.models.generate_content(
    model=model_name,
    config=types.GenerateContentConfig(
        temperature=0.7,
        top_p=0.95,
        max_output_tokens=1024,
    ),
)


# retrieve node
def retrive_node(state: VerificationSubState) -> VerificationSubState:
    retriver = get_retriever()
    query = f"{state['sub_item']}의 {state['category']} {state['sub_item']} 분리 배출 방법"
    docs = retriver.invoke(query)

    state["regulation_text"] = docs

    return state


# generage node
def generate_node(state: VerificationSubState) -> VerificationSubState:
    prompt = get_generate_prompt(state)
    response = llm.invoke(prompt)
    state["generated_answer"] = response.content

    return state


# judge node
def judgenode(state: VerificationSubState) -> VerificationSubState:
    if state["retry_count"] > MAX_SUB_RETRY : return "END"

    prompt = get_judge_prompt(state)

    verdict = json.loads(llm.invoke(prompt).content)
    state["is_valid"] = verdict["is_valid"]
    state["failure_reason"] = verdict.get("failure_reason", "")

    if not state["is_valid"]:
        state["retry_count"] += 1