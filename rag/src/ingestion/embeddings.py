from langchain_upstage import UpstageEmbeddings

def get_embeddings(model_name):
    return UpstageEmbeddings(model=model_name)