from pathlib import Path

from striprtf.striprtf import rtf_to_text


def extract_text_from_rtf(file_path: str) -> str:
    raw = Path(file_path).read_bytes()
    for encoding in ("utf-8", "utf-8-sig", "cp1251", "latin-1"):
        try:
            rtf_string = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        rtf_string = raw.decode("utf-8", errors="replace")

    text = rtf_to_text(rtf_string)
    return text.strip()
