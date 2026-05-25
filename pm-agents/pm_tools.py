import json
import os
from datetime import datetime, timezone
from llm_provider import llm_json_array
from pm_storage import storage

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