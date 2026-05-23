from __future__ import annotations

import os
from dataclasses import dataclass

from enterprise_paths import inter_agent_mongo_db_name, inter_agent_mongo_uri


@dataclass(frozen=True)
class RouterSettings:
    backend: str = "sqlite"
    sqlite_db_path: str = ""
    mongo_uri: str = ""
    mongo_db_name: str = ""
    shared_secret: str = "change-me-registration"
    admin_secret: str = "change-me-admin"
    api_host: str = "127.0.0.1"
    api_port: int = 8765

    @classmethod
    def from_env(cls) -> RouterSettings:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_sqlite = os.path.join(repo_root, "enterprise_router.db")
        return cls(
            backend=os.getenv("ENTERPRISE_ROUTER_BACKEND", "sqlite").strip().lower(),
            sqlite_db_path=os.getenv("ENTERPRISE_ROUTER_DB", default_sqlite),
            mongo_uri=os.getenv("MONGODB_URI", inter_agent_mongo_uri()),
            mongo_db_name=os.getenv(
                "ENTERPRISE_ROUTER_MONGO_DB",
                os.getenv("ENTERPRISE_MONGO_INTER_AGENT_DB", inter_agent_mongo_db_name()),
            ),
            shared_secret=os.getenv("ENTERPRISE_ROUTER_SHARED_SECRET", "change-me-registration"),
            admin_secret=os.getenv("ENTERPRISE_ROUTER_ADMIN_SECRET", "change-me-admin"),
            api_host=os.getenv("ENTERPRISE_ROUTER_HOST", "127.0.0.1"),
            api_port=int(os.getenv("ENTERPRISE_ROUTER_PORT", "8765")),
        )
