from __future__ import annotations

import os
import sys
from dataclasses import dataclass

# These exist so RouterSettings(...) stays convenient to construct directly
# (tests do this constantly, always passing their own explicit secrets).
# from_env() -- the actual server-boot path -- refuses to silently fall back
# to them; see the placeholder check below. A router that boots on
# "change-me-admin" and never tells anyone is exactly the kind of gap that
# turns into an incident on someone else's infrastructure, not just a repo
# a single operator already knows the real values for.
_PLACEHOLDER_SHARED_SECRET = "change-me-registration"
_PLACEHOLDER_ADMIN_SECRET = "change-me-admin"


@dataclass(frozen=True)
class RouterSettings:
    sqlite_db_path: str = ""
    shared_secret: str = _PLACEHOLDER_SHARED_SECRET
    admin_secret: str = _PLACEHOLDER_ADMIN_SECRET
    api_host: str = "127.0.0.1"
    api_port: int = 8765

    @classmethod
    def from_env(cls) -> RouterSettings:
        repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        default_sqlite = os.path.join(repo_root, "enterprise_router.db")
        shared_secret = os.getenv("ENTERPRISE_ROUTER_SHARED_SECRET", "")
        admin_secret = os.getenv("ENTERPRISE_ROUTER_ADMIN_SECRET", "")
        allow_dev_defaults = os.getenv("ENTERPRISE_ROUTER_ALLOW_DEV_DEFAULTS", "").strip().lower() in {"1", "true", "yes", "on"}

        missing = [
            name for name, value in (
                ("ENTERPRISE_ROUTER_SHARED_SECRET", shared_secret),
                ("ENTERPRISE_ROUTER_ADMIN_SECRET", admin_secret),
            )
            if not value
        ]
        if missing:
            if allow_dev_defaults:
                print(
                    f"[enterprise_router] WARNING: {', '.join(missing)} not set -- "
                    "booting with insecure placeholder secrets because "
                    "ENTERPRISE_ROUTER_ALLOW_DEV_DEFAULTS is set. Do not use this "
                    "outside local development.",
                    file=sys.stderr,
                )
                shared_secret = shared_secret or _PLACEHOLDER_SHARED_SECRET
                admin_secret = admin_secret or _PLACEHOLDER_ADMIN_SECRET
            else:
                raise RuntimeError(
                    f"Refusing to start with insecure defaults: {', '.join(missing)} "
                    "must be set to a real secret. For local development only, set "
                    "ENTERPRISE_ROUTER_ALLOW_DEV_DEFAULTS=1 to boot with a placeholder instead."
                )

        return cls(
            sqlite_db_path=os.getenv("ENTERPRISE_ROUTER_DB", default_sqlite),
            shared_secret=shared_secret,
            admin_secret=admin_secret,
            api_host=os.getenv("ENTERPRISE_ROUTER_HOST", "127.0.0.1"),
            api_port=int(os.getenv("ENTERPRISE_ROUTER_PORT", "8765")),
        )
