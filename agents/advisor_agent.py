from ._compat import import_legacy_ceo_agents_module

_legacy = import_legacy_ceo_agents_module("advisor_agent")
AdvisorAgent = _legacy.AdvisorAgent

__all__ = ["AdvisorAgent"]
