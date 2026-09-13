"""Process manager for auto-hosting an Engineering build's generated code.

Extracts the source embedded in an artifact's content (see
engineering_agent.py's _artifact_body -- every generated file is embedded as
a fenced code block under "## Generated Source"), writes it to a fresh temp
directory, and runs enterprise_router/generic_app_runner.py against that
directory inside a locked-down, network-isolated Docker container on a free
local port.

Two things gate this, both fail-closed:

1. ENTERPRISE_ROUTER_ENABLE_BUILD_HOSTING must be explicitly truthy. Default
   is disabled. This runs unreviewed LLM-generated code; an operator has to
   consciously opt in, not discover it's on by default.
2. Docker must be present on PATH. There is no unsandboxed subprocess
   fallback -- earlier versions of this module ran generated code as a
   plain subprocess with the router's own OS permissions, isolated only by
   being its own process and binding to localhost. That's fine for one
   operator on their own laptop; it's not something to hand to an
   enterprise's other engineers. If Docker isn't available, Run simply
   doesn't work, rather than silently degrading to the unsafe path.

The container itself: --network none is incompatible with the whole point
of this feature (the operator needs to reach the hosted app over HTTP), so
isolation instead uses a Docker "internal" network (--internal), which
still allows inbound access via a published port but disables the
network's outbound NAT -- the container can't reach the internet or
anything else on the host's network. Also: --read-only root filesystem
(mounts are the only writable-adjacent surface, and those are read-only
too), --cap-drop ALL, --security-opt no-new-privileges, a non-root numeric
user, and hard memory/cpu/pids caps.

Caveat, stated plainly: this was authored without a Docker daemon
available to test against (see the Enterprise Deployment Blueprint). The
command construction is unit-tested directly (see
tests/test_build_runner.py) so the safety flags are verified to be
present and correct as *text*, but actual daemon behavior -- especially
whether --internal networks behave as documented across Docker Desktop
versions and platforms -- has not been observed running for real.
Validate before relying on it.

Every run/stop attempt (successful or not) is written to the router's own
audit log (the same one GET /audit and the website's Observability page
already show), so build hosting isn't a blind spot.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

_SOURCE_BLOCK_RE = re.compile(r"### `([^`]+)`\n\n```[a-zA-Z0-9]*\n(.*?)\n```", re.DOTALL)
_REPO_ROOT = Path(__file__).resolve().parent.parent
_RUNNER_SCRIPT = Path(__file__).resolve().parent / "generic_app_runner.py"
_MAX_RUNTIME_S = 30 * 60  # auto-reap after 30 minutes so forgotten runs don't pile up
_SANDBOX_NETWORK = "kanosei-build-sandbox"
_CONTAINER_PREFIX = "kanosei-build-"
_DB_PATH = os.environ.get("ENTERPRISE_ROUTER_DB") or str(_REPO_ROOT / "enterprise_router.db")


def hosting_enabled() -> bool:
    return os.environ.get("ENTERPRISE_ROUTER_ENABLE_BUILD_HOSTING", "").strip().lower() in {"1", "true", "yes", "on"}


def docker_available() -> bool:
    return shutil.which("docker") is not None


def _log_audit(event_type: str, artifact_id: str, details: dict) -> None:
    """Best-effort: a failure to log must never break run/stop itself."""
    try:
        from enterprise_router.sqlite_storage import SQLiteStorage

        SQLiteStorage(_DB_PATH).log_audit(
            event_type, artifact_id, "admin", details, datetime.now(timezone.utc).isoformat()
        )
    except Exception as exc:  # pragma: no cover - logging must never be fatal
        print(f"[build_runner] audit log failed (non-fatal): {exc}")


def docker_run_cmd(*, container_name: str, network: str, port: int, workdir: str) -> list[str]:
    """Pure command construction, kept separate from execution so the
    safety flags are directly unit-testable without a real Docker daemon."""
    return [
        "docker", "run", "-d", "--rm",
        "--name", container_name,
        "--network", network,
        "--memory", "256m",
        "--cpus", "0.5",
        "--pids-limit", "64",
        "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges",
        "--read-only",
        "--tmpfs", "/tmp:size=16m,noexec",
        "--user", "65534:65534",
        "-e", "PYTHONDONTWRITEBYTECODE=1",
        "-v", f"{_RUNNER_SCRIPT}:/runner/generic_app_runner.py:ro",
        "-v", f"{workdir}:/workdir:ro",
        "-p", f"127.0.0.1:{port}:{port}",
        "python:3.13-slim",
        "python3", "/runner/generic_app_runner.py", "/workdir", str(port),
    ]


@dataclass
class RunningBuild:
    artifact_id: str
    port: int
    container_name: str
    workdir: str
    started_at: float
    class_name: str | None = None
    init_error: str | None = None


class BuildRunnerManager:
    def __init__(self) -> None:
        self._runs: dict[str, RunningBuild] = {}
        self._lock = threading.Lock()

    def extract_files(self, content: str) -> dict[str, str]:
        # A build's spec can itself quote a PRIOR artifact's full body as RAG
        # background context (engineering_agent.py's _augment_spec_with_rag_context)
        # -- and since that prior artifact may carry its own embedded
        # "## Generated Source" section, the same heading can appear more than
        # once in one artifact's content, with unrelated/truncated code inside
        # the quoted section confusing a naive regex scan across the whole
        # document. _artifact_body() always appends the artifact's OWN source
        # last, after everything else, so anchor extraction to content after
        # the LAST occurrence of the heading.
        marker = "\n## Generated Source\n\n"
        idx = content.rfind(marker)
        section = content[idx + len(marker):] if idx != -1 else content
        files = {}
        for filename, source in _SOURCE_BLOCK_RE.findall(section):
            files[filename.strip()] = source
        return files

    def _free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", 0))
            return s.getsockname()[1]

    def _ensure_sandbox_network(self) -> None:
        inspect = subprocess.run(
            ["docker", "network", "inspect", _SANDBOX_NETWORK],
            capture_output=True, text=True,
        )
        if inspect.returncode == 0:
            return
        create = subprocess.run(
            ["docker", "network", "create", "--internal", _SANDBOX_NETWORK],
            capture_output=True, text=True,
        )
        if create.returncode != 0 and "already exists" not in create.stderr:
            raise RuntimeError(f"Failed to create sandbox network: {create.stderr.strip()}")

    def start(self, artifact_id: str, content: str) -> dict:
        if not hosting_enabled():
            _log_audit("build_run_refused", artifact_id, {"reason": "hosting_disabled"})
            raise PermissionError(
                "Build hosting is disabled by policy. Set "
                "ENTERPRISE_ROUTER_ENABLE_BUILD_HOSTING=1 to enable it -- read the "
                "Enterprise Deployment Blueprint's critical-path section on what "
                "that means before doing so."
            )
        if not docker_available():
            _log_audit("build_run_refused", artifact_id, {"reason": "docker_unavailable"})
            raise RuntimeError(
                "Docker was not found on PATH. Build hosting requires Docker for "
                "sandboxing and does not fall back to unsandboxed execution."
            )

        with self._lock:
            self._reap_stale_locked()
            existing = self._runs.get(artifact_id)
            if existing and self._is_running(existing):
                return self._describe(existing)

            files = self.extract_files(content)
            if not files:
                _log_audit("build_run_refused", artifact_id, {"reason": "no_embedded_source"})
                raise ValueError("This artifact has no embedded generated source to run.")

            self._ensure_sandbox_network()

            workdir = Path(tempfile.mkdtemp(prefix=f"build_{artifact_id}_"))
            for rel, source in files.items():
                path = workdir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding="utf-8")

            port = self._free_port()
            container_name = f"{_CONTAINER_PREFIX}{artifact_id}"
            # In case a previous run's container leaked past its own --rm.
            subprocess.run(["docker", "rm", "-f", container_name], capture_output=True)

            cmd = docker_run_cmd(
                container_name=container_name, network=_SANDBOX_NETWORK, port=port, workdir=str(workdir),
            )
            launch = subprocess.run(cmd, capture_output=True, text=True)
            if launch.returncode != 0:
                shutil.rmtree(workdir, ignore_errors=True)
                _log_audit("build_run_failed", artifact_id, {"reason": "docker_run_failed", "stderr": launch.stderr.strip()})
                raise RuntimeError(f"Failed to start sandboxed container: {launch.stderr.strip()}")

            run = RunningBuild(
                artifact_id=artifact_id, port=port, container_name=container_name,
                workdir=str(workdir), started_at=time.time(),
            )
            ready = self._wait_for_ready(port)
            if ready:
                class_name, init_error = self._read_ready_status(container_name)
                run.class_name = class_name
                run.init_error = init_error

            self._runs[artifact_id] = run
            _log_audit("build_run_started", artifact_id, {
                "port": port, "container_name": container_name,
                "class_name": run.class_name, "init_error": run.init_error, "ready": ready,
            })
            return self._describe(run)

    def _wait_for_ready(self, port: int, timeout_s: float = 8.0) -> bool:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.5):
                    return True
            except OSError:
                time.sleep(0.2)
        return False

    def _read_ready_status(self, container_name: str) -> tuple[str | None, str | None]:
        logs = subprocess.run(["docker", "logs", container_name], capture_output=True, text=True)
        m = re.search(r"class=(\S+) instantiated=(\S+) error=(.*)", logs.stdout)
        if not m:
            return None, None
        class_name = None if m.group(1) == "None" else m.group(1)
        init_error = None if m.group(3) == "None" else m.group(3)
        return class_name, init_error

    def _is_running(self, run: RunningBuild) -> bool:
        result = subprocess.run(
            ["docker", "inspect", "-f", "{{.State.Running}}", run.container_name],
            capture_output=True, text=True,
        )
        return result.returncode == 0 and result.stdout.strip() == "true"

    def stop(self, artifact_id: str) -> bool:
        with self._lock:
            run = self._runs.pop(artifact_id, None)
            if run is None:
                return False
            self._terminate(run)
            _log_audit("build_run_stopped", artifact_id, {"container_name": run.container_name})
            return True

    def status(self) -> list[dict]:
        with self._lock:
            self._reap_stale_locked()
            return [self._describe(r) for r in self._runs.values()]

    def _reap_stale_locked(self) -> None:
        now = time.time()
        for artifact_id, run in list(self._runs.items()):
            if not self._is_running(run) or (now - run.started_at) > _MAX_RUNTIME_S:
                self._terminate(run)
                self._runs.pop(artifact_id, None)
                _log_audit("build_run_reaped", artifact_id, {"container_name": run.container_name})

    def _terminate(self, run: RunningBuild) -> None:
        subprocess.run(["docker", "rm", "-f", run.container_name], capture_output=True)
        shutil.rmtree(run.workdir, ignore_errors=True)

    def _describe(self, run: RunningBuild) -> dict:
        return {
            "artifact_id": run.artifact_id,
            "port": run.port,
            "url": f"http://localhost:{run.port}",
            "container_name": run.container_name,
            "started_at": run.started_at,
            "class_name": run.class_name,
            "init_error": run.init_error,
            "running": self._is_running(run),
        }


_manager: BuildRunnerManager | None = None


def get_manager() -> BuildRunnerManager:
    global _manager
    if _manager is None:
        _manager = BuildRunnerManager()
    return _manager
