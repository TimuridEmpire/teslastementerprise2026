import json
import os
from datetime import datetime, timezone, timedelta
from llm_provider import llm_json_array, llm_json_object
from pm_storage import storage
from agent_transport import AGENT_ENGINEERING, AGENT_MARKETING

def _resolve_project_id(name, payload, existing):
    payload_project_id = payload.get("project_id") if isinstance(payload, dict) else None
    if payload_project_id is not None:
        return payload_project_id
    if existing:
        return existing["id"]
    return None

def generate_features_llm(goal):
    prompt = (
        f"List 6 product features to achieve this goal: {goal}. "
        "Respond ONLY with a JSON array. Each item must have 'name' (string) "
        "and 'impact' (one of: high, medium, low). "
        "Example: [{\"name\": \"Feature A\", \"impact\": \"high\"}]"
    )
    features = llm_json_array(prompt)
    if not features:
        features = [
            {"name": "AI-Powered Analytics Dashboard", "impact": "high"},
            {"name": "Multi-Tenant SSO Integration", "impact": "high"},
            {"name": "Automated Onboarding Flow", "impact": "high"},
            {"name": "Usage-Based Billing Module", "impact": "medium"},
            {"name": "In-App Help Center", "impact": "medium"},
            {"name": "Dark Mode UI", "impact": "low"},
        ]
    return features

def moscow_prioritize(features):
    must = [f for f in features if f.get("impact") == "high"]
    should = [f for f in features if f.get("impact") == "medium"]
    could = [f for f in features if f.get("impact") == "low"]
    wont = [f for f in features if f.get("impact") not in ("high", "medium", "low")]
    return {"must": must, "should": should, "could": could, "wont": wont}

def save_backlog(data):
    os.makedirs("data", exist_ok=True)
    with open("data/backlog.json", "w") as f:
        json.dump(data, f, indent=2)

def create_project(name, goal, payload):
    existing = storage.find_active_project_by_name(name)
    resolved_id = _resolve_project_id(name, payload, existing)
    project = storage.upsert_project(
        name=name,
        goal=goal,
        payload=payload,
        project_id=resolved_id,
        description=(payload or {}).get("description", ""),
        status="active",
    )
    os.makedirs("data", exist_ok=True)
    projects = []
    if os.path.exists("data/projects.json"):
        with open("data/projects.json", "r") as f:
            projects = json.load(f)
    match_idx = next((idx for idx, p in enumerate(projects) if p.get("id") == project["id"]), None)
    record = {
        "id": project["id"],
        "name": project["name"],
        "goal": project["goal"],
        "payload": project.get("payload", {}),
        "description": project.get("description", ""),
        "created_at": project.get("created_at", datetime.now(timezone.utc).isoformat()),
        "updated_at": project.get("updated_at", datetime.now(timezone.utc).isoformat()),
        "status": project.get("status", "active"),
        "requests": [],
    }
    if match_idx is None:
        projects.append(record)
    else:
        previous_requests = projects[match_idx].get("requests", [])
        record["requests"] = previous_requests
        projects[match_idx] = record
    with open("data/projects.json", "w") as f:
        json.dump(projects, f, indent=2)
    return project

def add_request_to_project(project_id, request):
    if not os.path.exists("data/projects.json"):
        return
    with open("data/projects.json", "r") as f:
        projects = json.load(f)
    for p in projects:
        if p["id"] == project_id:
            p["requests"].append(request)
            break
    with open("data/projects.json", "w") as f:
        json.dump(projects, f, indent=2)
    storage.add_project_event(
        source="PM",
        event_type=request.get("type", "project_request"),
        project_id=project_id,
        message_id=request.get("message_id"),
        details=request,
    )

def generate_acceptance_criteria(feature_name, goal=""):
    """Auto-generate 3 simple acceptance criteria for a feature (LLM + fallback)."""
    prompt = (
        f"Write 3 concise acceptance criteria for the software feature '{feature_name}'"
        + (f" supporting the goal: {goal}." if goal else ".")
        + " Respond ONLY with a JSON array of short strings. "
        'Example: ["User can log in with email", "Errors show a clear message"]'
    )
    criteria = llm_json_array(prompt)
    cleaned = [str(c).strip() for c in criteria if str(c).strip()] if criteria else []
    if not cleaned:
        cleaned = [
            f"{feature_name} is implemented and accessible to the user",
            f"{feature_name} handles valid input without errors",
            f"{feature_name} has basic tests covering its core behavior",
        ]
    return cleaned


