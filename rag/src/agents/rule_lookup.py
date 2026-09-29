from functools import lru_cache

from dotenv import load_dotenv
from langchain_pinecone import PineconeVectorStore
from langchain_upstage import UpstageEmbeddings

load_dotenv()
_vectorstore = None

# 규정 조회 1건은 Upstage 임베딩 API + Pinecone 검색으로 네트워크를 2~3회 왕복하므로
# 실측 ~2초가 걸린다(analyze 응답에서 DB 다음으로 큰 비중). 그런데 결과를 결정하는
# 입력은 (major_category, minor_category) [+ 경기도면 sgg_name] 뿐이고, 분류기가
# 내놓는 클래스는 17개로 고정이라 조합이 유한하다. 같은 물건을 다시 물어볼 이유가
# 없으므로 프로세스 메모리에 캐시한다.
#
#   - national_rule: 지역과 무관 -> 17개 클래스만 채워지면 전국 모든 사용자가 적중
#   - region_rule  : 경기도 시군구마다 다르므로 sgg_name 까지 캐시 키에 포함
#
# Pinecone 인덱스는 인제스션 시점에 고정되므로 런타임 무효화가 필요 없다. 인덱스를
# 다시 적재했다면 RAG 프로세스를 재시작하면 캐시도 함께 비워진다.
_RULE_CACHE_SIZE = 1024


def get_vectorstore():
    global _vectorstore
    if _vectorstore is None:
        _vectorstore = PineconeVectorStore.from_existing_index(
            index_name="recycling-ssg",
            embedding=UpstageEmbeddings(model="solar-embedding-2-passage"),
        )
    return _vectorstore


def merge_method(method: str | None, byeolpyo1_method: str | None) -> str | None:
    parts = [p for p in [method, byeolpyo1_method] if p]
    return "\n\n".join(parts) if parts else None


# 1. national_rule: 사전 method + 별표1 byeolpyo1_method를 합쳐서 반환
#    분류기(YOLO) 86개 세부 클래스와 RAG 데이터의 minor_category는 세분화 기준이 달라서
#    (예: "박카스병"/"맥주병"/"소주병"/"물병" 전부 RAG엔 "음료수병" 하나로만 있음) 정확히
#    일치하는 minor_category가 없을 수 있다. 그럴 땐 같은 major_category 안에서 minor_category
#    텍스트와 의미상 가장 가까운 항목으로 대체한다(임베딩 유사도 검색 본연의 방식).
#
#    캐시된 dict 를 그대로 돌려주면 호출부가 실수로 수정했을 때 캐시가 오염되므로 복사본을
#    반환한다(현재 호출부는 읽기만 하지만, 값이 싸고 사고를 원천 차단한다).
def find_national_rule(major_category: str, minor_category: str) -> dict | None:
    cached = _find_national_rule_uncached(major_category, minor_category)
    return dict(cached) if cached is not None else None


@lru_cache(maxsize=_RULE_CACHE_SIZE)
def _find_national_rule_uncached(major_category: str, minor_category: str) -> dict | None:
    vs = get_vectorstore()
    results = vs.similarity_search(
        query=minor_category,
        k=1,
        filter={
            "doc_type": "national_law",
            "major_category": major_category,
            "minor_category": minor_category,
        },
    )
    if not results:
        # 정확히 일치하는 minor_category가 없으면 major_category 내에서 의미상 최선 매칭으로 폴백
        results = vs.similarity_search(
            query=minor_category,
            k=1,
            filter={"doc_type": "national_law", "major_category": major_category},
        )
    if not results:
        return None
    md = results[0].metadata
    return {
        "item": md.get("byeolpyo1_item") or md.get("item"),
        "source": md.get("source", "기후에너지환경부"),
        "method": merge_method(md.get("method"), md.get("byeolpyo1_method")),
    }


# 2. region_rule: 경기도 지자체 예외
#    우선순위: minor_category 정확 일치 -> major_category 전체에 적용되는 예외(minor_category
#    없음) -> 그래도 없으면 같은 major_category+지역 안에서 의미상 가장 가까운 항목(results[0]).
#    national_rule과 마찬가지로 분류기 세부 클래스와 RAG minor_category가 안 맞는 경우를 위한 폴백.
#
#    경기도 게이트는 캐시 바깥에 둔다. 경기도가 아니면 애초에 조회 자체가 없어 캐시할 것이
#    없고, user_region dict 는 (unhashable 이라) 캐시 키로 쓸 수도 없기 때문이다.
def find_region_rule(major_category: str, minor_category: str, user_region: dict) -> dict | None:
    if user_region.get("sido_name") != "경기도":
        return None
    cached = _find_region_rule_uncached(
        major_category, minor_category, user_region.get("sgg_name")
    )
    return dict(cached) if cached is not None else None


@lru_cache(maxsize=_RULE_CACHE_SIZE)
def _find_region_rule_uncached(
    major_category: str, minor_category: str, sgg_name: str | None
) -> dict | None:
    vs = get_vectorstore()
    results = vs.similarity_search(
        query=minor_category,
        k=10,
        filter={
            "doc_type": "region_exception",
            "major_category": major_category,
            "region": sgg_name,
        },
    )
    if not results:
        return None

    exact = [d for d in results if d.metadata.get("minor_category") == minor_category]
    broad = [d for d in results if "minor_category" not in d.metadata]
    doc = (exact or broad or results)[0]

    md = doc.metadata
    return {
        "region": md.get("region"),
        "source_url": md.get("source_url"),
        "exception_type": md.get("exception_type"),
        "method": doc.page_content,
    }


# 캐시 상태 점검용(시연 전 프리워밍이 제대로 됐는지 확인).
def rule_cache_info() -> dict:
    return {
        "national": _find_national_rule_uncached.cache_info()._asdict(),
        "region": _find_region_rule_uncached.cache_info()._asdict(),
    }
