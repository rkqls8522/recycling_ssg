from fastapi import FastAPI

from rag.api.routes.disposal import router as disposal_router
from rag.api.routes.reclassify import router as reclassify_router
from rag.api.routes.chat import router as chat_router

app = FastAPI(title="Recycling SSG RAG Service")

app.include_router(disposal_router)
app.include_router(reclassify_router)
app.include_router(chat_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
