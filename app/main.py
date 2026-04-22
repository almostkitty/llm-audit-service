from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.templating import Jinja2Templates

from app.api.routes import audit, auth, extract, health
from app.db.session import init_db

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(lifespan=lifespan)
if STATIC_DIR.is_dir():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(health.router)
app.include_router(auth.router)
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


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse(
        request,
        "login.html",
        {"active_page": "login"},
    )


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request):
    return templates.TemplateResponse(
        request,
        "register.html",
        {"active_page": "register"},
    )


@app.get("/account", response_class=HTMLResponse)
def account_page(request: Request):
    return templates.TemplateResponse(
        request,
        "account.html",
        {"active_page": "account"},
    )