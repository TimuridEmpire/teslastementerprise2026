"""
PM / Marketing business data layer (projects, backlogs, campaigns).

Inter-agent message routing uses ``enterprise_router`` (see ``agent_transport``).
"""

import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import DESCENDING, MongoClient
from pymongo.database import Database

from enterprise_paths import backlog_db_path, inter_agent_mongo_db_name, inter_agent_mongo_uri


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class PMStorage:
    """
    Domain persistence for PM and Marketing agents.
    Does not handle the enterprise message router queue.
    """

    def __init__(self, mongo_uri: Optional[str] = None, db_name: Optional[str] = None) -> None:
        uri = mongo_uri or inter_agent_mongo_uri()
        name = db_name or inter_agent_mongo_db_name()
        default_data_dir = os.path.dirname(backlog_db_path()) or "data"
        self.backlog_path = os.getenv(
            "BACKLOG_PATH", os.path.join(default_data_dir, "pm_backlog.json")
        )
        self.client = MongoClient(uri)
        self.db: Database = self.client[name]
        self._init_db()

    def _init_db(self) -> None:
        self.db["projects"].create_index("status")
        self.db["project_events"].create_index("project_id")
        self.db["backlog_entries"].create_index("project_id")

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

        existing = self.db["projects"].find_one({"_id": resolved_id})
        if existing:
            self.db["projects"].update_one(
                {"_id": resolved_id},
                {
                    "$set": {
                        "name": name,
                        "goal": goal,
                        "description": resolved_description,
                        "status": status,
                        "metadata": metadata,
                        "updated_at": now,
                    }
                },
            )
        else:
            self.db["projects"].insert_one(
                {
                    "_id": resolved_id,
                    "name": name,
                    "goal": goal,
                    "description": resolved_description,
                    "status": status,
                    "metadata": metadata,
                    "created_at": now,
                    "updated_at": now,
                }
            )
        return self.get_project(resolved_id) or {}

    def get_project(self, project_id: str) -> Optional[Dict[str, Any]]:
        doc = self.db["projects"].find_one({"_id": project_id})
        if not doc:
            return None
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

    def find_active_project_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        doc = self.db["projects"].find_one(
            {"name": name, "status": "active"},
            sort=[("updated_at", DESCENDING)],
        )
        if not doc:
            return None
        return self.get_project(doc["_id"])

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
        self.db["project_events"].insert_one(
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
            self.db["projects"].update_one(
                {"_id": project_id},
                {"$set": {"updated_at": now}},
            )

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

        self.db["backlog_entries"].delete_many({"project_id": project_id})
        created_at = _utc_now()
        docs = []
        for bucket, items in prioritized.items():
            for feature in items:
                docs.append(
                    {
                        "_id": str(uuid.uuid4()),
                        "project_id": project_id,
                        "bucket": bucket,
                        "feature_name": str(feature.get("name", "")),
                        "impact": str(feature.get("impact", "")),
                        "created_at": created_at,
                    }
                )
        if docs:
            self.db["backlog_entries"].insert_many(docs)

        self.db["projects"].update_one(
            {"_id": project_id},
            {"$set": {"updated_at": _utc_now()}},
        )

    def save_campaign(self, campaign: Dict[str, Any]) -> None:
        project_id = campaign.get("project_id")
        now = _utc_now()
        self.db["campaigns"].insert_one(
            {
                "_id": str(uuid.uuid4()),
                "project_id": project_id,
                "campaign": campaign,
                "created_at": now,
            }
        )
        if project_id:
            self.db["projects"].update_one(
                {"_id": project_id},
                {"$set": {"updated_at": now}},
            )


# Backward-compatible alias
Storage = PMStorage

storage = PMStorage()
