from rag.src.agents.state import AgentState
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.messages import HumanMessage
from rag.src.prompts.templates import get_llm_prompt


def make_classify_node(model_name:str):
    llm = ChatGoogleGenerativeAI(
        model = model_name,
        temperature=0.2,
        max_output_tokens=300
    )
    prompt = get_llm_prompt()

    def classify_node(state: AgentState):
        img_url = state['img_url']
        classify_chain = prompt | llm
        response = classify_chain.invoke({'img_url' : img_url})
        return {'answer' : response}

    return classify_node
        
