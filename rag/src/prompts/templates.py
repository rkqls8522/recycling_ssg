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
                    "- 형광등: 형광등\n"
                ),
            },
            {
                "type": "image_url",
                "image_url": "{img_url}",
            },
        ]),
    ])


def get_judge_prompt() -> ChatPromptTemplate:
    return ChatPromptTemplate.from_messages([
        ("human", [
            {
                "type": "text",
                "text": (
                    "당신은 생활폐기물 분리배출 이미지 분류 결과를 검증하는 엄격한 검증자입니다.\n"
                    "당신의 역할은 분류가 맞았다고 확인해주는 것이 아니라, 틀렸을 가능성을 적극적으로 찾아내는 것입니다.\n\n"
                    "[검증 기준]\n"
                    "아래 이미지를 보고, 제시된 분류 라벨(대분류: {major_category}, 소분류: {minor_category})이 "
                    "이미지 속 실제 사물과 일치하는지 판단하세요.\n"
                    "- 사물의 종류와 재질이 라벨과 실제로 일치하는지 확인하세요.\n"
                    "- 이미지에 여러 사물이 있다면, 가장 크고 명확하게 보이는 사물을 기준으로 판단하세요.\n"
                    "- 이미지가 흐리거나 사물이 잘 안 보여서 판단이 어려우면, 근거 불충분(false)으로 처리하세요. "
                    "임의로 추측해서 통과시키지 마세요.\n"
                    "- 라벨이 그럴듯해 보인다는 이유만으로 통과시키지 마세요 — 이미지에 실제로 드러난 근거가 있어야 합니다.\n\n"
                    "[출력 지침]\n"
                    "- is_valid: 라벨이 이미지에 명확히 근거하면 true, 아니면 false\n"
                    "- reason: false인 경우 왜 안 맞는지 한두 문장으로 구체적으로 설명하세요 "
                    "(재분류 시 참고할 수 있도록 실질적인 내용으로). true인 경우 빈 문자열."
                ),
            },
            {"type": "image_url", "image_url": "{img_url}"},
        ]),
    ])