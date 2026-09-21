from dotenv import load_dotenv
from langchain_pinecone import PineconeVectorStore
from langchain_upstage import UpstageEmbeddings

load_dotenv()
_vectorstore = None

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
def find_national_rule(major_category: str, minor_category: str) -> dict | None:
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
def find_region_rule(major_category: str, minor_category: str, user_region: dict) -> dict | None:
    if user_region.get("sido_name") != "경기도":
        return None

    vs = get_vectorstore()
    results = vs.similarity_search(
        query=minor_category,
        k=10,
        filter={
            "doc_type": "region_exception",
            "major_category": major_category,
            "region": user_region.get("sgg_name"),
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
