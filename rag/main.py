from dotenv import load_dotenv
from src.ingestion.embeddings import get_embeddings
from src.vectorstore.pinecone_vectorstore import load_existing_index
from src.retrieval.retriever import get_retriever
from src.graph import build_graph
from configs.config import load_config

load_dotenv()

def main():
    config = load_config()

    embeddings = get_embeddings(config["embedding_model"])
    vector_store = load_existing_index(embeddings, config["pinecone_index"])
    retriever = get_retriever(vector_store, config["retriever_k"])

    graph = build_graph(retriever, config["llm"])

    query = "보조배터리는 어떻게 재활용해야 하나요?"
    region = '군포시'
    result = graph.invoke({"query": query, "region": region})
    print(result)


if __name__ == "__main__":
    main()