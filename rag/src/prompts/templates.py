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


# 3. LLM NODE
def get_llm_prompt():
    return """이 사진 속 폐기물을 분류해주세요.
    
        반드시 아래 [분류 체계]에 있는 대분류/소분류 표현을 "그대로" 사용하세요.
        목록에 없는 표현을 새로 만들어내지 마세요. 애매하면 가장 가까운 항목을 고르세요.
        반드시 한국어로만 답변하세요. 영어를 절대 섞지 마세요.
    
        [분류 체계]
        - 고철류: 고철, 골프채, 비철금속, 전기프라이팬, 주전자, 철옷걸이, 프라이팬
        - 나무: 기타, 나무행거, 도마, 액자, 장식품, 주걱, 주방용품, 포장재
        - 도기류: 그릇류, 뚝배기, 받침, 병, 장식품, 주전자, 컵, 항아리, 화분
        - 비닐: 과자봉지, 리필용기, 봉투, 에어캡, 일회용덮개, 포장제
        - 스티로폼: 네모트레이, 보호재, 스티로폼, 포장용기
        - 유리병: 맥주병, 물병, 박카스병, 소주병, 음료수병, 주방용기
        - 의류: 레깅스, 면의류, 상의, 외투, 원피스, 하의, 합성섬유
        - 종이류: 노트, 상자류, 신문지, 신발상자, 음료수곽, 종이봉투, 책자, 포장상자
        - 캔류: 캔, 스팸류, 통조림캔
        - 페트병: 일회용음료수잔, 페트병
        - 플라스틱류: 대용량플라스틱통, 밀폐용기, 바구니, 욕실용품, 장난감
        - 형광등: 전구, 형광등
    
        반드시 아래 JSON 형식으로만 답변하세요. 다른 설명은 절대 추가하지 마세요.
    
        {"category": "위 목록의 대분류 중 하나", "sub_item": "위 목록의 소분류 중 하나"}"""


# 4. RAG NODE
def get_rag_prompt():
    return _client.pull_prompt("rlm/rag-prompt", dangerously_pull_public_prompt=True)