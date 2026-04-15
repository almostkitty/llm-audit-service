import json
from typing import Any

import pymupdf4llm


def extract_pdf_as_json(file_path: str) -> str:
    result: Any = pymupdf4llm.to_json(file_path)
    if isinstance(result, str):
        return result
    return json.dumps(result, ensure_ascii=False)


def extract_text_from_pdf(file_path: str) -> str:
    return pymupdf4llm.to_text(file_path)
