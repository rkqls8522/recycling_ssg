from langsmith import Client

_client = Client()

# 2. RULE NODE
def get_rule_prompt(region:str, category:str, sub_item:str, rule:str, exception_type:str=None):
    header = f"[{category} - {sub_item}] 분리배출 안내"
    region_line = f"📍 지역: {region}"
    rule_line = f"♻️ 배출 방법: {rule}"

    lines = [header, region_line, rule_line]

    if exception_type:
        lines.append(f"⚠️ 이 지역만의 예외 규정입니다 ({exception_type})")

    return "\n".join(lines)

# 4. RAG NODE
def get_rag_prompt():
    return _client.pull_prompt("rlm/rag-prompt", dangerously_pull_public_prompt=True)