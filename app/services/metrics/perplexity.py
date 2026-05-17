"""
Перплексия по произвольной causal LM из HuggingFace.

По умолчанию в проекте: **ai-forever/mGPT** (~1.3B, хорошо по-русски; тяжелее по памяти и времени).

Легче для CPU/Colab без GPU: ``PERPLEXITY_MODEL_NAME=ai-forever/rugpt3small_based_on_gpt2``
(семейство ruGPT3 на GPT-2, дообучено на русском).
"""

import math
import os
from functools import lru_cache


DEFAULT_MODEL_NAME = "ai-forever/mGPT"


def _dtype_env_key() -> str:
    """Нормализованное значение PERPLEXITY_TORCH_DTYPE для ключа кэша загрузки."""
    return (os.getenv("PERPLEXITY_TORCH_DTYPE") or "").strip().lower()


def _torch_dtype_from_key(torch, key: str):
    if key in ("float16", "fp16"):
        return torch.float16
    if key in ("bfloat16", "bf16"):
        return torch.bfloat16
    if key in ("float32", "fp32"):
        return torch.float32
    return None


@lru_cache(maxsize=8)
def _load_model_and_tokenizer(model_name: str, dtype_key: str):
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
    td = _torch_dtype_from_key(torch, dtype_key)
    load_kw = {}
    if td is not None:
        load_kw["torch_dtype"] = td
    model = AutoModelForCausalLM.from_pretrained(model_name, **load_kw)
    model.eval()

    device = _resolve_torch_device(torch)
    model.to(device)
    return model, tokenizer, device, torch


def _resolve_torch_device(torch) -> str:
    forced = (os.getenv("PERPLEXITY_DEVICE") or "").strip().lower()
    if forced in ("cuda", "mps", "cpu"):
        return forced
    if torch.cuda.is_available():
        return "cuda"
    if hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return "mps"
    return "cpu"


def _positive_int_env(name: str, default: int) -> int:
    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        v = int(raw)
    except ValueError:
        return default
    return max(1, v)


def perplexity(
    text: str,
    *,
    model_name: str | None = None,
    stride: int = 512,
) -> float:
    if not text or not text.strip():
        return 0.0

    model_name = model_name or os.getenv("PERPLEXITY_MODEL_NAME", DEFAULT_MODEL_NAME)
    model, tokenizer, device, torch = _load_model_and_tokenizer(
        model_name, _dtype_env_key()
    )

    ids = tokenizer.encode(text, add_special_tokens=False)
    seq_len = len(ids)
    input_ids = torch.tensor([ids], dtype=torch.long, device=device)

    max_len = int(
        getattr(model.config, "n_positions", None)
        or getattr(model.config, "max_position_embeddings", 1024)
    )
    forward_cap = _positive_int_env("PERPLEXITY_MAX_FORWARD_TOKENS", 0)
    if forward_cap > 0:
        max_len = min(max_len, forward_cap)

    stride_use = _positive_int_env("PERPLEXITY_STRIDE", stride)
    # при ограничении окна шаг не должен превышать его иначе пропускаются позиции
    stride_use = min(stride_use, max_len)

    nlls = []
    prev_end = 0

    for begin in range(0, seq_len, stride_use):
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
        if device == "mps":
            try:
                torch.mps.empty_cache()
            except AttributeError:
                pass
        prev_end = end
        if end == seq_len:
            break

    ppl = torch.exp(torch.stack(nlls).sum() / seq_len).item()
    if math.isinf(ppl) or math.isnan(ppl):
        return 0.0
    return float(ppl)
