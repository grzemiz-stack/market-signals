"""Jedyna droga do modeli językowych: lokalna Ollama na pętli zwrotnej (zasada „tylko lokalnie”, ms.netpolicy).

Każdy kod wołający LLM idzie przez `generate()` — tests/test_local_only.py zabrania odwołań do Ollamy i bibliotek
LLM gdziekolwiek indziej. Adres można zmienić zmienną MS_OLLAMA_URL, ale tylko na adres lokalny (inaczej błąd).
LLM wyłącznie klasyfikuje teksty (DECISIONS 2026-10-06), nie prognozuje.
"""

from __future__ import annotations

import os

from ms.netpolicy import is_local

DEFAULT_URL = "http://127.0.0.1:11434"


def base_url() -> str:
    url = os.environ.get("MS_OLLAMA_URL", DEFAULT_URL).rstrip("/")
    if not is_local(url):
        raise RuntimeError(f"LLM tylko lokalnie: {url!r} nie jest adresem 127.0.0.1/localhost")
    return url


def generate(model: str, prompt: str, timeout: float = 600, format: dict | None = None, **options) -> str:
    """Jedno zapytanie do lokalnej Ollamy (/api/generate, bez strumieniowania); zwraca tekst odpowiedzi.
    format: schemat JSON odpowiedzi (wymuszany przez Ollamę); options: temperature, seed, num_ctx itd."""
    import requests

    body = {"model": model, "prompt": prompt, "stream": False, "options": options}
    if format is not None:
        body["format"] = format
    r = requests.post(f"{base_url()}/api/generate", timeout=timeout, json=body)
    r.raise_for_status()
    return r.json()["response"]


def model_digest(model: str) -> str:
    """Digest zainstalowanego modelu (do runs) — z lokalnej Ollamy."""
    import requests

    tags = requests.get(f"{base_url()}/api/tags", timeout=30).json()["models"]
    return next(m["digest"] for m in tags if m["name"] == model)
