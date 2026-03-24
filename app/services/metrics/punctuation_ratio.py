import re


def punctuation_ratio(text: str) -> float:
    if not text:
        return 0.0

    punctuation_count = len(re.findall(r"[.,!?;:()\-\—\"'…]", text))
    char_count = len(text)
    if char_count == 0:
        return 0.0

    return punctuation_count / char_count
