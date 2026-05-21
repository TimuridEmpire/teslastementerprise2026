"""
Compatibility package that exposes modules from ``ceo-agents/`` under ``agents.*``.
"""

from .advisor_agent import AdvisorAgent
from .ceo_agent import CeoAgent

__all__ = ["AdvisorAgent", "CeoAgent"]
