# rag/src/ingestion/ingest.py
import sys
import json
from pathlib import Path

from dotenv import load_dotenv
from langchain_core.documents import Document
from langchain_upstage import UpstageEmbeddings


RAG_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = RAG_ROOT / "data" / "metadata"

sys.path.append(str(RAG_ROOT))
from src.vectorstore.pinecone_vectorstore import upsert_documents  

load_dotenv()


# Pinecone은 메타데이터에 null을 허용하지 않으므로 None 값 필드는 제거
def clean_metadata(metadata: dict) -> dict:
    return {k: v for k, v in metadata.items() if v is not None}


# 1. 상위법령 (waste_sorting_dictionary_classified.json) -> Document 리스트
def load_national_law_documents(path: Path) -> list[Document]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    documents = []
    for group in data["dictionary"]:
        for item in group["items"]:
            lines = [f"품목: {item['item']}", f"배출방법: {item['method']}"]
            if item.get("byeolpyo1_method"):
                lines.append(f"[별표1 배출요령]\n{item['byeolpyo1_method']}")
            page_content = "\n".join(lines)

            metadata = {
                "doc_type": "national_law",
                "source": data["source"]["organization"],
                "region": "전국",
                "item": item["item"],
                "major_category": item.get("major_category"),
                "minor_category": item.get("minor_category"),
            }
            documents.append(
                Document(page_content=page_content, metadata=clean_metadata(metadata))
            )
    return documents


# 2. 지자체별규정 (gyeonggi_region_exceptions_processed.json) -> Document 리스트
def load_region_exception_documents(path: Path) -> list[Document]:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)

    return [
        Document(
            page_content=entry["page_content"],
            metadata=clean_metadata(entry["metadata"]),
        )
        for entry in data
    ]


def main():
    national_docs = load_national_law_documents(
        DATA_DIR / "waste_sorting_dictionary_classified.json"
    )
    region_docs = load_region_exception_documents(
        DATA_DIR / "gyeonggi_region_exceptions_processed.json"
    )
    all_documents = national_docs + region_docs

    print(
        f"상위법령 {len(national_docs)}개 + 지자체규정 {len(region_docs)}개 "
        f"= 총 {len(all_documents)}개 업서트"
    )

    embeddings = UpstageEmbeddings(model="solar-embedding-2-passage")
    upsert_documents(all_documents, embeddings, index_name="recycling-ssg")

    print("완료")


if __name__ == "__main__":
    main()