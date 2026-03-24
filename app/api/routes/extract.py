import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from app.services.ingestion.docx_reader import extract_text_from_docx
from app.services.ingestion.odt_reader import extract_text_from_odt
from app.services.ingestion.pdf_reader import extract_text_from_pdf
from app.services.ingestion.rtf_reader import extract_text_from_rtf

router = APIRouter()

_SUPPORTED = (
    ".pdf",
    ".docx",
    ".rtf",
    ".odt",
)


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

    if suffix not in _SUPPORTED:
        raise HTTPException(
            status_code=400,
            detail="Поддерживаются: .pdf, .docx, .rtf, .odt и текстовые .txt",
        )

    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "wb") as tmp:
            tmp.write(content)

        if suffix == ".pdf":
            text = extract_text_from_pdf(path)
        elif suffix == ".docx":
            text = extract_text_from_docx(path)
        elif suffix == ".rtf":
            text = extract_text_from_rtf(path)
        else:
            text = extract_text_from_odt(path)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

    return {"text": text}
