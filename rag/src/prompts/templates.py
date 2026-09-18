from rag.src.agents.state import VerificationSubState


# 3. LLM NODE
from langchain_core.prompts import ChatPromptTemplate

def get_llm_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("human", [
            {
                "type": "text",
                "text": (
                    "이 사진 속 폐기물을 분류해주세요.\n\n"
                    "반드시 아래 [분류 체계]에 있는 대분류/소분류 표현을 \"그대로\" 사용하세요.\n"
                    "목록에 없는 표현을 새로 만들어내지 마세요. 애매하면 가장 가까운 항목을 고르세요.\n"
                    "반드시 한국어로만 답변하세요. 영어를 절대 섞지 마세요.\n"
                    "{failure_reason_section}\n"
                    "[분류 체계]\n"
                    "- 고철류: 고철, 비철금속\n"
                    "- 나무: 나무\n"
                    "- 도기류: 도기\n"
                    "- 비닐: 비닐\n"
                    "- 스티로폼: 스티로폼\n"
                    "- 유리병: 유리병\n"
                    "- 의류: 의류\n"
                    "- 종이류: 책, 박스류, 신문지, 종이\n"
                    "- 캔류: 캔\n"
                    "- 페트병: 페트병\n"
                    "- 플라스틱류: 플라스틱, 장난감\n"
                    "- 형광등: 전구\n"
                ),
            },
            {
                "type": "image_url",
                "image_url": "{img_url}",
            },
        ]),
    ])


# 4-1. RAG GENERATE NODE
def get_generate_prompt(state: VerificationSubState):
    retry_note = (f"이전 시도 실패 이유 : {state['failure_reason']} -> 이 문제를 반영해 다시 작성하세요."
                  if state.get("failure_reason") else "")
    
    return (f"""
    아래의 작성 예시를 참고하여 제공된 배출정보로만 근거로 사용자에게 안내할 배출방법과 주의사항을 작성예시를 참고하여 작성하세요.
    정보에 없는 내용은 추가하지 마세요.

    [배출 지역]
    {state['region']}
    [배출 정보]
    {state["regulation_text"]}, {state["sub_item"]}
    {retry_note}

    [작성 예시]
    1. 
    {"배출 방법" : ["이물질·스티커를 제거해 주세요","깨끗한 상태에서 스티로폼 전용 수거함에 배출하세요"]}
    {"주의사항" : ["오염된 스티로폼 -> 종량제 봉투", "색스티로폼·은박 완충재 -> 종량제 봉투"]}
    2. 
    {"배출 방법" : ["내용물을 비우고 행궈 주세요","라벨과 뚜껑을 분리해 주세요", "투명 페트병 전용 수거함에 배출하세요"]}
    {"주의사항" : ["색이 있는 페트병은 플라스틱류 수거함 배출"]}
    """)


# 4-2. RAG JUDGE NODE
def get_judge_prompt(state: VerificationSubState):
    return (f"""
    [원본데이터] {state['regulation_text']} 
    [생성된 답변] {state['generated_answer']}

    생성된 답변이 원본 데이터에 없는 내용을 포함하면 false로 판정하세요
    JSON으로만 응답 {{"is_valid": bool, "failure_reason": string}}
    """)