"""
artifact_writer.py

Shared helper for PM and Marketing agents to produce human-readable
markdown artifacts (roadmaps, campaign briefs, etc.).

Design:
  * render_*        -> pure functions that turn agent data into a markdown string
  * write_artifact  -> persists the markdown file locally and records an event
                       in the shared project log
  * publish_artifact-> sends an ARTIFACT_PUBLISHED message to CEO through the
                       enterprise router so the rest of the system knows the
                       artifact exists.  S3 upload and database persistence are
                       stubbed as TODO comments and will slot in here later
                       without any caller changes.

Artifacts are written to ARTIFACTS_DIR (default "artifacts/").
publish_artifact() is live: it uses agent_transport.submit(), which routes
through the Enterprise Router when credentials are present and falls back to
the local MessageBus in offline/demo mode (ENTERPRISE_ROUTER_OFFLINE_DEMO=1).
"""

from __future__ import annotations

import logging
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from pm_storage import storage

ARTIFACTS_DIR = os.getenv("ARTIFACTS_DIR", "artifacts")

logger = logging.getLogger(__name__)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slug(value: str) -> str:
    """Filesystem-safe slug for filenames/dirs."""
    cleaned = re.sub(r"[^a-zA-Z0-9._-]+", "-", (value or "").strip()).strip("-")
    return cleaned.lower() or "untitled"


def write_artifact(
    *,
    agent: str,
    name: str,
    content: str,
    project_id: Optional[str] = None,
    extension: str = "md",
) -> Dict[str, Any]:
    """
    Persist a markdown artifact locally and record it in the shared event log.

    Layout: ARTIFACTS_DIR/<agent>/<project_id or "_general">/<name>.<ext>
    Returns metadata dict: {path, agent, name, project_id, created_at}.
    """
    project_dir = _slug(project_id) if project_id else "_general"
    target_dir = Path(ARTIFACTS_DIR) / _slug(agent) / project_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    file_path = target_dir / f"{_slug(name)}.{extension}"
    file_path.write_text(content, encoding="utf-8")

    metadata: Dict[str, Any] = {
        "path": str(file_path),
        "agent": agent,
        "name": name,
        "project_id": project_id,
        "created_at": _utc_now(),
    }

    # Record in the shared project timeline so the UI/observability layer
    # can see that this artifact was produced.
    try:
        storage.add_project_event(
            source=agent,
            event_type="artifact_written",
            project_id=project_id,
            details={"name": name, "path": metadata["path"]},
        )
    except Exception:
        # Storage logging must never block artifact creation.
        pass

    return metadata


