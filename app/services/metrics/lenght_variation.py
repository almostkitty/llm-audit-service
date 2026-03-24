import re

import numpy as np


def word_length_variation(text: str) -> float:
    words = re.findall(r"\b[а-яА-Яa-zA-ZёЁ]+\b", text)
    lengths = [len(word) for word in words]
    if not lengths:
        return 0.0

    return float(np.std(lengths))
