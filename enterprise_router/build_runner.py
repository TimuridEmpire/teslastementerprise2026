"""Process manager for auto-hosting an Engineering build's generated code.

Extracts the source embedded in an artifact's content (see
engineering_agent.py's _artifact_body -- every generated file is embedded as
a fenced code block under "## Generated Source"), writes it to a fresh temp
directory, and spawns enterprise_router/generic_app_runner.py as its own
subprocess against that directory on a free local port.

Explicitly NOT sandboxed beyond process isolation and binding to localhost
only: this runs unreviewed LLM-generated code with the same OS permissions
as the router. That's an accepted tradeoff (self-hosted, single-operator
dev tool), not an oversight -- see the module docstring on generic_app_runner.py.
"""
from __future__ import annotations

import re
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

_SOURCE_BLOCK_RE = re.compile(r"### `([^`]+)`\n\n```[a-zA-Z0-9]*\n(.*?)\n```", re.DOTALL)
_RUNNER_SCRIPT = Path(__file__).resolve().parent / "generic_app_runner.py"
_MAX_RUNTIME_S = 30 * 60  # auto-reap after 30 minutes so forgotten runs don't pile up


@dataclass
class RunningBuild:
    artifact_id: str
    port: int
    pid: int
    process: subprocess.Popen
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

    def start(self, artifact_id: str, content: str) -> dict:
        with self._lock:
            self._reap_stale_locked()
            existing = self._runs.get(artifact_id)
            if existing and existing.process.poll() is None:
                return self._describe(existing)

            files = self.extract_files(content)
            if not files:
                raise ValueError("This artifact has no embedded generated source to run.")

            workdir = Path(tempfile.mkdtemp(prefix=f"build_{artifact_id}_"))
            for rel, source in files.items():
                path = workdir / rel
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(source, encoding="utf-8")

            port = self._free_port()
            process = subprocess.Popen(
                [sys.executable, str(_RUNNER_SCRIPT), str(workdir), str(port)],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )

            ready_line = self._wait_for_ready(process)
            run = RunningBuild(
                artifact_id=artifact_id, port=port, pid=process.pid, process=process,
                workdir=str(workdir), started_at=time.time(),
            )
            if ready_line:
                m = re.search(r"class=(\S+) instantiated=(\S+) error=(.*)", ready_line)
                if m:
                    run.class_name = None if m.group(1) == "None" else m.group(1)
                    run.init_error = None if m.group(3) == "None" else m.group(3)
            self._runs[artifact_id] = run
            return self._describe(run)

    def _wait_for_ready(self, process: subprocess.Popen, timeout_s: float = 5.0) -> str | None:
        deadline = time.time() + timeout_s
        while time.time() < deadline:
            if process.poll() is not None:
                return None
            line = process.stdout.readline() if process.stdout else ""
            if line.startswith("READY"):
                return line.strip()
            if not line:
                time.sleep(0.05)
        return None

    def stop(self, artifact_id: str) -> bool:
        with self._lock:
            run = self._runs.pop(artifact_id, None)
            if run is None:
                return False
            self._terminate(run)
            return True

    def status(self) -> list[dict]:
        with self._lock:
            self._reap_stale_locked()
            return [self._describe(r) for r in self._runs.values()]

    def _reap_stale_locked(self) -> None:
        now = time.time()
        for artifact_id, run in list(self._runs.items()):
            if run.process.poll() is not None or (now - run.started_at) > _MAX_RUNTIME_S:
                self._terminate(run)
                self._runs.pop(artifact_id, None)

    def _terminate(self, run: RunningBuild) -> None:
        try:
            run.process.terminate()
            run.process.wait(timeout=3)
        except Exception:
            try:
                run.process.kill()
            except Exception:
                pass
        shutil.rmtree(run.workdir, ignore_errors=True)

    def _describe(self, run: RunningBuild) -> dict:
        return {
            "artifact_id": run.artifact_id,
            "port": run.port,
            "url": f"http://localhost:{run.port}",
            "pid": run.pid,
            "started_at": run.started_at,
            "class_name": run.class_name,
            "init_error": run.init_error,
            "running": run.process.poll() is None,
        }


_manager: BuildRunnerManager | None = None


def get_manager() -> BuildRunnerManager:
    global _manager
    if _manager is None:
        _manager = BuildRunnerManager()
    return _manager
