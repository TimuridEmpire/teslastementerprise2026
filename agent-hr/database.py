import json
import os
from datetime import datetime

from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError


class AgentBacklog:
    """
    SQLite-based storage for agent interactions and logs.
    Strictly maps to the agent JSON envelope schema:
    {
        "id", "timestamp", "sender", "recipient",
        "task_type", "context", "payload", "status", "error"
    }
    """

    def __init__(self, db_path="enterprise_backlog.db"):
        self.db_path = db_path
        # Use the provided path (filename) to derive a MongoDB database name
        # keep the default value unchanged for compatibility
        dbname = os.path.splitext(os.path.basename(self.db_path))[0]
        self.client = MongoClient(os.environ.get("MONGO_URI", "mongodb+srv://asu:pass123@mydeployment.onlk26z.mongodb.net/?appName=mongosh+2.8.2"))
        self.db = self.client[dbname]
        self._initialize_db()

    # ================================================================
    # SETUP
    # ================================================================

    def _initialize_db(self):
        """
        Creates the database tables if they don't exist yet.
        - interactions: stores every agent message/task
        - logs:         stores what each agent actually did
        """
        # For MongoDB we ensure collections exist and set an index on `id` for interactions
        interactions = self.db.get_collection("interactions")
        logs = self.db.get_collection("logs")
        # ensure `id` is unique for interactions (maps to previous PRIMARY KEY)
        try:
            interactions.create_index("id", unique=True)
        except Exception:
            pass

    # ================================================================
    # INTERACTION FUNCTIONS
    # ================================================================

    def record_interaction(self, message: dict):
        """
        Insert a message/task into the interactions table.
        Pass in a dict matching the JSON schema.
        Uses INSERT OR IGNORE so duplicate ids are skipped safely.
        """
        try:
            interactions = self.db.get_collection("interactions")
            doc = {
                "id": message.get("id"),
                "timestamp": message.get("timestamp", datetime.utcnow().isoformat()),
                "sender": message.get("sender", ""),
                "recipient": message.get("recipient", ""),
                "task_type": message.get("task_type", ""),
                # store context/payload as JSON-like objects (dicts)
                "context": message.get("context", {}),
                "payload": message.get("payload", {}),
                "status": message.get("status", "pending"),
                "error": message.get("error", "")
            }
            try:
                interactions.insert_one(doc)
            except DuplicateKeyError:
                # INSERT OR IGNORE semantics: do nothing if id exists
                pass
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to record interaction: {e}")

    def get_pending_interactions(self):
        """
        Returns all interactions with status 'pending'.
        Use this to find tasks that still need to be processed.
        """
        try:
            interactions = self.db.get_collection("interactions")
            cursor = interactions.find({"status": "pending"})
            return [self._reconstruct_message(row) for row in cursor]
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to get pending interactions: {e}")
            return []

    def get_agent_history(self, agent_name: str, limit: int = 50):
        """
        Returns all interactions where the agent was either sender or recipient.
        Useful for checking what an agent has sent or received.
        """
        try:
            interactions = self.db.get_collection("interactions")
            cursor = interactions.find({"$or": [{"sender": agent_name}, {"recipient": agent_name}]})
            cursor = cursor.sort("timestamp", -1).limit(limit)
            return [self._reconstruct_message(row) for row in cursor]
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to retrieve agent history: {e}")
            return []

    def update_status(self, task_id: str, status: str, error: str = ""):
        """
        Update the status of an interaction.
        e.g. from 'pending' to 'in_progress' or 'done' or 'error'
        """
        try:
            interactions = self.db.get_collection("interactions")
            interactions.update_one({"id": task_id}, {"$set": {"status": status, "error": error}})
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to update status: {e}")

    # ================================================================
    # LOG FUNCTIONS
    # ================================================================

    def record_log(self, task_id: str, agent_name: str, action: str, details: dict = {}):
        """
        Log an action an agent took.
        Call this inside hireAgents() and fireAgents() in Kanosei_HR.py.
        """
        try:
            logs = self.db.get_collection("logs")
            doc = {
                "task_id": task_id,
                "agent_name": agent_name,
                "action": action,
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
            }
            logs.insert_one(doc)
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to record log: {e}")

    def get_logs(self, task_id: str = None):
        """
        Get logs. Pass a task_id to filter by task, or leave empty for all logs.
        """
        try:
            logs = self.db.get_collection("logs")
            if task_id:
                cursor = logs.find({"task_id": task_id})
            else:
                cursor = logs.find()
            result = []
            for row in cursor:
                # convert ObjectId to string if present
                row = dict(row)
                if "_id" in row:
                    row["_id"] = str(row["_id"])
                result.append(row)
            return result
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to get logs: {e}")
            return []

    # ================================================================
    # UTILITY
    # ================================================================

    def clear_backlog(self):
        """
        Wipes all data from the database tables.
        For development and testing purposes only. Do not call in production.
        """
        try:
            interactions = self.db.get_collection("interactions")
            logs = self.db.get_collection("logs")
            interactions.delete_many({})
            logs.delete_many({})
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to clear backlog: {e}")

    def _reconstruct_message(self, row):
        """
        Internal helper — converts a database row back into a dict
        matching the original JSON schema, parsing context and payload
        back from strings into dicts.
        """
        # row is a dict-like document from MongoDB
        return {
            "id":        row.get("id"),
            "timestamp": row.get("timestamp"),
            "sender":    row.get("sender"),
            "recipient": row.get("recipient"),
            "task_type": row.get("task_type"),
            "context":   row.get("context") or {},
            "payload":   row.get("payload") or {},
            "status":    row.get("status"),
            "error":     row.get("error")
        }

