import json
import os
import logging
from urllib import error, request

logger = logging.getLogger(__name__)


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


def _try_ollama(prompt: str):
    try:
        from ollama import chat

        res = chat(model='mistral', messages=[{'role': 'user', 'content': prompt}])
        return res.message.content.strip()
    except Exception:
        return None


def _try_openai_compatible(prompt: str):
    base_url = os.getenv("OPENAI_BASE_URL")
    api_key = os.getenv("OPENAI_API_KEY")
    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    if not base_url or not api_key:
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
            message = choices[0].get("message", {})
            content = message.get("content")
            if not isinstance(content, str):
                return None
            return content.strip()
    except (error.URLError, error.HTTPError, ValueError, TimeoutError) as exc:
        logger.warning("OpenAI-compatible provider request failed: %s", exc)
        return None


def llm_json_array(prompt: str):
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
    return None


def llm_json_object(prompt: str):
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
    return None