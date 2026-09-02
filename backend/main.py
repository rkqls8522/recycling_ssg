# backend/src/backend/main.py

from fastapi import FastAPI

app = FastAPI(
    title="recycling_ssg API",
    version="0.1.0",
)


@app.get("/health")
def health_check():
    return {"status": "ok"}