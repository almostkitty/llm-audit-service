import re


RUSSIAN_STOP_WORDS = {
    "и", "в", "во", "на", "по", "к", "ко", "с", "со", "у", "о", "об",
    "от", "до", "за", "для", "из", "под", "над", "при", "про", "через",
    "а", "но", "или", "либо", "же", "что", "чтобы", "как", "так", "не",
    "ни", "да", "то", "это", "этот", "эта", "эти", "тот", "та", "те",
    "он", "она", "оно", "они", "мы", "вы", "я", "ты", "их", "его", "ее"
}


def stop_word_ratio(text: str) -> float:
    words = re.findall(r"\b[а-яА-Яa-zA-ZёЁ]+\b", text.lower())
    if not words:
        return 0.0

    stop_count = sum(1 for word in words if word in RUSSIAN_STOP_WORDS)
    return stop_count / len(words)
