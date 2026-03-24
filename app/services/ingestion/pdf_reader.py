import json
from typing import Any

import pymupdf4llm


def extract_pdf_as_json(file_path: str) -> str:
    """Structured PDF extraction as a JSON string (pymupdf4llm layout pipeline)."""
    result: Any = pymupdf4llm.to_json(file_path)
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False)


def extract_text_from_pdf(file_path: str) -> str:
    """Plain text from PDF for the metrics pipeline."""
    return pymupdf4llm.to_text(file_path)
