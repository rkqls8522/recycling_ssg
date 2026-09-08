import yaml
from dotenv import load_dotenv

from src.ingestion.load_documents import load_documents
from src.ingestion.embeddings import get_embeddings
from src.vectorstore.pinecone_vectorstore import load_existing_index
from src.retrieval.retriever import get_retriever
from src.graph import build_graph
from pathlib import Path

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "configs" / "settings.yaml"

def load_config() -> dict:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        return yaml.safe_load(f)


def main():
    config = load_config()

    embeddings = get_embeddings(config["embedding_model"])
    vector_store = load_existing_index(embeddings, config["pinecone_index"])
    retriever = get_retriever(vector_store, config["retriever_k"])

    graph = build_graph(retriever, config["llm"])

    query = "군포시 보조배터리는 어떻게 재활용해야 하나요?"
    result = graph.invoke({"query": query})
    print(result)


if __name__ == "__main__":
    main()