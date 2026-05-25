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


def _artifact_root() -> Path:
    return Path(artifacts_dir()).resolve()


def _artifact_index_path() -> Path:
    return _artifact_root() / "index.jsonl"


def _public_record(record: JsonDict) -> JsonDict:
    return {
        "artifact_id": str(record.get("artifact_id") or ""),
        "agent_name": str(record.get("agent_name") or ""),
        "artifact_type": str(record.get("artifact_type") or "document"),
        "title": str(record.get("title") or "Untitled artifact"),
        "filename": str(record.get("filename") or ""),
        "agent_slug": str(record.get("agent_slug") or agent_slug(str(record.get("agent_name") or ""))),
        "created_at": str(record.get("created_at") or ""),
        "metadata": record.get("metadata") if isinstance(record.get("metadata"), dict) else {},
        "source_message_id": record.get("source_message_id") if record.get("source_message_id") else None,
        "source_task_type": record.get("source_task_type") if record.get("source_task_type") else None,
    }


def _append_index_record(record: JsonDict) -> None:
    root = _artifact_root()
    root.mkdir(parents=True, exist_ok=True)
    index_path = _artifact_index_path()
    with index_path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_public_record(record), default=str) + "\n")


def _read_index_records() -> list[JsonDict]:
    index_path = _artifact_index_path()
    if not index_path.exists():
        return []

    records: list[JsonDict] = []
    for line in index_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(raw, dict):
            public = _public_record(raw)
            if public["artifact_id"] and public["filename"]:
                records.append(public)
    return records


def _artifact_path_from_record(record: JsonDict) -> Path | None:
    root = _artifact_root()
    slug = _slugify(str(record.get("agent_slug") or record.get("agent_name") or ""))
    filename = Path(str(record.get("filename") or "")).name
    if not slug or not filename:
        return None
    candidate = (root / slug / filename).resolve()
    if not candidate.is_relative_to(root):
        return None
    if not candidate.is_file():
        return None
    return candidate


def _record_from_markdown(path: Path) -> JsonDict | None:
    root = _artifact_root()
    try:
        resolved = path.resolve()
        if not resolved.is_relative_to(root) or not resolved.is_file():
            return None
        text = resolved.read_text(encoding="utf-8")
    except OSError:
        return None

    title = resolved.stem
    for line in text.splitlines():
        if line.startswith("# "):
            title = line[2:].strip() or title
            break

    artifact_id_match = re.search(r"(art-[a-f0-9]+)", resolved.name)
    artifact_id = artifact_id_match.group(1) if artifact_id_match else f"file-{resolved.stem}"
    slug = resolved.parent.name
    return {
        "artifact_id": artifact_id,
        "agent_name": slug.replace("-", " ").title(),
        "artifact_type": "document",
        "title": title,
        "filename": resolved.name,
        "agent_slug": slug,
        "created_at": datetime.fromtimestamp(resolved.stat().st_mtime, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "metadata": {},
        "source_message_id": None,
        "source_task_type": None,
    }


def _scan_markdown_records() -> list[JsonDict]:
    root = _artifact_root()
    if not root.exists():
        return []
    records: list[JsonDict] = []
    for path in root.glob("*/*.md"):
        record = _record_from_markdown(path)
        if record:
            records.append(record)
    return records


def list_agent_artifacts(
    *, agent_name: str | None = None, limit: int = 20
) -> list[JsonDict]:
    """List artifact metadata without exposing local filesystem paths."""
    indexed = _read_index_records()
    seen = {record["artifact_id"] for record in indexed}
    records = indexed + [
        record for record in _scan_markdown_records() if record["artifact_id"] not in seen
    ]

    if agent_name:
        slug = agent_slug(agent_name)
        records = [
            record
            for record in records
            if agent_slug(str(record.get("agent_name") or "")) == slug
            or str(record.get("agent_slug") or "") == slug
        ]

    indexed_order = {record["artifact_id"]: i for i, record in enumerate(indexed)}
    records.sort(
        key=lambda record: (
            str(record.get("created_at") or ""),
            indexed_order.get(str(record.get("artifact_id") or ""), -1),
        ),
        reverse=True,
    )
    return records[: max(0, int(limit))]


def get_agent_artifact(artifact_id: str) -> JsonDict | None:
    """Return one artifact with markdown content, or None when not found/safe."""
    target = (artifact_id or "").strip()
    if not target:
        return None

    for record in list_agent_artifacts(agent_name=None, limit=10_000):
        if record.get("artifact_id") != target:
            continue
        path = _artifact_path_from_record(record)
        if path is None:
            return None
        try:
            content = path.read_text(encoding="utf-8")
        except OSError:
            return None
        return {**_public_record(record), "content": content}
    return None


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
    source_message_id: Optional[str] = None,
    source_task_type: Optional[str] = None,
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
        "agent_slug": slug,
        "created_at": created_at,
        "metadata": metadata or {},
        "source_message_id": source_message_id,
        "source_task_type": source_task_type,
    }
    _append_index_record(record)

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
