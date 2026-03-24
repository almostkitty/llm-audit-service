from odf import text as odftext
from odf.opendocument import load
from odf.teletype import extractText


def extract_text_from_odt(file_path: str) -> str:
    doc = load(file_path)
    chunks: list[str] = []
    for tag in (odftext.P, odftext.H):
        for el in doc.getElementsByType(tag):
            piece = extractText(el).strip()
            if piece:
                chunks.append(piece)
    return "\n\n".join(chunks)
