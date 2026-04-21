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
    # Длинные ВКР: полный текст кодируем в ids целиком, а в модель подаём только окна ≤ n_positions.
    # Иначе tokenizer предупреждает «sequence length … > max» (7939 > 2048), хотя forward идёт по слайсам.
    tokenizer.model_max_length = 1_000_000
    model = AutoModelForCausalLM.from_pretrained(model_name)
    model.eval()

    device = _resolve_torch_device(torch)
    model.to(device)
    return model, tokenizer, device, torch


def _resolve_torch_device(torch) -> str:
    """
    cuda → Apple MPS → cpu. Переопределение: ``PERPLEXITY_DEVICE=cuda|mps|cpu``.
    На Apple Silicon M2 ``mps`` обычно быстрее, чем чистый CPU (если PyTorch собран с MPS).
    """
    forced = (os.getenv("PERPLEXITY_DEVICE") or "").strip().lower()
    if forced in ("cuda", "mps", "cpu"):
        return forced
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


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

    ids = tokenizer.encode(text, add_special_tokens=False)
    seq_len = len(ids)
    input_ids = torch.tensor([ids], dtype=torch.long, device=device)

    max_len = int(
        getattr(model.config, "n_positions", None)
        or getattr(model.config, "max_position_embeddings", 1024)
    )
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
