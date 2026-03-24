from fastapi import APIRouter, UploadFile, File
from app.services.analyzer import analyze_text

router = APIRouter()

@router.post("/audit")
async def audit_file(file: UploadFile = File(...)):
    content = await file.read()
    text = content.decode("utf-8")
    result = analyze_text(text)
    return result