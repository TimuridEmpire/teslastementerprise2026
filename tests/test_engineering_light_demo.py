from __future__ import annotations

import importlib.util
from pathlib import Path


def load_engineering_module():
    path = Path(__file__).resolve().parents[1] / "eng-agents" / "engineering_agent.py"
    spec = importlib.util.spec_from_file_location("engineering_agent_under_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def sample_implement_feature() -> dict:
    return {
        "id": "eng-msg-1",
        "timestamp": "2026-05-26T00:00:00Z",
        "sender": "PM",
        "recipient": "Engineering",
        "task_type": "IMPLEMENT_FEATURE",
        "context": {"project_id": "project-1", "run_id": "run-1"},
        "payload": {
            "feature_id": "FT-001",
            "feature_name": "Live artifact panel",
            "spec": "Build a dashboard panel that renders live artifacts.",
            "acceptance_criteria": ["Shows newest artifact", "Does not show fake output as live"],
        },
        "status": "pending",
        "error": "",
    }


def sample_manager_intervention(instruction: str = "Build a scientific calculator.") -> dict:
    """Shape sent by website/components/chat/CommandChat.tsx's `/eng <text>`
    command: POST /manager/interventions -> EnterpriseRouter.
    submit_manager_intervention() always folds the free-text instruction
    into payload["instruction"]."""
    return {
        "id": "eng-msg-2",
        "timestamp": "2026-05-26T00:00:00Z",
        "sender": "MANAGER",
        "recipient": "Engineering",
        "task_type": "MANAGER_INTERVENTION",
        "context": {"source": "command_chat"},
        "payload": {"instruction": instruction},
        "status": "pending",
        "error": "",
    }


def test_detect_file_list_mistakes_flags_tab_separator():
    module = load_engineering_module()

    mistakes = module.FullSystem._detect_file_list_mistakes("flight_app.py,config.py,models.py\ttests.py")

    assert len(mistakes) == 1
    assert "comma" in mistakes[0].lower()


def test_detect_file_list_mistakes_flags_folder_path():
    module = load_engineering_module()

    mistakes = module.FullSystem._detect_file_list_mistakes("app.py,tests/tests.py")

    assert len(mistakes) == 1
    assert "folder" in mistakes[0].lower()


def test_detect_file_list_mistakes_clean_output_has_none():
    module = load_engineering_module()

    assert module.FullSystem._detect_file_list_mistakes("app.py,tests.py") == []


def test_extract_error_type_prefers_the_last_raised_exception():
    module = load_engineering_module()
    traceback_text = (
        "Traceback (most recent call last):\n"
        '  File "app.py", line 3, in <module>\n'
        "    import missing_thing\n"
        "ModuleNotFoundError: No module named 'missing_thing'\n"
        "\n"
        "During handling of the above exception, another exception occurred:\n"
        "\n"
        "TypeError: add_task() missing 1 required positional argument: 'due_date'"
    )

    result = module.FullSystem._extract_error_type(traceback_text)

    assert result == "TypeError: add_task() missing 1 required positional argument: 'due_date'"


def test_extract_error_type_returns_none_for_unrecognizable_output():
    module = load_engineering_module()

    assert module.FullSystem._extract_error_type("something went wrong, no idea what") is None


def test_record_lesson_and_recent_lessons_round_trip(monkeypatch, tmp_path):
    """Regression coverage for the "self-learning" feature: a role's own
    past, deterministically-detected mistakes (see _detect_file_list_mistakes
    / _record_test_failure_lesson) get recorded and read back scoped to
    that role, deduplicated, most-recently-repeated first -- not real
    fine-tuning (the local Ollama models are never retrained), just a
    persistent mistake log injected back into that role's future prompts."""
    monkeypatch.setenv("ENTERPRISE_ROUTER_DB", str(tmp_path / "router.db"))
    module = load_engineering_module()

    module.record_lesson("Lead Developer", "rule A")
    module.record_lesson("Lead Developer", "rule B")
    module.record_lesson("Lead Developer", "rule A")  # repeat -- should not duplicate
    module.record_lesson("Software Developer", "unrelated role rule")

    assert module.recent_lessons("Lead Developer") == ["rule A", "rule B"]
    assert module.recent_lessons("Software Developer") == ["unrelated role rule"]
    assert module.recent_lessons("Testing Engineer") == []


def test_recent_lessons_never_raises_when_store_unavailable(monkeypatch):
    module = load_engineering_module()

    class _RaisingStorage:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("simulated storage failure")

    import enterprise_router.sqlite_storage as sqlite_storage_module
    monkeypatch.setattr(sqlite_storage_module, "SQLiteStorage", _RaisingStorage)

    assert module.recent_lessons("Lead Developer") == []


def test_log_swarm_event_writes_to_the_routers_audit_log(monkeypatch, tmp_path):
    """review_and_iterate() runs a real multi-agent swarm -- a Lead
    Developer agent plans and reviews, a Software Developer agent writes
    code, a Testing Engineer agent writes and evaluates tests -- but until
    log_swarm_event() existed, none of that was visible anywhere outside
    the worker's own stdout. It must land in the same audit log GET
    /audit and the website's Observability page already read from."""
    db_path = tmp_path / "router.db"
    monkeypatch.setenv("ENTERPRISE_ROUTER_DB", str(db_path))
    module = load_engineering_module()

    module.log_swarm_event("swarm-abc123", "Software Developer", "wrote_file", "weather_app.py")

    from enterprise_router.sqlite_storage import SQLiteStorage
    rows = SQLiteStorage(str(db_path)).list_audit_log(limit=10)

    assert len(rows) == 1
    assert rows[0]["event_type"] == "swarm_activity"
    assert rows[0]["subject_id"] == "swarm-abc123"
    assert rows[0]["actor"] == "Software Developer"
    assert rows[0]["details"]["phase"] == "wrote_file"
    assert rows[0]["details"]["detail"] == "weather_app.py"


def test_log_swarm_event_never_raises_even_if_logging_fails(monkeypatch):
    module = load_engineering_module()

    class _RaisingStorage:
        def __init__(self, *_args, **_kwargs):
            raise RuntimeError("simulated storage failure")

    import enterprise_router.sqlite_storage as sqlite_storage_module
    monkeypatch.setattr(sqlite_storage_module, "SQLiteStorage", _RaisingStorage)

    module.log_swarm_event("swarm-x", "Lead Developer", "planned", "irrelevant")  # must not raise


def test_parse_file_list_handles_a_tab_instead_of_a_comma():
    """Regression test: reproduced live building a "flight app" via the CEO
    reasoning loop -- the lead agent's file-list output used a tab between
    the last two filenames instead of a comma ("models.py\\ttests.py"),
    which the old str.split(",") parser left as one corrupted filename.
    Every subsequent file write and test run then silently operated on
    that garbage path, and the fix-feedback loop couldn't recover because
    the corrupted name was never regenerated across iterations."""
    module = load_engineering_module()

    files = module.FullSystem._parse_file_list("flight_app.py,config.py,routes.py,models.py\ttests.py")

    assert files == ["flight_app.py", "config.py", "routes.py", "models.py", "tests.py"]


def test_parse_file_list_strips_folder_prefixes():
    """Regression test: reproduced live -- the lead agent output
    "tests/tests.py" despite being told not to use folder structure."""
    module = load_engineering_module()

    files = module.FullSystem._parse_file_list("app.py,tests/tests.py")

    assert files == ["app.py", "tests.py"]


def test_parse_file_list_drops_non_filename_noise():
    module = load_engineering_module()

    files = module.FullSystem._parse_file_list("app.py, here is your list:, tests.py")

    assert files == ["app.py", "tests.py"]


def test_split_testing_file_finds_tests_file_out_of_position():
    """Regression test: reproduced live building a To-Do List app -- the
    lead agent's file list was "README.md, requirements.txt, to_do_list.py,
    tests/tests.py, .gitignore, config.py" (tests file in the middle,
    config.py last). Code that trusted files[-1] wrote test content into
    config.py and ran "tests" against it instead of the real test file,
    guaranteeing every test run failed regardless of what Software
    Developer actually wrote."""
    module = load_engineering_module()
    files = module.FullSystem._parse_file_list(
        "README.md,requirements.txt,to_do_list.py,tests/tests.py,.gitignore,config.py"
    )

    testing_file, source_files = module.FullSystem._split_testing_file(files)

    assert testing_file == "tests.py"
    assert source_files == ["README.md", "requirements.txt", "to_do_list.py", ".gitignore", "config.py"]


def test_split_testing_file_falls_back_to_last_item_when_nothing_matches():
    module = load_engineering_module()

    testing_file, source_files = module.FullSystem._split_testing_file(["a.py", "b.py"])

    assert testing_file == "b.py"
    assert source_files == ["a.py"]


def test_ollama_base_url_honors_env_override(monkeypatch):
    """Regression test: the module-level Ollama LLM client used to hardcode
    base_url="http://localhost:11434" directly. Inside a container that's
    the container's own loopback, not wherever Ollama actually runs --
    Engineering would silently fail to reach it in any multi-container
    deployment (e.g. the Docker Compose bundle)."""
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://ollama:11434")
    module = load_engineering_module()

    assert module.OLLAMA_BASE_URL == "http://ollama:11434"


def test_augment_spec_with_rag_context_puts_the_real_spec_first(monkeypatch):
    """Regression test: reproduced live, a request for "a weather app" built
    a calculator instead, because retrieve_rag_context() returned a prior,
    similar-looking calculator spec that used to be prepended *before* the
    real instruction -- the local model fixated on the retrieved text
    instead of the actual spec. The real spec must now come first, and the
    retrieved block must be unambiguously marked as reference-only."""
    module = load_engineering_module()
    monkeypatch.setattr(
        module,
        "retrieve_rag_context",
        lambda query, **kwargs: [{"agent_name": "Engineering", "title": "Old Calculator", "score": 0.9, "snippet": "Feature: Calculator..."}],
    )
    monkeypatch.setattr(
        module,
        "format_rag_context_block",
        lambda hits, **kwargs: "## Related prior engineering specs/code\n- [Engineering] Old Calculator: Feature: Calculator...",
    )

    agent = module.EngineeringAgent(db=None)
    real_spec = "Feature: Weather Lookup App\nDescription: Build a weather classification module."
    augmented = agent._augment_spec_with_rag_context(real_spec)

    assert augmented.startswith(real_spec)
    assert augmented.index(real_spec) < augmented.index("Old Calculator")
    assert "background only" in augmented.lower()
    assert "do not implement" in augmented.lower()


def test_engineering_light_demo_writes_artifact_and_returns_feature_response(monkeypatch):
    module = load_engineering_module()
    monkeypatch.setenv("ENGINEERING_LIGHT_DEMO", "1")
    monkeypatch.setattr(module, "write_agent_artifact", lambda *args, **kwargs: {"artifact_id": "art-eng"})
    monkeypatch.setattr(module.EngineeringAgent, "_generated_files", lambda _self: [])

    agent = module.EngineeringAgent(db=None)
    response = agent.handle_message(sample_implement_feature())

    assert response["sender"] == "Engineering"
    assert response["recipient"] == "PM"
    assert response["task_type"] == "FEATURE_RESPONSE"
    assert response["status"] == "done"
    assert response["payload"]["artifact_id"] == "art-eng"
    assert response["payload"]["details"]["status"] == "light_demo"
    assert response["payload"]["generated_files"] == []


def test_engineering_handles_manager_intervention_from_chat_eng_command(monkeypatch):
    """Regression test: the website Chat page's `/eng <request>` command
    sends task_type MANAGER_INTERVENTION (Engineering is registered to
    accept it — scripts/bootstrap_router_agents.py) but engineering_agent.py
    previously had no handler for it, so every `/eng` request errored out
    instead of building anything."""
    module = load_engineering_module()
    monkeypatch.setenv("ENGINEERING_LIGHT_DEMO", "1")
    monkeypatch.setattr(module, "write_agent_artifact", lambda *args, **kwargs: {"artifact_id": "art-calc"})
    monkeypatch.setattr(module.EngineeringAgent, "_generated_files", lambda _self: [])

    agent = module.EngineeringAgent(db=None)
    response = agent.handle_message(sample_manager_intervention("Build a scientific calculator."))

    assert response["sender"] == "Engineering"
    assert response["recipient"] == "MANAGER"
    assert response["task_type"] == "FEATURE_RESPONSE"
    assert response["status"] == "done"
    assert response["payload"]["artifact_id"] == "art-calc"
    assert response["payload"]["details"]["status"] == "light_demo"
    assert "scientific calculator" in response["payload"]["details"]["spec_preview"]


def test_artifact_body_embeds_generated_source_before_next_clean(monkeypatch, tmp_path):
    """Regression test: OUTPUT_DIR is one shared scratch directory that
    _clean_output_dir() wipes at the start of the *next* build, so a past
    build's code was only ever visible on disk until something else ran --
    e.g. the weather app build got silently overwritten by a later
    calculator build, with no way to recover its code from the control
    plane afterward. _artifact_body() must embed the actual source into the
    artifact while the files still exist."""
    monkeypatch.setenv("OUTPUT_DIR", str(tmp_path))
    module = load_engineering_module()

    (tmp_path / "weather_app.py").write_text("class WeatherApp:\n    pass\n", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "weather_app.cpython-313.pyc").write_bytes(b"\x00\x01")

    agent = module.EngineeringAgent(db=None)
    body = agent._artifact_body("Build a weather app.", result={"status": "success", "iterations": 1})

    assert "## Generated Source" in body
    assert "weather_app.py" in body
    assert "class WeatherApp" in body
    assert "```python" in body
    # __pycache__ is build noise, not source -- it should not be listed or embedded.
    assert "__pycache__" not in body


def test_engineering_manager_intervention_without_instruction_fails_cleanly(monkeypatch):
    module = load_engineering_module()
    monkeypatch.setenv("ENGINEERING_LIGHT_DEMO", "1")
    monkeypatch.setattr(module, "write_agent_artifact", lambda *args, **kwargs: {"artifact_id": "art-err"})
    monkeypatch.setattr(module.EngineeringAgent, "_generated_files", lambda _self: [])

    agent = module.EngineeringAgent(db=None)
    message = sample_manager_intervention("")
    message["payload"] = {}

    response = agent.handle_message(message)

    assert response["status"] == "error"
    assert response["recipient"] == "MANAGER"
    assert "instruction" in response["payload"]["error"]
