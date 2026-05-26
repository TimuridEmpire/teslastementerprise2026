"""Start every implemented Enterprise Router-backed agent worker.

Run this after the router is running and after the agents have been registered.
The launcher starts only agents that have both an implementation and an API key.
Sales and Finance are registered names in the router/website, but this codebase
currently has no worker file for them, so this launcher reports them as missing.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RUN_SINGLE = ROOT / "run_single_agent.py"


@dataclass(frozen=True)
class AgentSpec:
    display_name: str
    router_name: str
    key_envs: tuple[str, ...]
    implemented: bool = True
    required_modules: tuple[str, ...] = ()


AGENTS: dict[str, AgentSpec] = {
    "ceo": AgentSpec("CEO", "CEO", ("CEO_AGENT_API_KEY", "NEXT_PUBLIC_CEO_API_KEY")),
    "pm": AgentSpec("PM", "PM", ("PM_AGENT_API_KEY", "PRODUCT_AGENT_API_KEY", "NEXT_PUBLIC_PM_API_KEY", "NEXT_PUBLIC_PRODUCT_API_KEY")),
    "marketing": AgentSpec("Marketing", "Marketing", ("MARKETING_AGENT_API_KEY", "NEXT_PUBLIC_MARKETING_API_KEY")),
    "hr": AgentSpec("HR", "HR", ("HR_AGENT_API_KEY", "NEXT_PUBLIC_HR_API_KEY")),
    "engineering": AgentSpec("Engineering", "Engineering", ("ENGINEERING_AGENT_API_KEY", "NEXT_PUBLIC_ENGINEERING_API_KEY"), required_modules=("crewai", "crewai_tools")),
    "advisor": AgentSpec("Strategic Advisor", "Strategic Advisor", ("ADVISOR_AGENT_API_KEY", "STRATEGIC_ADVISOR_AGENT_API_KEY", "NEXT_PUBLIC_ADVISOR_API_KEY")),
    "sales": AgentSpec("Sales", "Sales", ("SALES_AGENT_API_KEY", "NEXT_PUBLIC_SALES_API_KEY"), implemented=False),
    "finance": AgentSpec("Finance", "Finance", ("FINANCE_AGENT_API_KEY", "NEXT_PUBLIC_FINANCE_API_KEY"), implemented=False),
}

DEFAULT_ORDER = ("ceo", "pm", "marketing", "hr", "engineering", "advisor", "sales", "finance")


def split_agents(raw: str | None) -> list[str]:
    if not raw or raw.strip().lower() == "all":
        return list(DEFAULT_ORDER)
    names = []
    for item in raw.split(","):
        key = item.strip().lower().replace(" ", "-").replace("_", "-")
        if key == "product":
            key = "pm"
        if key == "eng":
            key = "engineering"
        if key == "strategic-advisor":
            key = "advisor"
        names.append(key)
    return names


def resolve_key(spec: AgentSpec) -> tuple[str | None, str | None]:
    for env_name in spec.key_envs:
        value = os.getenv(env_name, "").strip()
        if value:
            return env_name, value
    return None, None


def missing_modules(spec: AgentSpec) -> list[str]:
    return [
        module
        for module in spec.required_modules
        if importlib.util.find_spec(module) is None
    ]


def should_use_light_demo(key: str, spec: AgentSpec) -> bool:
    return key == "engineering" and bool(missing_modules(spec))


def list_status(selected: list[str]) -> int:
    for key in selected:
        spec = AGENTS.get(key)
        if spec is None:
            print(f"{key}: unknown")
            continue
        env_name, _ = resolve_key(spec)
        missing = missing_modules(spec)
        if should_use_light_demo(key, spec):
            state = f"implemented; light demo fallback available because missing {', '.join(missing)}"
        else:
            state = "implemented" if spec.implemented else "missing worker"
        key_state = f"key from {env_name}" if env_name else "no key env set"
        print(f"{spec.display_name}: {state}; {key_state}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Launch implemented Enterprise Router agent workers.")
    parser.add_argument("--agents", default="all", help="Comma-separated agents, or all. Example: HR,CEO,PM")
    parser.add_argument("--poll-interval", default="2", help="Seconds between polls for wrapper-based workers.")
    parser.add_argument("--list", action="store_true", help="Show which agents can run and which keys are present.")
    args = parser.parse_args()

    selected = split_agents(args.agents)
    if args.list:
        return list_status(selected)

    router_url = os.getenv("ENTERPRISE_ROUTER_URL", os.getenv("ENTERPRISE_ROUTER_API_URL", "")).strip()
    if not router_url:
        print("ENTERPRISE_ROUTER_URL is required, for example: http://localhost:8000", file=sys.stderr)
        return 2

    children: list[subprocess.Popen[str]] = []
    skipped = False

    for key in selected:
        spec = AGENTS.get(key)
        if spec is None:
            print(f"Skipping unknown agent {key!r}.")
            skipped = True
            continue
        if not spec.implemented:
            print(f"Skipping {spec.display_name}: no runtime worker exists in this codebase yet.")
            skipped = True
            continue
        missing = missing_modules(spec)
        if missing and not should_use_light_demo(key, spec):
            print(f"Skipping {spec.display_name}: missing Python package(s): {', '.join(missing)}.")
            skipped = True
            continue
        env_name, api_key = resolve_key(spec)
        if not api_key:
            print(f"Skipping {spec.display_name}: set one of {', '.join(spec.key_envs)}.")
            skipped = True
            continue

        env = os.environ.copy()
        env["ENTERPRISE_ROUTER_URL"] = router_url
        env["ENTERPRISE_AGENT_NAME"] = spec.router_name
        env["ENTERPRISE_AGENT_API_KEY"] = api_key
        if should_use_light_demo(key, spec):
            env["ENGINEERING_LIGHT_DEMO"] = "1"
            print(
                f"{spec.display_name}: missing {', '.join(missing)}; "
                "starting deterministic light demo mode."
            )

        cmd = [sys.executable, str(RUN_SINGLE), spec.router_name, "--poll-interval", str(args.poll_interval)]
        print(f"Starting {spec.display_name} using {env_name}.")
        children.append(subprocess.Popen(cmd, cwd=str(ROOT), env=env, text=True))

    if not children:
        print("No agent workers were started.", file=sys.stderr)
        return 1 if skipped else 0

    print("Agent workers are running. Press Ctrl+C to stop them.")
    try:
        while True:
            for child in list(children):
                code = child.poll()
                if code is not None:
                    children.remove(child)
                    print(f"Worker exited with code {code}.")
            if not children:
                return 1
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping agent workers...")
        for child in children:
            child.terminate()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())



