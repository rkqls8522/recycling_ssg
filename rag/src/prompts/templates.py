from langsmith import Client

_client = Client()

def get_rag_prompt():
    return _client.pull_prompt("rlm/rag-prompt", dangerously_pull_public_prompt=True)