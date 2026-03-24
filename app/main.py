from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from app.api.routes import audit, extract


app = FastAPI()
app.include_router(audit.router)
app.include_router(extract.router)

@app.get("/")
def root():
    return {"message": "LLM Audit Service is running"}


@app.get("/demo")
def demo_page():
    demo_path = Path(__file__).parent / "templates" / "demo.html"
    return FileResponse(demo_path)


@app.get("/extract")
def extract_page():
    path = Path(__file__).parent / "templates" / "extract.html"
    return FileResponse(path)