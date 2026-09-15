from langchain_pinecone import PineconeVectorStore

def upsert_documents(documents, embeddings, index_name: str):
    return PineconeVectorStore.from_documents(
        documents=documents,
        embedding=embeddings,
        index_name=index_name,
    )


def load_existing_index(embeddings, index_name: str):
    return PineconeVectorStore.from_existing_index(
        index_name=index_name,
        embedding=embeddings,
    )

