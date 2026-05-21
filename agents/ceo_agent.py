from ._compat import import_legacy_ceo_agents_module

_legacy = import_legacy_ceo_agents_module("ceo_agent")
CeoAgent = _legacy.CeoAgent

__all__ = ["CeoAgent"]
