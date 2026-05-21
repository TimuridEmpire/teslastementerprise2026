import importlib
import sys
import types
from pathlib import Path


def ensure_ceo_agents_on_path() -> None:
    root = Path(__file__).resolve().parents[1]
    ceo_agents_dir = root / "ceo-agents"
    ceo_agents_path = str(ceo_agents_dir)
    if ceo_agents_path not in sys.path:
        sys.path.insert(0, ceo_agents_path)


def import_legacy_ceo_agents_module(module_name: str):
    """
    Import ``ceo-agents/<module_name>.py`` as a synthetic package module so
    its relative imports (e.g. ``from .thread_safe_agent``) still resolve.
    """
    root = Path(__file__).resolve().parents[1]
    ceo_agents_dir = root / "ceo-agents"
    package_name = "_ceo_agents_legacy"
    pkg = sys.modules.get(package_name)
    if pkg is None:
        pkg = types.ModuleType(package_name)
        pkg.__path__ = [str(ceo_agents_dir)]  # type: ignore[attr-defined]
        sys.modules[package_name] = pkg
    return importlib.import_module(f"{package_name}.{module_name}")
