import json
import os
from llm_provider import llm_json_object
from pm_storage import storage

def plan_campaign(product, features):
    feature_names = [f["name"] if isinstance(f, dict) else f for f in features]
    prompt = (
        f"Plan a marketing campaign for {product} with features: {feature_names}. "
        "Respond ONLY with a JSON object with these keys: "
        "'product' (string), 'tagline' (string), 'channel' (string), "
        "'budget' (integer USD), 'expected_leads' (integer), 'timeline_weeks' (integer). "
        "No explanation, just the JSON object."
    )
    campaign = llm_json_object(prompt)
    if campaign:
        campaign["product"] = campaign.get("product", product)
        campaign["features"] = feature_names
    else:
        feature_names = [f["name"] if isinstance(f, dict) else f for f in features]
        campaign = {
            "product": product,
            "features": feature_names,
            "tagline": f"Unlock the power of {product}",
            "channel": "Email + Social Media",
            "budget": 8000,
            "expected_leads": 150,
            "timeline_weeks": 6
        }
    return campaign

def save_campaign(campaign):
    os.makedirs("data", exist_ok=True)
    existing = []
    if os.path.exists("data/campaigns.json"):
        with open("data/campaigns.json", "r") as f:
            existing = json.load(f)
    existing.append(campaign)
    with open("data/campaigns.json", "w") as f:
        json.dump(existing, f, indent=2)
    storage.save_campaign(campaign)

def generate_email(product: str, tagline: str, features: list, channel: str = "email") -> dict:
    feature_names = [f["name"] if isinstance(f, dict) else f for f in features]
    prompt = (
        f"Write a marketing email for the product '{product}'. "
        f"Tagline: '{tagline}'. Key features: {feature_names}. Channel: {channel}. "
        "Respond ONLY with a JSON object with keys: "
        "'subject' (string), 'body' (plain-text with \\n line breaks), 'html_body' (simple HTML). "
        "No explanation outside the JSON."
    )
    result = llm_json_object(prompt)
    if result and result.get("subject") and result.get("body"):
        result.setdefault("html_body", "")
        return result
    # Fallback
    feature_bullets = "\n".join(f"  • {n}" for n in feature_names)
    html_bullets = "".join(f"<li>{n}</li>" for n in feature_names)
    return {
        "subject": f"Introducing {product} — {tagline}",
        "body": f"Hi there,\n\nWe're excited to introduce {product} — {tagline}\n\nKey features:\n{feature_bullets}\n\nReply to book a demo.\n\nBest,\nThe {product} Team",
        "html_body": f"<p>Hi there,</p><p><strong>{product}</strong> — {tagline}</p><ul>{html_bullets}</ul><p><a href='#'>Book a demo</a></p>",
    }


def generate_image_prompt(product: str, tagline: str, features: list, style: str = "photorealistic") -> dict:
    feature_names = [f["name"] if isinstance(f, dict) else f for f in features]
    prompt = (
        f"Create an image generation prompt for a marketing visual for '{product}'. "
        f"Tagline: '{tagline}'. Features: {feature_names}. Style: {style}. "
        "Respond ONLY with a JSON object with keys: "
        "'prompt' (detailed image prompt, max 200 words), "
        "'negative_prompt' (comma-separated terms to avoid), "
        "'suggested_size' (one of: '1024x1024', '1792x1024', '1024x1792'). "
        "No explanation outside the JSON."
    )
    result = llm_json_object(prompt)
    if result and result.get("prompt"):
        result.setdefault("negative_prompt", "blurry, watermark, text overlay, low quality")
        result.setdefault("suggested_size", "1792x1024")
        return result
    # Fallback
    return {
        "prompt": f"A sleek {style} marketing banner for {product}. Clean workspace, glowing screens showing {', '.join(feature_names[:2])}. Blue and white palette, professional lighting, no text.",
        "negative_prompt": "blurry, watermark, text overlay, low quality, distorted",
        "suggested_size": "1792x1024",
    }