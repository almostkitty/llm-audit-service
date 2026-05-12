from collections import Counter
from typing import Any

_INVISIBLE_AND_SPECIAL_SPACES: dict[int, str] = {
    0x00A0: "NBSP",
    0x202F: "NARROW_NBSP",
    0x200B: "ZERO_WIDTH_SPACE",
    0x200C: "ZERO_WIDTH_NON_JOINER",
    0x200D: "ZERO_WIDTH_JOINER",
    0x2060: "WORD_JOINER",
    0xFEFF: "ZWNBSP_OR_BOM",
}

_BIDI_MARKS: dict[int, str] = {
    0x200E: "LRM",
    0x200F: "RLM",
    0x202A: "LRE",
    0x202B: "RLE",
    0x202C: "PDF",
    0x202D: "LRO",
    0x202E: "RLO",
}

_ALL_MARKERS: dict[int, str] = {
    **_INVISIBLE_AND_SPECIAL_SPACES,
    **_BIDI_MARKS,
}


def find_llm_unicode_signals(text: str) -> dict[str, Any]:
    by_label: Counter[str] = Counter()
    by_codepoint_hex: Counter[str] = Counter()

    for ch in text:
        cp = ord(ch)
        label = _ALL_MARKERS.get(cp)
        if label:
            by_label[label] += 1
            by_codepoint_hex[f"U+{cp:04X}"] += 1

    latex_slash_dollar = text.count("\\" + "$")
    latex_slash_tilde = text.count("\\" + "~")

    char_signal = bool(by_label) or bool(latex_slash_dollar or latex_slash_tilde)

    return {
        "has_signals": char_signal,
        "counts_by_label": dict(sorted(by_label.items(), key=lambda x: (-x[1], x[0]))),
        "counts_by_codepoint": dict(sorted(by_codepoint_hex.items(), key=lambda x: (-x[1], x[0]))),
        "categories": {
            "invisible_and_special_spaces": {
                k: by_label[k] for k in _INVISIBLE_AND_SPECIAL_SPACES.values() if k in by_label
            },
            "bidirectional_marks": {k: by_label[k] for k in _BIDI_MARKS.values() if k in by_label},
        },
        "latex_style_escapes": {
            "backslash_dollar": latex_slash_dollar,
            "backslash_tilde": latex_slash_tilde,
        },
        "total_flagged_characters": sum(by_label.values()),
    }
