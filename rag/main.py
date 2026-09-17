from fastapi import FastAPI

from rag.api.routes.disposal import router as disposal_router

app = FastAPI(title="Recycling SSG RAG Service")

app.include_router(disposal_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
