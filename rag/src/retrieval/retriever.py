def get_retriever(vector_store, k: int = 3):
    return vector_store.as_retriever(search_kwargs={"k": k})
