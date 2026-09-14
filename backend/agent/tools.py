"""Lightweight retrieval "tool" the AI Agent uses to ground its answers.

This is a small curated knowledge base keyed by ``major_category``,
standing in for a full RAG pipeline (the spec calls for RAG/Multi-Agent,
SR-26). It is intentionally simple and dependency-free so the chat endpoint
keeps working even without a vector DB: swap ``_TIPS`` for a real retriever
(embeddings + vector search over 지자체 분리배출 가이드) without touching
the call sites in agent/service.py.
"""

from __future__ import annotations

_TIPS: dict[str, list[str]] = {
    "플라스틱류": [
        "내용물을 비우고 물로 헹군 뒤 배출합니다.",
        "다른 재질(라벨, 고무, 금속 부속 등)은 최대한 제거합니다.",
        "라벨이 잘 떨어지지 않으면 가능한 만큼만 제거하고 배출해도 됩니다. 재활용 선별 과정에서 추가로 분리됩니다.",
    ],
    "페트병": [
        "내용물을 비우고 라벨을 제거한 뒤 압착하여 뚜껑을 닫아 배출합니다.",
        "라벨이 잘 떨어지지 않으면 가능한 만큼만 제거하고 배출합니다.",
    ],
    "유리병": [
        "내용물을 비우고 이물질을 제거한 뒤 배출합니다.",
        "깨진 유리는 재활용이 아닌 일반쓰레기(불연성)로 배출해야 하며, 신문지 등으로 감싸 배출합니다.",
    ],
    "캔류": [
        "내용물을 비우고 헹군 뒤 가능하면 압착하여 배출합니다.",
        "스팸 등 기름기가 많은 캔은 물로 헹궈 기름기를 최대한 제거합니다.",
    ],
    "종이류": [
        "물기와 이물질(테이프, 스프링 등)을 제거하고 펼쳐서 배출합니다.",
        "코팅되거나 비닐이 섞인 종이(영수증, 방수코팅 상자 등)는 종이류로 배출하지 않습니다.",
    ],
    "비닐": [
        "이물질과 음식물을 제거한 뒤 배출합니다.",
        "여러 재질이 섞인 비닐(알루미늄 코팅 등)은 종량제 봉투로 배출해야 할 수 있습니다.",
    ],
    "스티로폼": [
        "테이프, 상표 스티커 등 이물질을 제거한 뒤 배출합니다.",
        "음식물이 심하게 오염된 스티로폼(컵라면 용기 등)은 재활용이 아닌 일반쓰레기로 배출합니다.",
    ],
    "고철류": ["다른 재질의 부속품(플라스틱 손잡이 등)은 가능한 범위에서 분리해 배출합니다."],
    "형광등": ["깨지지 않도록 구매 시 포장재에 담아 배출하며, 별도 수거함이 있는 경우 그곳에 배출합니다."],
    "의류": ["헌옷 수거함을 이용하거나 지역 규정에 따라 배출합니다. 오염이 심한 의류는 일반쓰레기로 배출될 수 있습니다."],
    "도기류": ["도자기, 그릇류는 재활용이 아닌 불연성 일반쓰레기로 배출하는 지역이 많습니다. 지역 규정을 확인하세요."],
    "나무": ["대형 목재는 대형폐기물 스티커를 부착해 배출해야 할 수 있습니다."],
}

_DEFAULT_TIPS = ["오염이 심한 경우 재활용이 아닌 일반쓰레기로 배출될 수 있습니다.", "정확한 배출 방법은 지역 규정을 우선 따릅니다."]


def retrieve_tips(major_category: str) -> list[str]:
    return _TIPS.get(major_category, _DEFAULT_TIPS)
