"""Grounded nutrition chat and a separate food-recognition adapter.

Calorie and safety numbers always come from the Python services. A language
model may only explain records that were already loaded. Without an API key
the consultant uses those records directly and says so.
"""

from __future__ import annotations

import json

import httpx

from app.core.config import get_settings


def _llm() -> dict:
    settings = get_settings()
    if settings.groq_api_key:
        return {
            "key": settings.groq_api_key,
            "base": settings.groq_base_url.rstrip("/"),
            "chat": settings.groq_chat_model,
            "vision": settings.groq_vision_model,
            "provider": "groq",
        }
    return {
        "key": settings.openai_api_key,
        "base": settings.openai_base_url.rstrip("/"),
        "chat": settings.openai_chat_model,
        "vision": settings.openai_vision_model,
        "provider": settings.ai_provider,
    }


def _complete(system: str, user: str, timeout: float = 20) -> str | None:
    llm = _llm()
    if not llm["key"]:
        return None
    try:
        response = httpx.post(
            f"{llm['base']}/chat/completions",
            headers={"Authorization": f"Bearer {llm['key']}", "User-Agent": "FitDesi/1.0"},
            json={
                "model": llm["chat"],
                "temperature": 0.3,
                "max_tokens": 400,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
            },
            timeout=timeout,
        )
        response.raise_for_status()
        message = response.json()["choices"][0]["message"]
        content = (message.get("content") or message.get("reasoning") or "").strip()
        return content or None
    except Exception:
        return None


def _fallback(message: str, context: dict, language: str) -> str:
    diary = context.get("today") or {}
    plan = context.get("plan") or {}
    foods = context.get("food_matches") or []
    consumed = diary.get("energy_kcal")
    target = plan.get("calorie_target")
    remaining = None
    if consumed is not None and target is not None:
        remaining = round(target - consumed, 1)
    lower = message.lower()
    if any(word in lower for word in ("biryani", "paratha")):
        line = "Yes, you can include it while losing weight if the portion fits the day's calorie target. "
        if foods:
            food = foods[0]
            line += f"The catalogue estimate for {food['name']} is {food.get('energy_kcal')} kcal per 100 g. "
        if remaining is not None:
            line += f"You have about {remaining} kcal remaining against today's target. "
        elif consumed is None:
            line += "There is no food logged today, so I cannot say what you have already eaten. "
        return line + "This is an estimate, not a promise, and it does not account for unlogged oil."
    if "breakfast" in lower and "calor" in lower:
        breakfast = diary.get("breakfast_kcal")
        if breakfast is None:
            return "Breakfast has no logged items today, so I will not invent a calorie total."
        return f"Logged breakfast is {breakfast} kcal. Missing nutrients are left unknown rather than treated as zero."
    if "protein" in lower or "dinner" in lower:
        if foods:
            names = ", ".join(food["name"] for food in foods[:3])
            return f"From the foods available to you, higher-protein options include {names}. Portions still have to fit the calorie target."
        return "I need foods in the catalogue that match your diet before I suggest a dinner."
    if "weight" in lower or "progress" in lower:
        trend = context.get("weight") or {}
        if trend.get("points", 0) < 2:
            return "There are not enough weight entries to explain a trend. One day's change is only a fluctuation."
        return (
            f"From {trend['points']} entries, weight changed by {trend.get('change')} kg from the first saved entry. "
            "Look at the weekly average rather than a single morning."
        )
    if "step" in lower:
        steps = context.get("steps")
        goal = context.get("step_target")
        if steps is None:
            return "No step record is saved for today. You can enter steps manually or sync a health source."
        return f"Today's selected step source shows {steps} steps. The target is {goal}. Sources are not added together."
    if consumed is None and target is None:
        return (
            "I can use your saved diary, weight, and plan. Nothing is logged for today and there is no active calorie target yet. "
            "I will not invent intake or promise a goal date."
        )
    parts = []
    if target is not None:
        parts.append(f"Your current calorie target is {target} kcal.")
    if consumed is None:
        parts.append("No food is logged today.")
    else:
        parts.append(f"Logged intake is {consumed} kcal.")
    parts.append("I do not diagnose conditions or recommend an extreme diet.")
    return " ".join(parts)


def explain_plan(summary: dict) -> str:
    text = _complete(
        "You are FitDesi's coach. Explain this calculated plan in two short English sentences. "
        "Do not change the numbers. Do not promise a date. Do not give medical advice.",
        json.dumps(summary),
        timeout=18,
    )
    if text:
        return text
    if summary.get("safety_status") == "blocked":
        return summary.get("blocked_reason") or "This target was slowed down so the deficit stays moderate."
    target = summary.get("calorie_target")
    if target:
        return f"Your calculated target is {target} kcal. Portions are estimates from the food catalogue, not a medical prescription."
    return "The plan uses your saved measurements. Missing numbers stay unknown rather than zero."


