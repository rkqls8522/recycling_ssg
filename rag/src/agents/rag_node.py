
from langchain_nvidia_ai_endpoints import ChatNVIDIA
from src.prompts.templates import get_rag_prompt
from configs.config import load_config
from state import AgentState

config = load_config()

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

