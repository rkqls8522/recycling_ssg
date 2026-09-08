
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from typing_extensions import List, TypedDict
from langchain_core.documents import Document
from src.prompts.templates import get_rag_prompt
from configs.config import load_config

config = load_config()

# State 생성하기
class AgentState(TypedDict):
    query: str # 사용자의 질문
    context : List[Document] # LLM이 답변에 참고할 문서
    region : str
    answer: str 


# retrieve node
def make_retrieve_node(retriever):
    def retrieve(state: AgentState):
        query = state["query"]
        region = state["region"]
        k=config["retriever_k"]
        filter_dict = {"region": region} if region else None
        docs = retriever.vectorstore.similarity_search(query, k=k, filter=filter_dict)

        return {"context":docs}
    return retrieve


# generage node
def make_generate_node(model_name:str):
    llm = ChatNVIDIA(
    model=model_name,
    temperature=0.7,
    top_p=0.95,
    max_tokens=1024,
    chat_template_kwargs={"enable_thinking":False},
    )
    prompt = get_rag_prompt()

    def generate(state: AgentState):
        context = state['context']
        query = state['query']
        rag_chain = prompt | llm
        response = rag_chain.invoke({'question':query, 'context': context})
        return {'answer' : response}

    return generate