def daily_tip(context: dict) -> str:
    text = _complete(
        "Give one practical English sentence for today. Use only the JSON. If a value is null, say it is not logged. Do not invent meals.",
        json.dumps(context),
        timeout=12,
    )
    if text:
        return text
    consumed = (context.get("today") or {}).get("energy_kcal")
    target = (context.get("plan") or {}).get("calorie_target")
    if consumed is None:
        return "Nothing is logged yet today. Search a stored food and add a portion."
    if target is not None:
        return f"You have logged {consumed} kcal toward a {target} kcal target."
    return f"You have logged {consumed} kcal today."


def choose_meal(candidates: list[dict], remaining: float | None) -> dict:
    if not candidates:
        return {"food_id": None, "name": None, "reason": "No stored foods are available to suggest."}
    text = _complete(
        "Pick exactly one food from the JSON list. Reply with JSON only: "
        '{"id": 0, "reason": "one English sentence"}. Do not invent a food that is not in the list.',
        json.dumps({"remaining_kcal": remaining, "foods": candidates}),
        timeout=12,
    )
    chosen = candidates[0]
    reason = "This is a stored catalogue food. The calorie figure is an estimate per 100 g."
    if text:
        start, end = text.find("{"), text.rfind("}")
        if start >= 0 and end > start:
            try:
                parsed = json.loads(text[start:end + 1])
                match = next((item for item in candidates if item["id"] == parsed.get("id")), None)
                if match:
                    chosen = match
                    if parsed.get("reason"):
                        reason = str(parsed["reason"])
            except json.JSONDecodeError:
                pass
    return {
        "food_id": chosen["id"],
        "name": chosen["name"],
        "energy_kcal": chosen.get("energy_kcal"),
        "default_serving_g": chosen.get("default_serving_g"),
        "reason": reason,
    }


def consultant_reply(message: str, context: dict, language: str) -> dict:
    llm = _llm()
    provider = "fallback"
    if llm["key"]:
        system = (
            "You are FitDesi's nutrition coach. Reply in English. Use only the JSON context for the user's records. "
            "If a value is null, say it was not logged. Do not invent meals, weight, or steps. "
            "Do not diagnose or prescribe an extreme diet. Say that portions and cooked dishes are estimates."
        )
        content = _complete(system, json.dumps({"question": message, "context": context}), timeout=25)
        if content:
            return {"content": content, "provider": llm["provider"], "estimate": True}
        provider = "fallback_after_provider_error"
    return {"content": _fallback(message, context, language), "provider": provider, "estimate": True}


def recognise_foods(image_bytes: bytes, content_type: str) -> dict:
    llm = _llm()
    if not llm["key"] or not llm["vision"]:
        return {
            "status": "provider_not_configured",
            "provider": "unconfigured",
            "predictions": [],
            "message": "Photo recognition is not available on this AI account. Search the food by name. A photo cannot reveal hidden oil or ingredients.",
        }
    import base64

    encoded = base64.b64encode(image_bytes).decode("ascii")
    prompt = (
        "Identify likely foods in this meal photo. Reply with JSON only: "
        '{"items":[{"name":"","confidence":0.0,"portion_note":""}]}. '
        "Confidence is 0 to 1. Never claim exact oil, salt, or hidden ingredients. These are estimates."
    )
    try:
        response = httpx.post(
            f"{llm['base']}/chat/completions",
            headers={"Authorization": f"Bearer {llm['key']}", "User-Agent": "FitDesi/1.0"},
            json={
                "model": llm["vision"],
                "temperature": 0,
                "messages": [{
                    "role": "user",
                    "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": f"data:{content_type};base64,{encoded}"}},
                    ],
                }],
            },
            timeout=50,
        )
        response.raise_for_status()
        raw = response.json()["choices"][0]["message"]["content"]
        start = raw.find("{")
        end = raw.rfind("}")
        parsed = json.loads(raw[start:end + 1]) if start >= 0 else {"items": []}
        return {
            "status": "estimated",
            "provider": llm["provider"],
            "predictions": parsed.get("items") or [],
            "message": "These matches are estimates. Confirm the food and portion before saving.",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "provider_error",
            "provider": llm["provider"],
            "predictions": [],
            "message": f"The vision provider did not return a usable result ({exc.__class__.__name__}). Enter the food manually.",
        }
