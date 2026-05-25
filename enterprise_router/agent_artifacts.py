"""Persist agent deliverables as markdown and poll router prompt envelopes."""

from __future__ import annotations

import json
import re
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from enterprise_paths import artifacts_dir
from message_schema import Message

from .service import EnterpriseRouter

JsonDict = dict[str, Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _slugify(value: str, *, max_len: int = 48) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "artifact").lower()).strip("-")
    if not slug:
        slug = "artifact"
    return slug[:max_len].strip("-") or "artifact"


def agent_slug(agent_name: str) -> str:
    return _slugify(agent_name, max_len=64)


def envelope_prompt_json(envelope: JsonDict) -> JsonDict:
    """
    Normalize prompt-oriented fields from a router envelope for logging or handlers.

    Other agents typically place instructions in ``payload.message``, ``payload.prompt``,
    or ``payload.instruction`` (see ``scripts/initiate_router_workflow.py`` seeds).
    """
    payload = envelope.get("payload") if isinstance(envelope.get("payload"), dict) else {}
    context = envelope.get("context") if isinstance(envelope.get("context"), dict) else {}
    prompt = (
        payload.get("prompt")
        or payload.get("message")
        or payload.get("instruction")
        or payload.get("task")
        or ""
    )
    return {
        "message_id": envelope.get("id"),
        "timestamp": envelope.get("timestamp"),
        "sender": envelope.get("sender"),
        "recipient": envelope.get("recipient"),
        "task_type": envelope.get("task_type"),
        "status": envelope.get("status"),
        "prompt": str(prompt),
        "payload": payload,
        "context": context,
    }


def _format_markdown(
    *,
    agent_name: str,
    title: str,
    body: str,
    artifact_type: str,
    created_at: str,
    metadata: Optional[JsonDict],
) -> str:
    meta_block = ""
    if metadata:
        meta_block = (
            "\n\n## Metadata\n\n```json\n"
            + json.dumps(metadata, indent=2, default=str)
            + "\n```\n"
        )
    return (
        f"# {title}\n\n"
        f"**Agent:** {agent_name}  \n"
        f"**Type:** {artifact_type}  \n"
        f"**Created:** {created_at}  \n\n"
        f"---\n\n"
        f"{body.rstrip()}\n"
        f"{meta_block}"
    )


def write_agent_artifact(
    agent_name: str,
    *,
    title: str,
    body: str,
    artifact_type: str = "document",
    metadata: Optional[JsonDict] = None,
    filename: Optional[str] = None,
    router: Optional[EnterpriseRouter] = None,
) -> JsonDict:
    """
    Write a markdown artifact under ``artifacts/<agent-slug>/``.

    Returns a record with ``path``, ``artifact_id``, and ``filename`` for callers
    (e.g. CEO reasoning loop or website sync).
    """
    name = (agent_name or "agent").strip() or "agent"
    created_at = _utc_now()
    artifact_id = f"art-{uuid.uuid4().hex[:8]}"
    slug = agent_slug(name)
    out_dir = Path(artifacts_dir()) / slug
    out_dir.mkdir(parents=True, exist_ok=True)

    safe_title = _slugify(title, max_len=40)
    safe_type = _slugify(artifact_type, max_len=24)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_name = filename or f"{stamp}_{safe_type}_{safe_title}_{artifact_id}.md"
    out_path = out_dir / out_name

    content = _format_markdown(
        agent_name=name,
        title=title,
        body=body,
        artifact_type=artifact_type,
        created_at=created_at,
        metadata=metadata,
    )
    out_path.write_text(content, encoding="utf-8")

    record: JsonDict = {
        "artifact_id": artifact_id,
        "agent_name": name,
        "artifact_type": artifact_type,
        "title": title,
        "path": str(out_path),
        "filename": out_name,
        "created_at": created_at,
    }

    if router is not None:
        router._audit(
            artifact_id,
            "artifact_written",
            {
                "agent_name": name,
                "artifact_type": artifact_type,
                "path": record["path"],
                "title": title,
            },
            actor=name,
        )

    return record


def poll_one_router_message(
    *,
    recipient: str,
    fetch_next: Callable[[str], Optional[JsonDict]],
    ack: Callable[[str, str], None],
    nack: Callable[[str, str, str], None],
    handler: Callable[[JsonDict], Any],
    log_prompt_json: bool = True,
) -> bool:
    """
    Fetch one leased envelope, optionally log prompt JSON, run ``handler``, then ack/nack.

    Returns True when a message was leased (even if the handler failed and nacked).
    """
    target = (recipient or "").strip()
    envelope = fetch_next(target)
    if envelope is None:
        return False

    Message.validate_envelope(envelope)
    if log_prompt_json:
        print(json.dumps(envelope_prompt_json(envelope)), flush=True)

    message_id = str(envelope.get("id", ""))
    try:
        handler(envelope)
    except Exception as exc:
        if message_id:
            nack(message_id, target, str(exc))
        return True

    if message_id:
        ack(message_id, target)
    return True


def poll_router_prompts_loop(
    *,
    recipient: str,
    fetch_next: Callable[[str], Optional[JsonDict]],
    ack: Callable[[str, str], None],
    nack: Callable[[str, str, str], None],
    handler: Callable[[JsonDict], Any],
    poll_interval_s: float = 2.0,
    log_prompt_json: bool = True,
    once: bool = False,
) -> None:
    """Poll the enterprise router queue until interrupted (or ``once`` is True)."""
    interval = max(0.25, float(poll_interval_s))
    while True:
        processed = poll_one_router_message(
            recipient=recipient,
            fetch_next=fetch_next,
            ack=ack,
            nack=nack,
            handler=handler,
            log_prompt_json=log_prompt_json,
        )
        if once:
            return
        if not processed:
            time.sleep(interval)
