import re

_WORD_RE = re.compile(r"\b[а-яА-Яa-zA-ZёЁ]+\b", re.UNICODE)


def _tokenize_words(text: str) -> list[str]:
    return _WORD_RE.findall(text.lower())


def _ngram_repetition_ratio(words: list[str], n: int) -> float:
    if len(words) < n:
        return 0.0
    ngrams = [tuple(words[i : i + n]) for i in range(len(words) - n + 1)]
    total = len(ngrams)
    if total == 0:
        return 0.0
    unique = len(set(ngrams))
    return 1.0 - (unique / total)


def repetition_score(text: str) -> float:
    words = _tokenize_words(text)
    if len(words) < 2:
        return 0.0

    bi = _ngram_repetition_ratio(words, 2)
    if len(words) < 3:
        return bi

    tri = _ngram_repetition_ratio(words, 3)
    return (bi + tri) / 2.0
