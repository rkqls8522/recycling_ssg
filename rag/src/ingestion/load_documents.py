# 1️⃣ Loading 작업 : tagged JSON file -> list of Document objects (공통문서)

import json
from langchain_core.documents import Document
from pathlib import Path

CURRENT_DIR = Path(__file__).resolve().parent  # rag/src/data
RAG_ROOT = CURRENT_DIR.parent.parent            # rag

json_path = RAG_ROOT / "data" / "metadata" / "waste_baseline_tagged.json"

def load_documents(file_path:str) -> list[Document]:
    with open(file_path,  encoding="utf-8") as f:  
        records = json.load(f)

    return [
        Document(page_content=r["page_content"], metadata=r["metadata"]) for r in records
    ]


