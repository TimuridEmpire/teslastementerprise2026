from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class RouterSettings:
    sqlite_db_path: str = ""
    shared_secret: str = "change-me-registration"
    admin_secret: str = "change-me-admin"
    api_host: str = "127.0.0.1"
    api_port: int = 8765

    @classmethod
    def from_env(cls) -> RouterSettings:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_sqlite = os.path.join(repo_root, "enterprise_router.db")
        return cls(
            sqlite_db_path=os.getenv("ENTERPRISE_ROUTER_DB", default_sqlite),
            shared_secret=os.getenv("ENTERPRISE_ROUTER_SHARED_SECRET", "change-me-registration"),
            admin_secret=os.getenv("ENTERPRISE_ROUTER_ADMIN_SECRET", "change-me-admin"),
            api_host=os.getenv("ENTERPRISE_ROUTER_HOST", "127.0.0.1"),
            api_port=int(os.getenv("ENTERPRISE_ROUTER_PORT", "8765")),
        )
