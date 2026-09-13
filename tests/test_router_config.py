from __future__ import annotations

import pytest

from enterprise_router.config import RouterSettings


def _clear_secret_env(monkeypatch):
    monkeypatch.delenv("ENTERPRISE_ROUTER_SHARED_SECRET", raising=False)
    monkeypatch.delenv("ENTERPRISE_ROUTER_ADMIN_SECRET", raising=False)
    monkeypatch.delenv("ENTERPRISE_ROUTER_ALLOW_DEV_DEFAULTS", raising=False)


def test_from_env_refuses_to_boot_with_no_secrets_set(monkeypatch):
    """A router that silently falls back to 'change-me-admin' when nobody
    set a real secret is exactly the kind of gap that's invisible on a
    single operator's own machine but becomes an incident on someone
    else's infrastructure. from_env() -- the actual server-boot path --
    must fail loudly instead."""
    _clear_secret_env(monkeypatch)

    with pytest.raises(RuntimeError, match="Refusing to start with insecure defaults"):
        RouterSettings.from_env()


def test_from_env_allows_placeholders_only_with_explicit_dev_opt_in(monkeypatch):
    _clear_secret_env(monkeypatch)
    monkeypatch.setenv("ENTERPRISE_ROUTER_ALLOW_DEV_DEFAULTS", "1")

    settings = RouterSettings.from_env()

    assert settings.admin_secret == "change-me-admin"
    assert settings.shared_secret == "change-me-registration"


def test_from_env_boots_normally_with_real_secrets_set(monkeypatch):
    _clear_secret_env(monkeypatch)
    monkeypatch.setenv("ENTERPRISE_ROUTER_SHARED_SECRET", "real-shared-secret")
    monkeypatch.setenv("ENTERPRISE_ROUTER_ADMIN_SECRET", "real-admin-secret")

    settings = RouterSettings.from_env()

    assert settings.shared_secret == "real-shared-secret"
    assert settings.admin_secret == "real-admin-secret"
