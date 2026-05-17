from contextlib import asynccontextmanager
from pathlib import Path

from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlmodel import Session
from starlette.templating import Jinja2Templates

from app.api.routes import audit, audit_history, auth, extract, reports, teacher_feedback
from app.api.deps import get_optional_user
from app.api.routes.reports import resolve_report
from app.db.models import User
from app.db.session import get_session, init_db
from app.services.report_builder import DECISION_THRESHOLD
from app.services.teacher_feedback import feedback_to_dict, get_teacher_feedback

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
app.include_router(auth.router)
app.include_router(audit_history.router)
app.include_router(audit.router)
app.include_router(extract.router)
app.include_router(reports.router)
app.include_router(teacher_feedback.router)


@app.get("/health")
def health():
    return {"message": "LLM Audit Service is running"}


def _demo_page_response(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "demo.html",
        {"active_page": "demo"},
    )


@app.get("/", response_class=HTMLResponse)
def home_page(request: Request):
    return _demo_page_response(request)


@app.get("/demo")
def demo_redirect():
    return RedirectResponse(url="/", status_code=307)


@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request):
    return templates.TemplateResponse(
        request,
        "history.html",
        {"active_page": "history"},
    )


@app.get("/report/{report_id}", response_class=HTMLResponse)
def report_page(
    request: Request,
    report_id: str,
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User | None, Depends(get_optional_user)],
):
    if user is None:
        return templates.TemplateResponse(
            request,
            "report.html",
            {
                "active_page": "report",
                "report": None,
                "error": "Войдите в аккаунт, чтобы просматривать отчёты.",
                "login_required": True,
            },
            status_code=401,
        )
    try:
        report = resolve_report(session, report_id, user)
    except HTTPException as exc:
        if exc.status_code not in (status.HTTP_404_NOT_FOUND, status.HTTP_401_UNAUTHORIZED):
            raise
        return templates.TemplateResponse(
            request,
            "report.html",
            {
                "active_page": "report",
                "report": None,
                "error": exc.detail,
                "login_required": False,
            },
            status_code=exc.status_code,
        )
    teacher_feedback_data = None
    if user.role == "teacher" and user.id is not None:
        check_id = str(report.get("id") or report_id)
        if check_id and check_id != "last":
            row = get_teacher_feedback(
                session,
                audit_check_id=check_id,
                teacher_id=user.id,
            )
            if row is not None:
                teacher_feedback_data = feedback_to_dict(row)

    return templates.TemplateResponse(
        request,
        "report.html",
        {
            "active_page": "report",
            "report": report,
            "decision_threshold": DECISION_THRESHOLD,
            "error": None,
            "login_required": False,
            "is_teacher": user.role == "teacher",
            "teacher_feedback": teacher_feedback_data,
        },
    )


@app.get("/info", response_class=HTMLResponse)
def info_page(request: Request):
    return templates.TemplateResponse(
        request,
        "info.html",
        {"active_page": "info"},
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