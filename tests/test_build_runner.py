from __future__ import annotations

import pytest

import enterprise_router.build_runner as build_runner
from enterprise_router.build_runner import BuildRunnerManager, docker_run_cmd


def test_extract_files_ignores_rag_quoted_source_from_a_prior_artifact():
    """Regression test: reproduced live building a clock app. Once artifacts
    embed their own generated source (engineering_agent.py's _artifact_body),
    RAG retrieval can quote a PRIOR artifact's full body -- including that
    prior artifact's own "## Generated Source" section -- as background
    context inside the CURRENT artifact's "## Engineering Request" section.
    That produced two "## Generated Source" headings in one artifact, and a
    naive whole-document regex scan matched a code fence spanning from the
    first (quoted, truncated) heading all the way to the real closing fence
    of the current build's own file, misattributing clock_app.py's real
    source under the quoted weather_app.py filename entirely. Extraction
    must anchor to the artifact's own section (always the last occurrence)."""
    content = (
        "## Engineering Request\n\n"
        "Feature: Clock App\n\n"
        "--- The section below is background only, from unrelated prior "
        "work. Do NOT implement anything described in it -- implement "
        "ONLY the spec above. ---\n\n"
        "## Related prior engineering specs/code (semantic retrieval)\n"
        "- [Engineering] Engineering Feature Implementation (similarity 0.69): "
        "# Engineering Feature Implementation\n\n## Generated Source\n\n"
        "### `weather_app.py`\n\n```python\nclass WeatherApp:\n"
        "    def get_forecast(self, city, temperature_celsius):\n"
        "        if not isinstance(temperature_celsius, (int, float)):\n"
        "            raise ValueError(\"Temperature must be a number\")\n"
        "        if temperature_celsius < 10:\n\n"
        "## Generated Files\n\n- `clock_app.py`\n\n"
        "## Test Status\n\npassed\n\n"
        "## Generated Source\n\n"
        "### `clock_app.py`\n\n"
        "```python\n"
        "class Clock:\n"
        "    def current_time(self, hour, minute, second):\n"
        "        return f'{hour:02}:{minute:02}:{second:02}'\n"
        "```\n"
    )

    files = BuildRunnerManager().extract_files(content)

    assert set(files.keys()) == {"clock_app.py"}
    assert "class Clock" in files["clock_app.py"]
    assert "WeatherApp" not in files["clock_app.py"]


def test_start_refuses_when_hosting_disabled_by_default(monkeypatch):
    """Fail-closed by default: Run must not be usable until an operator
    explicitly opts in. This runs unreviewed LLM-generated code -- it
    should never be on just because nobody thought to turn it off."""
    monkeypatch.delenv("ENTERPRISE_ROUTER_ENABLE_BUILD_HOSTING", raising=False)

    with pytest.raises(PermissionError, match="disabled by policy"):
        BuildRunnerManager().start("art-x", "## Generated Source\n\n### `a.py`\n\n```python\npass\n```\n")


def test_start_refuses_when_docker_unavailable(monkeypatch):
    """No unsandboxed subprocess fallback: earlier versions of this module
    ran generated code as a plain subprocess with the router's own OS
    permissions when nothing better was available. That's the exact gap
    the Enterprise Deployment Blueprint flagged as blocking GA -- Run must
    refuse outright rather than silently degrade to it."""
    monkeypatch.setenv("ENTERPRISE_ROUTER_ENABLE_BUILD_HOSTING", "1")
    monkeypatch.setattr(build_runner, "docker_available", lambda: False)

    with pytest.raises(RuntimeError, match="Docker was not found"):
        BuildRunnerManager().start("art-x", "## Generated Source\n\n### `a.py`\n\n```python\npass\n```\n")


def test_start_refuses_without_embedded_source_even_when_enabled(monkeypatch):
    monkeypatch.setenv("ENTERPRISE_ROUTER_ENABLE_BUILD_HOSTING", "1")
    monkeypatch.setattr(build_runner, "docker_available", lambda: True)

    with pytest.raises(ValueError, match="no embedded generated source"):
        BuildRunnerManager().start("art-x", "## Engineering Request\n\nNo source embedded.\n")


def test_docker_run_cmd_isolates_network_and_drops_privileges():
    """The actual Docker daemon behavior isn't verified in this environment
    (no daemon available) -- but the command text itself is, so a future
    edit can't silently drop a safety flag without a test failing."""
    cmd = docker_run_cmd(
        container_name="kanosei-build-art-x", network="kanosei-build-sandbox",
        port=54321, workdir="/tmp/some-workdir",
    )

    # Isolated from the internet/host network, not just "some" network.
    assert "--network" in cmd
    assert cmd[cmd.index("--network") + 1] == "kanosei-build-sandbox"
    # No root, no capabilities, no privilege escalation, no writable rootfs.
    assert "--user" in cmd
    assert cmd[cmd.index("--user") + 1] == "65534:65534"
    assert "--cap-drop" in cmd
    assert cmd[cmd.index("--cap-drop") + 1] == "ALL"
    assert "--security-opt" in cmd
    assert cmd[cmd.index("--security-opt") + 1] == "no-new-privileges"
    assert "--read-only" in cmd
    # Hard resource caps -- a fork bomb or memory hog can't take the host down.
    assert "--memory" in cmd
    assert "--cpus" in cmd
    assert "--pids-limit" in cmd
    # Generated code is mounted read-only -- the sandboxed process can't
    # modify its own source out from under the extraction that produced it.
    assert any(":/workdir:ro" in part for part in cmd)
    # Published only to localhost, matching the rest of this project's
    # "bound to localhost" posture -- not exposed on all interfaces.
    assert any(part.startswith("127.0.0.1:54321:") for part in cmd)
