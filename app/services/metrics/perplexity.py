import math
import os
from functools import lru_cache


DEFAULT_MODEL_NAME = "ai-forever/rugpt3small_based_on_gpt2"


@lru_cache(maxsize=2)
def _load_model_and_tokenizer(model_name: str):
    """
    Lazy-load HuggingFace model/tokenizer once per process.
    Import is local to avoid hard dependency unless perplexity is enabled.
    """
    try:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError as exc:
        raise RuntimeError(
            "Perplexity requires 'torch' and 'transformers'. "
            "Install dependencies before enabling it."
        ) from exc

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    model.eval()

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model.to(device)
    return model, tokenizer, device, torch


def perplexity(
    text: str,
    *,
    model_name: str | None = None,
    stride: int = 512,
) -> float:
    """
    Compute causal language model perplexity for input text.

    Notes:
    - Uses sliding-window evaluation for texts longer than model context length.
    - Returns 0.0 for empty/whitespace-only text.
    """
    if not text or not text.strip():
        return 0.0

    model_name = model_name or os.getenv("PERPLEXITY_MODEL_NAME", DEFAULT_MODEL_NAME)
    model, tokenizer, device, torch = _load_model_and_tokenizer(model_name)

    enc = tokenizer(text, return_tensors="pt")
    input_ids = enc["input_ids"].to(device)
    seq_len = input_ids.size(1)

    max_len = getattr(model.config, "n_positions", 1024)
    nlls = []
    prev_end = 0

    for begin in range(0, seq_len, stride):
        end = min(begin + max_len, seq_len)
        trg_len = end - prev_end
        input_slice = input_ids[:, begin:end]
        target_ids = input_slice.clone()
        target_ids[:, :-trg_len] = -100

        with torch.no_grad():
            outputs = model(input_slice, labels=target_ids)
            # outputs.loss is mean CE over valid target tokens.
            neg_log_likelihood = outputs.loss * trg_len

        nlls.append(neg_log_likelihood)
        prev_end = end
        if end == seq_len:
            break

    ppl = torch.exp(torch.stack(nlls).sum() / seq_len).item()
    if math.isinf(ppl) or math.isnan(ppl):
        return 0.0
    return float(ppl)
