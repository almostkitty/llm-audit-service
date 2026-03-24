import numpy as np

def burstiness(text: str) -> float:
    words = text.split()
    lengths = [len(word) for word in words]
    if not lengths:
        return 0.0
    return float(np.std(lengths))