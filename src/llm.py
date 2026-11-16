"""All LLM calls go through the Bifrost gateway (OpenAI-compatible API)."""
import json
import os
import re
import threading
import time

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = os.getenv("BIFROST_BASE_URL", "http://localhost:8080/v1")
EXTRACT_MODEL = os.getenv("EXTRACT_MODEL", "openai/gpt-4o-mini")
JUDGE_MODEL = os.getenv("JUDGE_MODEL", "openai/gpt-4o")
FALLBACKS = [m.strip() for m in os.getenv("FALLBACK_MODELS", "").split(",") if m.strip()]

client = OpenAI(base_url=BASE_URL, api_key=os.getenv("BIFROST_API_KEY", "dummy"))

# Per-call telemetry, shown in the UI "Gateway panel"
STATS: list[dict] = []
_lock = threading.Lock()


def reset_stats() -> None:
    with _lock:
        STATS.clear()


def chat(model: str, system: str, user: str, temperature: float = 0.0, stage: str = "") -> str:
    kwargs = dict(
        model=model,
        temperature=temperature,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    if FALLBACKS:
        # Bifrost-specific: automatic failover to these models if the primary fails.
        kwargs["extra_body"] = {"fallbacks": FALLBACKS}

    t0 = time.time()
    resp = client.chat.completions.create(**kwargs)
    latency = time.time() - t0

    usage = getattr(resp, "usage", None)
    # Bifrost reports the provider that actually served the request in extra_fields.provider
    extra = (getattr(resp, "model_extra", None) or {}).get("extra_fields") or {}
    provider = extra.get("provider")
    served = getattr(resp, "model", model)
    if provider and not str(served).startswith(f"{provider}/"):
        served = f"{provider}/{served}"
    with _lock:
        STATS.append(
            {
                "stage": stage,
                "requested_model": model,
                "served_model": served,
                "latency_s": round(latency, 2),
                "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            }
        )
    return resp.choices[0].message.content or ""


def parse_json(text: str) -> dict:
    """Robustly pull a JSON object out of a model reply (handles ``` fences)."""
    text = text.strip()
    text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.DOTALL)
        if m:
            return json.loads(m.group(0))
        raise
