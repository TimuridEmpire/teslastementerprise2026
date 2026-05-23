"""
Single source of truth for enterprise persistence.

- **SQLite** — internal backlog: ``AgentBacklog`` / ``MessageBus`` (``ENTERPRISE_BACKLOG_DB``).
- **JSONL** — bus audit file (``ENTERPRISE_MESSAGE_BUS_JSONL``).
- **MongoDB** — optional queue backend for the enterprise router when ``ENTERPRISE_ROUTER_BACKEND=mongo``.
- **Enterprise Router HTTP** — cross-service API (``inter_agent_api.py`` / ``enterprise_router.api``).

ENTERPRISE_BACKLOG_DB            — SQLite path (default: <repo>/enterprise_backlog.db)
ENTERPRISE_MESSAGE_BUS_JSONL     — JSONL path (default: <repo>/enterprise_message_bus.jsonl)
MONGODB_URI                      — Mongo connection (default: mongodb://localhost:27017/)
ENTERPRISE_MONGO_INTER_AGENT_DB  — Mongo DB name (default: enterprise_inter_agent)
ENTERPRISE_ROUTER_URL            — Router base URL for agent HTTP clients
ENTERPRISE_AGENT_NAME            — This agent's id (X-Agent-Id)
ENTERPRISE_AGENT_API_KEY         — Bearer token issued by admin
ENTERPRISE_ROUTER_ADMIN_SECRET   — Admin header for registration / agent setup
ENTERPRISE_ROUTER_SHARED_SECRET  — Registration request secret
ENTERPRISE_ROUTER_BACKEND        — sqlite (default) or mongo
ENTERPRISE_ROUTER_PORT           — API listen port (default 8765)
"""

from __future__ import annotations

import os
try:
    from dotenv import load_dotenv
except ImportError:
    def load_dotenv(*args, **kwargs):  # type: ignore[override]
        return False

# Load the .env file once for the whole application
load_dotenv()

_REPO_ROOT = os.path.dirname(os.path.abspath(__file__))


def backlog_db_path() -> str:
    """Returns the local path for the SQLite DB."""
    env = os.environ.get("ENTERPRISE_BACKLOG_DB")
    if env:
        return os.path.abspath(env)
    return os.path.join(_REPO_ROOT, "enterprise_backlog.db")


def message_bus_jsonl_path() -> str:
    """Returns the local path for the JSONL audit file."""
    env = os.environ.get("ENTERPRISE_MESSAGE_BUS_JSONL")
    if env:
        return os.path.abspath(env)
    return os.path.join(_REPO_ROOT, "enterprise_message_bus.jsonl")


def inter_agent_mongo_uri() -> str:
    """
    Returns the secure MongoDB URI from the .env file.
    Falls back to a local default if the .env variable is missing.
    """
    return os.getenv("MONGODB_URI", "mongodb://localhost:27017/")


def inter_agent_mongo_db_name() -> str:
    """
    Returns the specific database name.
    """
    return os.getenv("ENTERPRISE_MONGO_INTER_AGENT_DB", "enterprise_inter_agent")