def publish_artifact(
    metadata: Dict[str, Any],
    *,
    source_msg: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Notify the enterprise that an artifact has been produced.

    Sends an ARTIFACT_PUBLISHED message to CEO via the enterprise router,
    carrying the same correlation context (source_message_id, run_id,
    project_id) required by the Enterprise Router Implementation Guide.

    Parameters
    ----------
    metadata   : dict returned by write_artifact()
    source_msg : the inbound message that triggered this artifact, used to
                 populate source_message_id and run_id in the outbound context.
                 If omitted those fields are left empty.

    Current behaviour (Phase 1)
    ---------------------------
    Sends ARTIFACT_PUBLISHED to CEO through agent_transport.submit().

    Future behaviour (Phase 2 — stubs below)
    -----------------------------------------
    1. Upload the local file to S3; capture the object URL.
    2. Persist {project_id, agent, name, url} in the shared database.
    3. Include the s3_url in the router message payload.

    This function is intentionally non-fatal: errors are logged as warnings
    and never re-raised, so the calling agent's primary work is never blocked.
    """
    try:
        from agent_transport import AGENT_CEO, submit
        from message_schema import Message
    except ImportError as exc:
        logger.warning("publish_artifact: transport layer unavailable — %s", exc)
        return metadata

    agent      = metadata.get("agent", "unknown")
    name       = metadata.get("name", "artifact")
    project_id = metadata.get("project_id")
    path       = metadata.get("path", "")
    created_at = metadata.get("created_at", _utc_now())

    # ------------------------------------------------------------------
    # TODO (Phase 2): Upload `path` to S3.
    # Example (pseudocode):
    #   s3_url = s3_client.upload(path, bucket=S3_BUCKET, key=s3_key)
    #   metadata["s3_url"] = s3_url
    # ------------------------------------------------------------------

    # ------------------------------------------------------------------
    # TODO (Phase 2): Persist artifact record in the shared database.
    # Example (pseudocode):
    #   db.artifacts.insert({
    #       "project_id": project_id, "agent": agent,
    #       "name": name, "url": s3_url, "created_at": created_at,
    #   })
    # ------------------------------------------------------------------

    # Build correlation context from the inbound message that triggered
    # this artifact, exactly as the router guide requires.
    inbound: Dict[str, Any] = source_msg or {}
    inbound_ctx: Dict[str, Any] = inbound.get("context", {}) if isinstance(inbound, dict) else {}

    context: Dict[str, Any] = {}
    if project_id:
        context["project_id"] = project_id
    source_message_id = inbound.get("id", "")
    if source_message_id:
        context["source_message_id"] = source_message_id
    run_id = inbound_ctx.get("run_id", "")
    if run_id:
        context["run_id"] = run_id

    try:
        msg = Message.create(
            sender=agent,
            recipient=AGENT_CEO,
            task_type="ARTIFACT_PUBLISHED",
            context=context,
            payload={
                "agent": agent,
                "artifact_name": name,
                "local_path": path,
                # Phase 2: add "s3_url": metadata.get("s3_url") here.
                "created_at": created_at,
            },
        )
        submit(msg)
        logger.info(
            "publish_artifact: ARTIFACT_PUBLISHED sent to CEO "
            "(agent=%s, name=%s, project_id=%s, source=%s)",
            agent, name, project_id, source_message_id or "n/a",
        )
    except Exception as exc:
        logger.warning(
            "publish_artifact: failed to notify CEO of artifact '%s' — %s",
            name, exc,
        )

    return metadata


# ---------------------------------------------------------------------------
# Domain renderers — pure functions, no I/O
# ---------------------------------------------------------------------------

def _feature_lines(features: List[Any]) -> str:
    lines = []
    for f in features:
        if isinstance(f, dict):
            nm = f.get("name", "Unnamed feature")
            impact = f.get("impact")
            lines.append(f"- {nm}" + (f" _(impact: {impact})_" if impact else ""))
        else:
            lines.append(f"- {f}")
    return "\n".join(lines) if lines else "- _(none)_"


def render_roadmap_md(
    product: str,
    goal: str,
    prioritized: Dict[str, List[Any]],
) -> str:
    """Turn a MoSCoW-prioritized backlog into a readable roadmap document."""
    created = _utc_now()
    return (
        f"# Product Roadmap — {product}\n\n"
        f"_Generated by PM agent on {created}_\n\n"
        f"## Goal\n\n{goal or '_(no goal provided)_'}\n\n"
        f"## Must have\n\n{_feature_lines(prioritized.get('must', []))}\n\n"
        f"## Should have\n\n{_feature_lines(prioritized.get('should', []))}\n\n"
        f"## Could have\n\n{_feature_lines(prioritized.get('could', []))}\n\n"
        f"## Won't have (this cycle)\n\n{_feature_lines(prioritized.get('wont', []))}\n"
    )


def render_campaign_brief_md(
    product: str,
    campaign: Dict[str, Any],
    email: Optional[Dict[str, Any]] = None,
    image_prompt: Optional[Dict[str, Any]] = None,
) -> str:
    """Turn a campaign plan (+ optional email/image prompt) into a brief."""
    created = _utc_now()
    email = email or {}
    image_prompt = image_prompt or {}
    parts = [
        f"# Campaign Brief — {product}\n",
        f"_Generated by Marketing agent on {created}_\n",
        "## Overview\n",
        f"- **Tagline:** {campaign.get('tagline', '--')}",
        f"- **Channel:** {campaign.get('channel', '--')}",
        f"- **Budget:** ${campaign.get('budget', 0)}",
        f"- **Expected leads:** {campaign.get('expected_leads', 0)}",
        f"- **Timeline:** {campaign.get('timeline_weeks', '--')} weeks\n",
    ]
    if email:
        parts += [
            "## Launch email\n",
            f"**Subject:** {email.get('subject', '--')}\n",
            (email.get("body", "") or "_(no body)_") + "\n",
        ]
    if image_prompt.get("prompt"):
        parts += [
            "## Suggested visual\n",
            f"- **Prompt:** {image_prompt.get('prompt')}",
            f"- **Size:** {image_prompt.get('suggested_size', '--')}\n",
        ]
    return "\n".join(parts)