class AgentSpecs:
    """
    SQLite-based storage for agent specifications.
    """

    def __init__(self, db_path="enterprise_agent_specs.db"):
        self.db_path = db_path
        dbname = os.path.splitext(os.path.basename(self.db_path))[0]

        #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
        #  IMPORTANT: MongoClient URI MUST be the same as the locally 
        #             created Docker Database if running locally
        #!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!

        self.client = MongoClient("mongodb+srv://asu:pass123@mydeployment.onlk26z.mongodb.net/?appName=mongosh+2.8.2")
        self.db = self.client[dbname]
        self._initialize_db()

    # ================================================================
    # SETUP
    # ================================================================

    def _initialize_db(self):
        """
        Creates the database tables if they don't exist yet.
        - interactions: stores every agent message/task
        - logs:         stores what each agent actually did
        """
        specs = self.db.get_collection("specs")
        try:
            specs.create_index("agent_type", unique=True)
        except Exception:
            pass

    # ================================================================
    # INTERACTION FUNCTIONS
    # ================================================================

    def add_agent_specs(self, message: dict):
        """
        Insert a message/task into the interactions table.
        Pass in a dict matching the JSON schema.
        Uses INSERT OR IGNORE so duplicate ids are skipped safely.
        """
        try:
            specs = self.db.get_collection("specs")
            doc = {
                "agent_type": message.get("agent_type"),
                "agent_specs": message.get("agent_specs", {}),
                "error": message.get("error", "")
            }
            try:
                specs.insert_one(doc)
            except DuplicateKeyError:
                # INSERT OR IGNORE semantics
                pass
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to record specs: {e}")

    def get_specs(self, agent_type: str):
        """
        Returns all interactions with status 'pending'.
        Use this to find tasks that still need to be processed.
        """
        try:
            specs = self.db.get_collection("specs")
            doc = specs.find_one({"agent_type": agent_type})
            if not doc:
                return {}
            return doc.get("agent_specs", {})
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to get specs: {e}")
            return {}

    def update_spec(self, agent_type: str, spec_type: str, amount: int, error: str = ""):
        """
        Update the status of an interaction.
        e.g. from 'pending' to 'in_progress' or 'done' or 'error'
        """
        try:
            specs = self.db.get_collection("specs")
            new_specs = self.get_specs(agent_type)
            new_specs[spec_type] = amount
            specs.update_one({"agent_type": agent_type}, {"$set": {"agent_specs": new_specs, "error": error}})
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to update status: {e}")

    # ================================================================
    # UTILITY
    # ================================================================

    def clear_specs(self):
        """
        Wipes all data from the database tables.
        For development and testing purposes only. Do not call in production.
        """
        try:
            specs = self.db.get_collection("specs")
            specs.delete_many({})
        except Exception as e:
            print(f"[DATABASE ERROR] Failed to clear backlog: {e}")

    def _reconstruct_message(self, row):
        """
        Internal helper — converts a database row back into a dict
        matching the original JSON schema, parsing context and payload
        back from strings into dicts.
        """
        return {
            "type": row.get("agent_type"),
            "specs": row.get("agent_specs") or {},
            "error": row.get("error")
        }


# ====================================================================
# QUICK TEST
# Run this file directly to verify everything works
# python database.py
# ====================================================================
if __name__ == "__main__":
    db = AgentSpecs()

    db.clear_specs();

    db.add_agent_specs({
        "agent_type": "HR",
        "agent_specs": {
            "max_tokens": 1000,
            "max_agents": 2,
            },
        "error": ""
        })

    print(db.get_specs("HR"))

    db.update_spec("HR", "max_tokens", 10900)

    print(db.get_specs("HR"))
    