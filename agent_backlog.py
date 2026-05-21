import sqlite3
import json
import os
from datetime import datetime
from typing import Optional

from enterprise_paths import backlog_db_path


class AgentBacklog:
    """
    SQLite-based storage for agent interactions and logs.
    Strictly maps to the agent JSON envelope schema:
    {
        "id", "timestamp", "sender", "recipient",
        "task_type", "context", "payload", "status", "error"
    }
    """

    def __init__(self, db_path: Optional[str] = None):
        self.db_path = db_path if db_path is not None else backlog_db_path()
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
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # --------------------------------------------------------
            # INTERACTIONS TABLE
            # One row per message between agents, matches JSON schema
            # --------------------------------------------------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS interactions (
                    id          TEXT PRIMARY KEY,  -- unique message id e.g. "req-001"
                    timestamp   TEXT,              -- when it was created (ISO 8601)
                    sender      TEXT,              -- agent who sent it e.g. "CEO"
                    recipient   TEXT,              -- agent who receives it e.g. "HR"
                    task_type   TEXT,              -- e.g. "TALENT_REALLOCATION"
                    context     TEXT,              -- extra info as JSON string
                    payload     TEXT,              -- the actual task as JSON string
                    status      TEXT,              -- pending, in_progress, done, error
                    error       TEXT               -- error message if something went wrong
                )
            """)

            # --------------------------------------------------------
            # LOGS TABLE
            # One row per action an agent took
            # --------------------------------------------------------
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    log_id      INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id     TEXT,              -- links back to an interaction id
                    agent_name  TEXT,              -- which agent did this
                    action      TEXT,              -- what it did e.g. "hired", "fired"
                    details     TEXT,              -- extra info as JSON string
                    timestamp   TEXT               -- when it happened
                )
            """)

            conn.commit()

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
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR IGNORE INTO interactions
                    (id, timestamp, sender, recipient, task_type, context, payload, status, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    message.get("id"),
                    message.get("timestamp", datetime.utcnow().isoformat()),
                    message.get("sender", ""),
                    message.get("recipient", ""),
                    message.get("task_type", ""),
                    json.dumps(message.get("context", {})),
                    json.dumps(message.get("payload", {})),
                    message.get("status", "pending"),
                    message.get("error", "")
                ))
                conn.commit()

        except sqlite3.Error as e:
            print(f"[DATABASE ERROR] Failed to record interaction: {e}")

    def get_pending_interactions(self):
        """
        Returns all interactions with status 'pending'.
        Use this to find tasks that still need to be processed.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM interactions WHERE status = 'pending'")
                rows = cursor.fetchall()
                return [self._reconstruct_message(row) for row in rows]

        except sqlite3.Error as e:
            print(f"[DATABASE ERROR] Failed to get pending interactions: {e}")
            return []

    def get_agent_history(self, agent_name: str, limit: int = 50):
        """
        Returns all interactions where the agent was either sender or recipient.
        Useful for checking what an agent has sent or received.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT * FROM interactions
                    WHERE sender = ? OR recipient = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (agent_name, agent_name, limit))
                rows = cursor.fetchall()
                return [self._reconstruct_message(row) for row in rows]

        except sqlite3.Error as e:
            print(f"[DATABASE ERROR] Failed to retrieve agent history: {e}")
            return []

    def update_status(self, task_id: str, status: str, error: str = ""):
        """
        Update the status of an interaction.
        e.g. from 'pending' to 'in_progress' or 'done' or 'error'
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    UPDATE interactions SET status = ?, error = ? WHERE id = ?
                """, (status, error, task_id))
                conn.commit()

        except sqlite3.Error as e:
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
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO logs (task_id, agent_name, action, details, timestamp)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    task_id,
                    agent_name,
                    action,
                    json.dumps(details),
                    datetime.utcnow().isoformat()
                ))
                conn.commit()

        except sqlite3.Error as e:
            print(f"[DATABASE ERROR] Failed to record log: {e}")

    def get_logs(self, task_id: str = None):
        """
        Get logs. Pass a task_id to filter by task, or leave empty for all logs.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                if task_id:
                    cursor.execute("SELECT * FROM logs WHERE task_id = ?", (task_id,))
                else:
                    cursor.execute("SELECT * FROM logs")
                rows = cursor.fetchall()
                return [dict(row) for row in rows]

        except sqlite3.Error as e:
            print(f"[DATABASE ERROR] Failed to get logs: {e}")
            return []

    # ================================================================
    # UTILITY
    # ================================================================

    def clear_backlog(self):
        """
        Wipes the entire database and recreates it fresh.
        Useful for testing — don't run this in production!
        """
        if os.path.exists(self.db_path):
            os.remove(self.db_path)
            self._initialize_db()
            print("Backlog cleared.")

    def _reconstruct_message(self, row):
        """
        Internal helper — converts a database row back into a dict
        matching the original JSON schema, parsing context and payload
        back from strings into dicts.
        """
        return {
            "id":        row["id"],
            "timestamp": row["timestamp"],
            "sender":    row["sender"],
            "recipient": row["recipient"],
            "task_type": row["task_type"],
            "context":   json.loads(row["context"] or "{}"),
            "payload":   json.loads(row["payload"] or "{}"),
            "status":    row["status"],
            "error":     row["error"]
        }


# ====================================================================
# QUICK TEST
# Run this file directly to verify everything works
# python agent_backlog.py
# ====================================================================
if __name__ == "__main__":
    db = AgentBacklog()
    db.clear_backlog()
   
    # Test inserting a task matching the JSON schema
    sample_message = {
        "id": "req-001",
        "timestamp": "2026-03-01T10:00:00Z",
        "sender": "CEO",
        "recipient": "HR",
        "task_type": "TALENT_REALLOCATION",
        "context": {
            "quarter": "Q2",
            "year": 2026
        },
        "payload": {
            "task": "Hire 10 engineering agents, and fire all 20 marketing agents"
        },
        "status": "pending",
        "error": ""
    }

    db.record_interaction(sample_message)
    print("Inserted sample interaction.")

    # Test fetching pending tasks
    pending = db.get_pending_interactions()
    print("Pending interactions:", pending)

    # Test updating status
    db.update_status("req-001", "in_progress")
    print("Updated status to in_progress.")

    # Test logging agent actions
    db.record_log("req-001", "HR", "hired", {"number": 10, "type": "engineering"})
    db.record_log("req-001", "HR", "fired", {"number": 20, "type": "marketing"})

    # Test fetching logs
    logs = db.get_logs("req-001")
    print("Logs:", logs)

    # Test agent history
    history = db.get_agent_history("CEO")
    print("CEO history:", history)

    # Test updating to done
    db.update_status("req-001", "done")
    print("Updated status to done.")