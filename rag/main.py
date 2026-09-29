from fastapi import FastAPI

from rag.api.routes.disposal import router as disposal_router
from rag.api.routes.reclassify import router as reclassify_router
from rag.src.agents.rule_lookup import rule_cache_info
from rag.api.routes.chat import router as chat_router

app = FastAPI(title="Recycling SSG RAG Service")

app.include_router(disposal_router)
app.include_router(reclassify_router)
app.include_router(chat_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


# 규정 조회 캐시 적중 현황. 시연 전 프리워밍(scripts/warm_rule_cache.py)이
# 제대로 됐는지 확인하는 용도. RAG 서비스는 127.0.0.1 에만 바인딩되고 Caddy 도
# 프록시하지 않으므로 외부에 노출되지 않는다.
@app.get("/cache_info")
def cache_info() -> dict:
    return rule_cache_info()
