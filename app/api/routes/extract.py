import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.ingestion.docx_reader import extract_text_from_docx
from app.services.ingestion.pdf_reader import extract_text_from_pdf

router = APIRouter()


@router.post("/extract")
async def extract_document(file: UploadFile = File(...)):
    suffix = Path(file.filename or "").suffix.lower()
    content = await file.read()

    if suffix in (".txt", ".text", "") or not suffix:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("utf-8", errors="replace")
        return {"text": text}

    if suffix not in (".pdf", ".docx"):
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются файлы .pdf, .docx или текстовые .txt",
        )

    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(content)
        if suffix == ".pdf":
            text = extract_text_from_pdf(path)
        else:
            text = extract_text_from_docx(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    return {"text": text}
