"""Prompt templates for the stateless AI Agent chat endpoint."""

from __future__ import annotations

CHAT_SYSTEM_PROMPT = """너는 생활폐기물 분리배출 안내를 돕는 한국어 AI 상담원이다.
아래 [분석 컨텍스트]와 [참고 정보]를 바탕으로 사용자의 질문에 간결하고
실행 가능한 답변을 한국어로 제공하라. 확실하지 않은 지역별 세부 규정은
"정확한 사항은 지역 공지를 확인하세요"와 같이 안내하라. 답변은 3~5문장
이내로 작성한다."""


def build_chat_prompt(
    *,
    major_category: str,
    minor_category: str,
    sido_name: str,
    sgg_name: str,
    disposal_day: str | None,
    disposal_method: str | None,
    tips: list[str],
    user_message: str,
) -> str:
    tips_text = "\n".join(f"- {tip}" for tip in tips) or "- (참고 정보 없음)"
    disposal_day_text = disposal_day or "정보 없음"
    disposal_method_text = disposal_method or "정보 없음"

    return f"""{CHAT_SYSTEM_PROMPT}

[분석 컨텍스트]
- 폐기물 대분류: {major_category}
- 폐기물 소분류: {minor_category}
- 사용자 지역: {sido_name} {sgg_name}
- 배출요일: {disposal_day_text}
- 배출방법: {disposal_method_text}

[참고 정보]
{tips_text}

[사용자 질문]
{user_message}

[답변]"""
