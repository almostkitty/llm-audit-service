from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api.deps import get_current_user
from app.api.routes.reports import save_last_report
from app.db.models import User
from app.db.session import get_session
from app.services.analyzer import analyze_text
from app.services.audit_history import audit_check_to_dict, record_audit_check
from app.services.preprocessing.vkr_text import clean_thesis_text

router = APIRouter()


class ThesisCleanRequest(BaseModel):
    """Сырой текст документа (как после /extract)."""

    text: str = Field(..., min_length=1)


@router.post("/audit")
async def audit_file(
    session: Annotated[Session, Depends(get_session)],
    user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
    chars_before: Annotated[int | None, Form()] = None,
):
    content = await file.read()
    text = content.decode("utf-8")
    result = analyze_text(text)
    assert user.id is not None
    char_before: int | None = None
    if chars_before is not None and chars_before > 0:
        char_before = chars_before
    row, report = record_audit_check(
        session,
        user_id=user.id,
        filename=file.filename,
        text=text,
        audit_result=result,
        char_count_before=char_before,
    )
    save_last_report(user.id, report)
    return {
        **result,
        "check_id": row.id,
        "check": audit_check_to_dict(row),
        "report_id": report["id"],
        "report_url": f"/report/{row.id}",
    }


@router.post("/thesis-clean")
def thesis_clean(payload: ThesisCleanRequest):
    """
    Эвристическая очистка ВКР: от титула/реферата до блока «Введение» или «Глава 1»,
    обрезка библиографии, удаление типичных PDF/DOCX артефактов и похожих на код строк.
    Результат подставляют в поле текста на главной странице перед анализом.
    """
    raw = payload.text
    if not raw.strip():
        raise HTTPException(status_code=422, detail="Пустой текст.")
    parts = clean_thesis_text(raw)
    body = parts.get("text") or ""
    if not body.strip():
        raise HTTPException(
            status_code=422,
            detail="После очистки не осталось текста. Добавьте явный заголовок «Введение» или отредактируйте вручную.",
        )
    return {
        "text": body,
        "abstract_ru": parts.get("abstract_ru"),
        "abstract_en": parts.get("abstract_en"),
        "chars_before": len(raw),
        "chars_after": len(body),
    }
