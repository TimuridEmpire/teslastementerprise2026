import json
import os
import sys
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pymongo import MongoClient, DESCENDING
from pymongo.database import Database

# --- INTEGRATION: Path adjustment for subdirectory ---
# Since this file lives in `pm/`, we add the parent directory to the system path 
# so we can import the root-level enterprise configuration files.
current_dir = os.path.dirname(os.path.abspath(__file__))
root_dir = os.path.dirname(current_dir)
if root_dir not in sys.path:
    sys.path.append(root_dir)

from enterprise_paths import inter_agent_mongo_uri, inter_agent_mongo_db_name, backlog_db_path


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Storage:
    """
    The PM Agent's Business Data Layer. 
    Strictly handles domain-specific data (Projects, Backlogs, Campaigns).
    Message routing/persistence is delegated to the Enterprise Post Office.
    """
    def __init__(self, mongo_uri: Optional[str] = None, db_name: Optional[str] = None) -> None:
        # Dynamically pull the exact same MongoDB connection as the inter-agent bus
        uri = mongo_uri or inter_agent_mongo_uri()
        name = db_name or inter_agent_mongo_db_name()
        
        # Align the local backlog JSON artifact with the enterprise data directory
        default_data_dir = os.path.dirname(backlog_db_path()) or "data"
        self.backlog_path = os.getenv("BACKLOG_PATH", os.path.join(default_data_dir, "pm_backlog.json"))
        
        self.client = MongoClient(uri)
        self.db: Database = self.client[name]
        self._init_db()

    def _init_db(self) -> None:
        # Indexed for fast lookups on domain logic. 
        # (Message indexing is handled upstream now).
        self.db["projects"].create_index("status")
        self.db["project_events"].create_index("project_id")
        self.db["backlog_entries"].create_index("project_id")

    # ==================================================================
    # Projects
    # ==================================================================

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
                {"$set": {
                    "name": name,
                    "goal": goal,
                    "description": resolved_description,
                    "status": status,
                    "metadata": metadata,
                    "updated_at": now,
                }},
            )
        else:
            self.db["projects"].insert_one({
                "_id": resolved_id,
                "name": name,
                "goal": goal,
                "description": resolved_description,
                "status": status,
                "metadata": metadata,
                "created_at": now,
                "updated_at": now,
            })
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

    # ==================================================================
    # Project Events
    # ==================================================================

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
        self.db["project_events"].insert_one({
            "_id": str(uuid.uuid4()),
            "project_id": project_id,
            "source": source,
            "event_type": event_type,
            "message_id": message_id,
            "details": details or {},
            "created_at": now,
        })
        if project_id:
            self.db["projects"].update_one(
                {"_id": project_id},
                {"$set": {"updated_at": now}},
            )

    # ==================================================================
    # Backlog
    # ==================================================================

    def save_backlog(
        self,
        project_id: Optional[str],
        prioritized: Dict[str, List[Dict[str, Any]]],
    ) -> None:
        # Keep the JSON file artifact for backward compatibility/easy viewing
        backlog_dir = os.path.dirname(self.backlog_path)
        if backlog_dir:
            os.makedirs(backlog_dir, exist_ok=True)
        with open(self.backlog_path, "w") as f:
            json.dump(prioritized, f, indent=2)

        if not project_id:
            return

        self.db["backlog_entries"].delete_many({"project_id": project_id})
        created_at = _utc_now()
        docs = []
        for bucket, items in prioritized.items():
            for feature in items:
                docs.append({
                    "_id": str(uuid.uuid4()),
                    "project_id": project_id,
                    "bucket": bucket,
                    "feature_name": str(feature.get("name", "")),
                    "impact": str(feature.get("impact", "")),
                    "created_at": created_at,
                })
        if docs:
            self.db["backlog_entries"].insert_many(docs)

        self.db["projects"].update_one(
            {"_id": project_id},
            {"$set": {"updated_at": _utc_now()}},
        )

    # ==================================================================
    # Campaigns
    # ==================================================================

    def save_campaign(self, campaign: Dict[str, Any]) -> None:
        project_id = campaign.get("project_id")
        now = _utc_now()
        self.db["campaigns"].insert_one({
            "_id": str(uuid.uuid4()),
            "project_id": project_id,
            "campaign": campaign,
            "created_at": now,
        })
        if project_id:
            self.db["projects"].update_one(
                {"_id": project_id},
                {"$set": {"updated_at": now}},
            )


# Instantiate a singleton for import by PMAgent
storage = Storage()