def generate_text_spec(feature_name, goal="", acceptance_criteria=None):
    """Produce a short written specification string for a feature.

    This REPLACES the old `spec_link` field from Example 2 of the requirements
    doc: per the engineering lead, the PM -> Engineering message now carries a
    self-contained, written-out spec instead of a URL. Uses the LLM when one is
    available and ALWAYS falls back to a deterministic template, so the PM agent
    never errors just because no model is running. Same LLM+fallback pattern as
    generate_acceptance_criteria() above.
    """
    acceptance_criteria = acceptance_criteria or []
    criteria_block = "\n".join(f"- {c}" for c in acceptance_criteria)
    prompt = (
        f"Write a short implementation specification (3-5 sentences) for the "
        f"software feature '{feature_name}'"
        + (f" which supports the goal: {goal}." if goal else ".")
        + " Describe what to build and the expected behavior. "
        "Respond ONLY with a JSON object of the form "
        '{"spec": "<the specification text>"}.'
    )
    result = llm_json_object(prompt)
    spec_text = ""
    if isinstance(result, dict):
        spec_text = str(result.get("spec", "")).strip()
    if not spec_text:
        spec_text = (
            f"Implement the '{feature_name}' feature"
            + (f" in support of the goal: {goal}." if goal else ".")
            + " It should be a working, tested component that satisfies the "
            "acceptance criteria below and integrates with the existing product."
        )
    if criteria_block:
        spec_text = f"{spec_text}\n\nAcceptance criteria:\n{criteria_block}"
    return spec_text


def derive_target_release(context=None):
    """Best-effort target release date (ISO yyyy-mm-dd) for Engineering.

    Example 2 carries `target_release` in context, so PM must supply one even
    though the CEO's DEFINE_Q2_ROADMAP message (Example 1) only gives quarter/
    year. Order of preference:
      1. An explicit target_release the CEO included in the inbound context.
      2. The last day of the quarter named in context (e.g. "Q2" -> 06-30).
      3. A default ~45 days out, so there is always a concrete date.
    """
    context = context or {}
    explicit = context.get("target_release")
    if explicit:
        return str(explicit)

    quarter = str(context.get("quarter", "")).upper().strip()
    year = context.get("year")
    quarter_end = {"Q1": (3, 31), "Q2": (6, 30), "Q3": (9, 30), "Q4": (12, 31)}
    if quarter in quarter_end and year:
        month, day = quarter_end[quarter]
        try:
            return f"{int(year):04d}-{month:02d}-{day:02d}"
        except (TypeError, ValueError):
            pass

    return (datetime.now(timezone.utc) + timedelta(days=45)).strftime("%Y-%m-%d")


def decide_routes(*, product, goal, prioritized, project_id, artifact_path=None,
                  target_release=None):
    """
    Decide which agents PM should message after defining a roadmap.

    Returns a list of route dicts: {recipient, task_type, context, payload}.
    Every task_type here must be one the recipient accepts (see the router's
    allowed_task_types): Marketing accepts LAUNCH_CAMPAIGN + PM_REPORT,
    Engineering accepts IMPLEMENT_FEATURE.

    target_release: ISO date string put in the Engineering message context to
    match Example 2. Pass derive_target_release(msg["context"]) from the handler.
    """
    must = prioritized.get("must", [])
    should = prioritized.get("should", [])
    routes = []

    # 1. Marketing: launch a campaign for the launch-ready feature set.
    routes.append({
        "recipient": AGENT_MARKETING,
        "task_type": "LAUNCH_CAMPAIGN",
        "context": {"project_id": project_id},
        "payload": {"product_name": product, "features": must + should},
    })

    # 2. Marketing: status report (includes the roadmap artifact location).
    report_payload = {
        "project_name": product,
        "must_count": len(must),
        "should_count": len(should),
        "status": "roadmap_defined",
    }
    if artifact_path:
        report_payload["artifact_path"] = artifact_path
    routes.append({
        "recipient": AGENT_MARKETING,
        "task_type": "PM_REPORT",
        "context": {"project_id": project_id},
        "payload": report_payload,
    })

    # 3. Engineering: one IMPLEMENT_FEATURE per must-have feature.
    for idx, feature in enumerate(must, start=1):
        feature_name = feature.get("name") if isinstance(feature, dict) else str(feature)
        criteria = generate_acceptance_criteria(feature_name, goal)

        # Match Example 2's context: priority + target_release (plus our
        # project_id for UI correlation). target_release is only added when we
        # actually have one, so we never send an empty field.
        eng_context = {"project_id": project_id, "priority": "high"}
        if target_release:
            eng_context["target_release"] = target_release

        routes.append({
            "recipient": AGENT_ENGINEERING,
            "task_type": "IMPLEMENT_FEATURE",
            "context": eng_context,
            "payload": {
                "feature_id": f"FT-{idx:03d}",
                "feature_name": feature_name,
                # Written text spec, replacing Example 2's spec_link per the
                # engineering lead. Field name "spec" is PENDING eng confirmation
                # (fallback name discussed: "text_spec") -- change here if needed.
                "spec": generate_text_spec(feature_name, goal, criteria),
                "acceptance_criteria": criteria,
            },
        })

    return routes
