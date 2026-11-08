"""Grounded nutrition chat and a separate food-recognition adapter.

Calorie and safety numbers always come from the Python services. A language
model may only explain records that were already loaded. Without an API key
the consultant uses those records directly and says so.
"""

from __future__ import annotations

import json

import httpx

from app.core.config import get_settings


def contains_urdu(text: str) -> bool:
    return any("\u0600" <= char <= "\u06FF" for char in text)


def _fallback(message: str, context: dict, language: str) -> str:
    urdu = language == "ur" or contains_urdu(message)
    diary = context.get("today") or {}
    plan = context.get("plan") or {}
    foods = context.get("food_matches") or []
    consumed = diary.get("energy_kcal")
    target = plan.get("calorie_target")
    remaining = None
    if consumed is not None and target is not None:
        remaining = round(target - consumed, 1)
    lower = message.lower()
    if urdu:
        if consumed is None:
            intake = "آج کے کھانے کا کوئی اندراج موجود نہیں۔"
        else:
            intake = f"آج درج شدہ کھانے {consumed} کیلوری ہیں۔"
            if remaining is not None:
                intake += f" ہدف سے تقریباً {remaining} کیلوری باقی ہیں۔"
        if "بریانی" in message or "biryani" in lower:
            return intake + " بریانی وزن کم کرنے کے دوران رک نہیں جاتی۔ پلیٹ کو ہدف کے اندر رکھیں، اور یہ اندازہ ہے، ضمانت نہیں۔"
        return intake + " میں تشخیص نہیں کرتا۔ اگر طبی مسئلہ ہو تو ماہر سے رجوع کریں۔ اعداد آپ کے محفوظ اندراج سے ہیں۔"
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


def consultant_reply(message: str, context: dict, language: str) -> dict:
    settings = get_settings()
    provider = "fallback"
    if settings.openai_api_key:
        system = (
            "You are FitDesi's nutrition coach. Use only the JSON context for the user's records. "
            "If a value is null, say it was not logged. Do not invent meals, weight, or steps. "
            "Do not diagnose or prescribe an extreme diet. Say that portions and cooked dishes are estimates. "
            f"Reply in {'Urdu' if language == 'ur' or contains_urdu(message) else 'English'}."
        )
        try:
            response = httpx.post(
                f"{settings.openai_base_url.rstrip('/')}/chat/completions",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
                json={
                    "model": settings.openai_chat_model,
                    "temperature": 0.2,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": json.dumps({"question": message, "context": context})},
                    ],
                },
                timeout=40,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            return {"content": content, "provider": settings.ai_provider, "estimate": True}
        except Exception:
            provider = "fallback_after_provider_error"
    return {"content": _fallback(message, context, language), "provider": provider, "estimate": True}


def recognise_foods(image_bytes: bytes, content_type: str) -> dict:
    settings = get_settings()
    if not settings.openai_api_key:
        return {
            "status": "provider_not_configured",
            "provider": "unconfigured",
            "predictions": [],
            "message": "No vision provider key is configured. Choose the food manually. A photo cannot reveal hidden oil or ingredients.",
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
            f"{settings.openai_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            json={
                "model": settings.openai_vision_model,
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
            "provider": settings.ai_provider,
            "predictions": parsed.get("items") or [],
            "message": "These matches are estimates. Confirm the food and portion before saving.",
        }
    except Exception as exc:  # noqa: BLE001
        return {
            "status": "provider_error",
            "provider": settings.ai_provider,
            "predictions": [],
            "message": f"The vision provider did not return a usable result ({exc.__class__.__name__}). Enter the food manually.",
        }
