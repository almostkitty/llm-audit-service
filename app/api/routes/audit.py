from fastapi import APIRouter, File, UploadFile

from app.api.routes.reports import save_last_report
from app.services.analyzer import analyze_text

router = APIRouter()


@router.post("/audit")
async def audit_file(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8")
    result = analyze_text(text)
    save_last_report(result)
    return result
