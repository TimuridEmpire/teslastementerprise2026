"""
Agent implementations: CEO, advisor, multithreaded runtime, and thread-safe mixin.

Import from submodules, for example ``from agents.ceo_agent import CeoAgent``.

Shared runtime (message bus, backlog, logging, distribution tokens) stays in the
project root. Run tests from this directory with ``pytest`` so ``pythonpath`` in
``pytest.ini`` keeps imports working across ``agents/`` and the root modules.
"""
