from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from starlette.templating import Jinja2Templates

from app.api.routes import audit, extract, health
from app.db.session import init_db

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
app.include_router(health.router)
app.include_router(audit.router)
app.include_router(extract.router)


@app.get("/")
def root():
    return {"message": "LLM Audit Service is running"}


@app.get("/demo", response_class=HTMLResponse)
def demo_page(request: Request):
    return templates.TemplateResponse(
        request,
        "demo.html",
        {"active_page": "demo"},
    )


@app.get("/info", response_class=HTMLResponse)
def info_page(request: Request):
    return templates.TemplateResponse(
        request,
        "info.html",
        {"active_page": "info"},
    )


@app.get("/extract", response_class=HTMLResponse)
def extract_page(request: Request):
    return templates.TemplateResponse(
        request,
        "extract.html",
        {"active_page": "extract"},
    )