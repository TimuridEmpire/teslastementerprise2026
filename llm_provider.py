"""
llm_provider.py

LLM provider with Ollama (Mistral) primary and OpenAI-compatible fallback.
Provides structured (JSON) and raw text responses.
"""

from __future__ import annotations

import json
import logging
import os
from urllib import error, request

logger = logging.getLogger(__name__)


# ─── JSON helpers ─────────────────────────────────────────────────────────────

def _extract_json_array(text: str):
    try:
        start = text.index("[")
        end = text.rindex("]") + 1
    except ValueError as exc:
        raise ValueError("Model response does not include a JSON array.") from exc
    raw = text[start:end]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Model response contained an invalid JSON array.") from exc


def _extract_json_object(text: str):
    try:
        start = text.index("{")
        end = text.rindex("}") + 1
    except ValueError as exc:
        raise ValueError("Model response does not include a JSON object.") from exc
    raw = text[start:end]
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("Model response contained an invalid JSON object.") from exc


# ─── Ollama (Mistral) ─────────────────────────────────────────────────────────

def _try_ollama(prompt: str) -> str | None:
    """Try Ollama with Mistral. Returns raw text or None on any failure."""
    try:
        from ollama import chat  # type: ignore[reportMissingModuleSource]

        res = chat(model="mistral", messages=[{"role": "user", "content": prompt}])
        text = res.message.content.strip()
        logger.debug("Ollama (Mistral) responded successfully.")
        return text
    except Exception as exc:
        logger.warning("Ollama (Mistral) unavailable, falling back to OpenAI: %s", exc)
        return None


# ─── OpenAI-compatible fallback ───────────────────────────────────────────────

def _try_openai_compatible(prompt: str) -> str | None:
    """
    Try OpenAI-compatible endpoint (OpenAI, Azure, LM Studio, etc.).
    Requires OPENAI_BASE_URL and OPENAI_API_KEY env vars.
    """
    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

    if not base_url or not api_key:
        logger.warning(
            "OpenAI fallback not configured — set OPENAI_BASE_URL and OPENAI_API_KEY."
        )
        return None

    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
        }
    ).encode("utf-8")

    req = request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
            choices = payload.get("choices", [])
            if not choices:
                return None
            content = choices[0].get("message", {}).get("content")
            if not isinstance(content, str):
                return None
            logger.debug("OpenAI-compatible provider responded successfully.")
            return content.strip()
    except (error.URLError, error.HTTPError, ValueError, TimeoutError) as exc:
        logger.warning("OpenAI-compatible provider request failed: %s", exc)
        return None


# ─── Public API ───────────────────────────────────────────────────────────────

def llm_raw(prompt: str) -> str | None:
    """
    Return raw LLM text. Tries Ollama (Mistral) first, falls back to OpenAI.
    Returns None if both providers fail.
    """
    text = _try_ollama(prompt)
    if text:
        return text
    text = _try_openai_compatible(prompt)
    if text:
        return text
    logger.error("All LLM providers failed for raw prompt.")
    return None


def llm_json_array(prompt: str):
    """
    Return a parsed JSON array from the LLM.
    Tries Ollama (Mistral) first, falls back to OpenAI.
    Returns None if both providers fail or neither returns valid JSON.
    """
    text = _try_ollama(prompt)
    if text:
        try:
            return _extract_json_array(text)
        except Exception as exc:
            logger.warning("Failed to parse Ollama JSON array response: %s", exc)

    text = _try_openai_compatible(prompt)
    if text:
        try:
            return _extract_json_array(text)
        except Exception as exc:
            logger.warning("Failed to parse OpenAI-compatible JSON array response: %s", exc)

    logger.error("All LLM providers failed for JSON array prompt.")
    return None


def llm_json_object(prompt: str):
    """
    Return a parsed JSON object from the LLM.
    Tries Ollama (Mistral) first, falls back to OpenAI.
    Returns None if both providers fail or neither returns valid JSON.
    """
    text = _try_ollama(prompt)
    if text:
        try:
            return _extract_json_object(text)
        except Exception as exc:
            logger.warning("Failed to parse Ollama JSON object response: %s", exc)

    text = _try_openai_compatible(prompt)
    if text:
        try:
            return _extract_json_object(text)
        except Exception as exc:
            logger.warning("Failed to parse OpenAI-compatible JSON object response: %s", exc)

    logger.error("All LLM providers failed for JSON object prompt.")
    return None
