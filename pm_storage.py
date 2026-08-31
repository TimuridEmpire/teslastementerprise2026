"""
PM / Marketing business data layer (projects, backlogs, campaigns).

Inter-agent message routing uses ``enterprise_router`` (see ``agent_transport``).
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from enterprise_paths import backlog_db_path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PMStorage:
    """Domain persistence for PM and Marketing agents, backed by a local JSON file.

    Does not handle the enterprise message router queue.
    """

    def __init__(self) -> None:
        default_data_dir = os.path.dirname(backlog_db_path()) or "data"
        self.backlog_path = os.getenv(
            "BACKLOG_PATH", os.path.join(default_data_dir, "pm_backlog.json")
        )
        self.local_store_path = os.getenv(
            "PM_STORAGE_PATH", os.path.join(default_data_dir, "pm_storage.json")
        )
        self._init_file_store()

    def _init_file_store(self) -> None:
        store_dir = os.path.dirname(self.local_store_path)
        if store_dir:
            os.makedirs(store_dir, exist_ok=True)
        if not os.path.exists(self.local_store_path):
            self._write_store({
                "projects": [],
                "project_events": [],
                "backlog_entries": [],
                "campaigns": [],
            })

    def _read_store(self) -> Dict[str, list[Dict[str, Any]]]:
        try:
            with open(self.local_store_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {}
        return {
            "projects": list(data.get("projects") or []),
            "project_events": list(data.get("project_events") or []),
            "backlog_entries": list(data.get("backlog_entries") or []),
            "campaigns": list(data.get("campaigns") or []),
        }

    def _write_store(self, data: Dict[str, list[Dict[str, Any]]]) -> None:
        store_dir = os.path.dirname(self.local_store_path)
        if store_dir:
            os.makedirs(store_dir, exist_ok=True)
        with open(self.local_store_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def _project_doc_to_record(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": doc["_id"],
            "name": doc["name"],
            "goal": doc.get("goal", ""),
            "description": doc.get("description", ""),
            "status": doc.get("status", "active"),
            "payload": doc.get("metadata", {}),
            "created_at": doc["created_at"],
            "updated_at": doc["updated_at"],
        }

    def upsert_project(
        self,
        *,
        name: str,
        goal: str = "",
        payload: Optional[Dict[str, Any]] = None,
        project_id: Optional[str] = None,
        description: Optional[str] = None,
        status: str = "active",
    ) -> Dict[str, Any]:
        metadata = payload or {}
        now = _utc_now()
        resolved_id = project_id or str(uuid.uuid4())
        resolved_description = description or metadata.get("description", "")

        data = self._read_store()
        existing = next((p for p in data["projects"] if p.get("_id") == resolved_id), None)
        if existing:
            existing.update({
                "name": name,
                "goal": goal,
                "description": resolved_description,
                "status": status,
                "metadata": metadata,
                "updated_at": now,
            })
            doc = existing
        else:
            doc = {
                "_id": resolved_id,
                "name": name,
                "goal": goal,
                "description": resolved_description,
                "status": status,
                "metadata": metadata,
                "created_at": now,
                "updated_at": now,
            }
            data["projects"].append(doc)
        self._write_store(data)
        return self._project_doc_to_record(doc)

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        data = self._read_store()
        doc = next((p for p in data["projects"] if p.get("_id") == project_id), None)
        return self._project_doc_to_record(doc) if doc else None

    def find_active_project_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        data = self._read_store()
        matches = [
            p for p in data["projects"]
            if p.get("name") == name and p.get("status", "active") == "active"
        ]
        if not matches:
            return None
        doc = sorted(matches, key=lambda p: str(p.get("updated_at", "")), reverse=True)[0]
        return self._project_doc_to_record(doc)

    def add_project_event(
        self,
        *,
        source: str,
        event_type: str,
        project_id: Optional[str] = None,
        message_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        now = _utc_now()
        data = self._read_store()
        data["project_events"].append(
            {
                "_id": str(uuid.uuid4()),
                "project_id": project_id,
                "source": source,
                "event_type": event_type,
                "message_id": message_id,
                "details": details or {},
                "created_at": now,
            }
        )
        if project_id:
            for project in data["projects"]:
                if project.get("_id") == project_id:
                    project["updated_at"] = now
                    break
        self._write_store(data)

    def save_backlog(
        self,
        project_id: Optional[str],
        prioritized: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        backlog_dir = os.path.dirname(self.backlog_path)
        if backlog_dir:
            os.makedirs(backlog_dir, exist_ok=True)
        with open(self.backlog_path, "w", encoding="utf-8") as f:
            json.dump(prioritized, f, indent=2)

        if not project_id:
            return

        data = self._read_store()
        data["backlog_entries"] = [
            entry for entry in data["backlog_entries"]
            if entry.get("project_id") != project_id
        ]
        created_at = _utc_now()
        for bucket, items in prioritized.items():
            for feature in items:
                data["backlog_entries"].append(
                    {
                        "_id": str(uuid.uuid4()),
                        "project_id": project_id,
                        "bucket": bucket,
                        "feature_name": str(feature.get("name", "")),
                        "impact": str(feature.get("impact", "")),
                        "created_at": created_at,
                    }
                )
        for project in data["projects"]:
            if project.get("_id") == project_id:
                project["updated_at"] = _utc_now()
                break
        self._write_store(data)

    def save_campaign(self, campaign: Dict[str, Any]) -> None:
        project_id = campaign.get("project_id")
        now = _utc_now()
        data = self._read_store()
        data["campaigns"].append(
            {
                "_id": str(uuid.uuid4()),
                "project_id": project_id,
                "campaign": campaign,
                "created_at": now,
            }
        )
        if project_id:
            for project in data["projects"]:
                if project.get("_id") == project_id:
                    project["updated_at"] = now
                    break
        self._write_store(data)


# Backward-compatible alias
Storage = PMStorage

storage = PMStorage()
