"""Deterministic nutrition, portion, recipe, and metabolic calculations.

Missing nutrients stay None. They are never coerced to zero.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

NUTRIENT_FIELDS = (
    "energy_kcal",
    "protein_g",
    "carbohydrate_g",
    "fat_g",
    "saturated_fat_g",
    "fibre_g",
    "sugar_g",
    "sodium_mg",
)

ACTIVITY_FACTORS = {
    "sedentary": 1.2,
    "lightly_active": 1.375,
    "moderately_active": 1.55,
    "very_active": 1.725,
    "extra_active": 1.9,
}

FORMULA_NAME = "mifflin_st_jeor"
FORMULA_VERSION = "v1"
KCAL_PER_KG = 7700


def _round(value: float | None, places: int = 2) -> float | None:
    if value is None:
        return None
    return round(float(value), places)


def scale_nutrient(per_100g: float | None, grams: float) -> float | None:
    """Nutrient consumed = nutrient per 100 g × grams / 100."""
    if per_100g is None:
        return None
    if grams < 0:
        raise ValueError("Portion grams cannot be negative.")
    return _round(float(per_100g) * float(grams) / 100.0)


def scale_profile(per_100g: dict, grams: float) -> dict:
    return {field: scale_nutrient(per_100g.get(field), grams) for field in NUTRIENT_FIELDS}


def _sum_field(parts: list[dict], field: str, weights: list[float], trace_g: float = 2.0) -> float | None:
    total = 0.0
    for part, weight in zip(parts, weights, strict=True):
        value = part.get(field)
        if value is None:
            if weight > trace_g:
                return None
            continue
        total += float(value)
    return total


def combine_ingredients(
    items: list[tuple[dict, float]],
    added_water_g: float = 0,
    water_loss_g: float = 0,
) -> dict:
    """Combine ingredient nutrients and convert them to a cooked per-100 g profile.

    Added water contributes weight but no nutrients. Water loss reduces cooked
    weight and concentrates nutrients. Raw and cooked weights are kept separate.
    """
    if not items:
        raise ValueError("A recipe needs at least one ingredient.")
    weights = [float(grams) for _, grams in items]
    if any(weight <= 0 for weight in weights):
        raise ValueError("Ingredient quantity must be greater than zero.")
    raw_weight = sum(weights)
    cooked_weight = raw_weight + float(added_water_g) - float(water_loss_g)
    if cooked_weight <= 0:
        raise ValueError("Cooked weight must be greater than zero.")
    profiles = [scale_profile(profile, grams) for profile, grams in items]
    totals = {field: _round(_sum_field(profiles, field, weights)) for field in NUTRIENT_FIELDS}
    per_100g = {
        field: _round(None if value is None else value / cooked_weight * 100.0)
        for field, value in totals.items()
    }
    return {
        "raw_weight_g": _round(raw_weight),
        "added_water_g": _round(float(added_water_g)),
        "water_loss_g": _round(float(water_loss_g)),
        "cooked_weight_g": _round(cooked_weight),
        "totals": totals,
        "per_100g": per_100g,
        "yield_ratio": _round(cooked_weight / raw_weight, 4),
    }


def per_serving(totals: dict, servings: float) -> dict:
    if servings <= 0:
        raise ValueError("Servings must be greater than zero.")
    return {field: _round(None if totals.get(field) is None else totals[field] / servings) for field in NUTRIENT_FIELDS}


def bmr_mifflin_st_jeor(sex: str | None, weight_kg: float, height_cm: float, age_years: int) -> dict:
    if weight_kg <= 0 or height_cm <= 0 or age_years <= 0:
        raise ValueError("Weight, height, and age must be positive.")
    base = (10 * weight_kg) + (6.25 * height_cm) - (5 * age_years)
    normalized = (sex or "").lower()
    if normalized == "male":
        value = base + 5
        assumption = "Mifflin-St Jeor male constant (+5)."
    elif normalized == "female":
        value = base - 161
        assumption = "Mifflin-St Jeor female constant (−161)."
    else:
        value = base - 78
        assumption = "Sex was not specified, so the male and female constants were averaged (−78)."
    return {
        "bmr": round(value, 1),
        "formula_name": FORMULA_NAME,
        "formula_version": FORMULA_VERSION,
        "assumption": assumption,
    }


def tdee(bmr: float, activity_level: str) -> dict:
    if activity_level not in ACTIVITY_FACTORS:
        raise ValueError(f"Unknown activity level: {activity_level}")
    factor = ACTIVITY_FACTORS[activity_level]
    return {"tdee": round(bmr * factor, 1), "activity_factor": factor, "activity_level": activity_level}


def bmi(weight_kg: float, height_cm: float) -> float:
    metres = height_cm / 100
    return round(weight_kg / (metres * metres), 1)


def age_on(dob: date, today: date | None = None) -> int:
    today = today or date.today()
    years = today.year - dob.year
    if (today.month, today.day) < (dob.month, dob.day):
        years -= 1
    return years


def calorie_floor(sex: str | None) -> int:
    normalized = (sex or "").lower()
    if normalized == "male":
        return 1500
    if normalized == "female":
        return 1200
    return 1400


def assess_feasibility(payload: dict, today: date | None = None) -> dict:
    """Screen a weight goal. This is not a medical prescription or a guarantee."""
    today = today or date.today()
    assumptions = [
        "Weight change is estimated from an energy difference of about 7,700 kcal per kilogram. Individual results vary.",
        "The activity factor already estimates usual daily movement. Active exercise calories are not added back to the food budget.",
        "Targets are screening estimates for generally healthy adults and are not a promise that a date will be met.",
    ]
    blockers = []
    age = payload.get("age")
    if payload.get("date_of_birth"):
        dob = payload["date_of_birth"]
        if isinstance(dob, str):
            dob = date.fromisoformat(dob)
        age = age_on(dob, today)
    if age is None:
        blockers.append("Age or date of birth is required before a plan can be assessed.")
    elif age < 18:
        blockers.append("Automatic weight-loss diets are not created for anyone under 18.")
    if payload.get("pregnant"):
        blockers.append("Pregnancy needs individual clinical guidance. No weight-loss diet was created.")
    if payload.get("breastfeeding"):
        blockers.append("Breastfeeding needs individual clinical guidance. No weight-loss diet was created.")
    if payload.get("eating_disorder_history"):
        blockers.append("A history of disordered eating needs professional support. No calorie deficit was created.")
    if (payload.get("medical_conditions") or "").strip():
        blockers.append("A reported medical condition needs professional review before a diet is generated.")

    weight = float(payload["current_weight_kg"])
    target = float(payload["target_weight_kg"])
    height = float(payload["height_cm"])
    current_bmi = bmi(weight, height)
    goal_date = payload.get("goal_date")
    if isinstance(goal_date, str):
        goal_date = date.fromisoformat(goal_date)
    sex = payload.get("gender")
    activity = payload.get("activity_level") or "sedentary"
    bmr_result = bmr_mifflin_st_jeor(sex, weight, height, int(age or 30))
    tdee_result = tdee(bmr_result["bmr"], activity)
    maintenance = tdee_result["tdee"]
    floor = calorie_floor(sex)

    result = {
        "formula_name": FORMULA_NAME,
        "formula_version": FORMULA_VERSION,
        "calculated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "inputs": {
            "current_weight_kg": weight,
            "target_weight_kg": target,
            "height_cm": height,
            "age": age,
            "gender": sex,
            "activity_level": activity,
            "goal_date": goal_date.isoformat() if goal_date else None,
        },
        "current_bmi": current_bmi,
        "bmr": bmr_result["bmr"],
        "tdee": maintenance,
        "activity_factor": tdee_result["activity_factor"],
        "assumptions": assumptions + [bmr_result["assumption"]],
        "calorie_floor": floor,
        "safety_status": "ok",
        "messages": [],
    }

    if blockers:
        result["safety_status"] = "blocked"
        result["blocked_reason"] = " ".join(blockers)
        result["messages"] = blockers
        result["calorie_target"] = None
        return result

    min_target = round(18.5 * (height / 100) ** 2, 1)
    if target < min_target:
        result["messages"].append(
            f"The requested target is below BMI 18.5. The plan uses {min_target} kg as the lowest target weight."
        )
        target = min_target
        result["adjusted_target_weight_kg"] = target
    result["target_bmi"] = bmi(target, height)
    change = round(weight - target, 2)
    result["weight_change_kg"] = change
    direction = "loss" if change > 0 else "gain" if change < 0 else "maintain"
    result["direction"] = direction

    if direction == "maintain" or abs(change) < 0.2:
        result["calorie_target"] = round(maintenance)
        result["weekly_change_kg"] = 0
        result["goal_date"] = today.isoformat()
        _apply_macros(result, weight)
        result["messages"].append("Current and target weight are effectively the same, so the target is maintenance.")
        return result

    if goal_date is None:
        weekly = 0.5 if direction == "loss" else 0.25
        weeks_needed = abs(change) / weekly
        goal_date = today + timedelta(days=round(weeks_needed * 7))
        result["messages"].append("No date was supplied, so a steady pace was used to suggest one.")
    days = (goal_date - today).days
    if days < 7:
        result["safety_status"] = "adjusted"
        result["messages"].append("Less than a week is too short for a meaningful change. The timeline was extended.")
        days = max(7, round(abs(change) / 0.5 * 7))
        goal_date = today + timedelta(days=days)
    weeks = days / 7
    required_weekly = change / weeks
    max_weekly = min(1.0, round(weight * 0.01, 2))
    if direction == "gain":
        max_weekly = 0.5
    if abs(required_weekly) > max_weekly:
        result["safety_status"] = "adjusted"
        safe_weeks = abs(change) / max_weekly
        goal_date = today + timedelta(days=round(safe_weeks * 7))
        weeks = safe_weeks
        required_weekly = change / weeks
        result["messages"].append(
            "The requested date needs a faster change than the safety limit. "
            f"A calmer date is {goal_date.isoformat()}, at about {abs(round(required_weekly, 2))} kg per week."
        )
        result["alternative_goal_date"] = goal_date.isoformat()

    daily_delta = required_weekly * KCAL_PER_KG / 7
    proposed = maintenance - daily_delta
    if direction == "loss" and proposed < floor:
        result["safety_status"] = "adjusted"
        proposed = floor
        achievable_delta = maintenance - proposed
        achievable_weekly = achievable_delta * 7 / KCAL_PER_KG
        if achievable_weekly <= 0.05:
            result["safety_status"] = "blocked"
            result["blocked_reason"] = (
                "Even the lowest screening calorie target is close to estimated maintenance, "
                "so a deficit plan was not created. Professional advice is appropriate."
            )
            result["messages"].append(result["blocked_reason"])
            result["calorie_target"] = None
            return result
        safe_days = round(change / achievable_weekly * 7)
        goal_date = today + timedelta(days=max(safe_days, 7))
        required_weekly = achievable_weekly
        result["messages"].append(
            f"The date would have pushed intake below {floor} kcal. "
            f"The plan stays at {floor} kcal and the realistic date moves to {goal_date.isoformat()}."
        )
        result["alternative_goal_date"] = goal_date.isoformat()
    if direction == "gain":
        surplus = min(500, max(200, abs(daily_delta)))
        proposed = maintenance + surplus
        result["messages"].append("Weight gain is capped at a modest surplus of at most 500 kcal.")

    result["calorie_target"] = int(round(proposed))
    result["weekly_change_kg"] = round(required_weekly, 2)
    result["goal_date"] = goal_date.isoformat()
    result["estimated_daily_deficit"] = round(maintenance - result["calorie_target"])
    _apply_macros(result, weight)
    if result["safety_status"] == "ok" and not result["messages"]:
        result["messages"].append("The requested pace fits the screening limits. It is still an estimate, not a guarantee.")
    return result


def _apply_macros(result: dict, weight_kg: float) -> None:
    calories = result["calorie_target"]
    protein = round(max(1.4 * weight_kg, 60), 1)
    protein_kcal = protein * 4
    if protein_kcal > calories * 0.4:
        protein = round(calories * 0.35 / 4, 1)
        protein_kcal = protein * 4
    fat_kcal = calories * 0.3
    fat = round(fat_kcal / 9, 1)
    carb = round(max(calories - protein_kcal - fat_kcal, 0) / 4, 1)
    result["protein_g"] = protein
    result["fat_g"] = fat
    result["carbohydrate_g"] = carb
    result["fibre_g"] = 30
    result["hydration_ml"] = int(round(min(max(30 * weight_kg, 1800), 4000)))
    result["macro_basis"] = (
        "Protein is set around 1.4 g per kilogram of current weight, fat around 30 percent of calories, "
        "and carbohydrate fills the remainder. Fibre and water figures are general guidance, not a medical dose."
    )


def estimate_activity_kcal(met: float, weight_kg: float, minutes: float) -> float:
    """Estimated kcal = MET × body weight (kg) × hours. Label this as an estimate."""
    if minutes < 0 or weight_kg <= 0 or met <= 0:
        raise ValueError("MET, weight, and duration must be positive.")
    return round(met * weight_kg * (minutes / 60), 1)


def walking_distance_m(steps: int, stride_m: float = 0.75) -> float:
    return round(max(steps, 0) * stride_m, 1)


def walking_minutes(steps: int, cadence_steps_per_min: float = 100) -> float:
    if steps <= 0:
        return 0
    return round(steps / cadence_steps_per_min, 1)


SOURCE_PRIORITY = {
    "health_connect": 3,
    "healthkit": 3,
    "sensor": 2,
    "manual": 1,
}


def choose_step_source(records: list[dict]) -> dict | None:
    """Pick one source for a day so providers are not added together."""
    if not records:
        return None
    return max(records, key=lambda item: (SOURCE_PRIORITY.get(item.get("source"), 0), item.get("steps") or 0))


def summarize_nutrients(entries: list[dict]) -> dict:
    if not entries:
        return {"logged": False, "entries": 0, **{field: None for field in NUTRIENT_FIELDS}, "incomplete": {}}
    totals = {}
    incomplete = {}
    for field in NUTRIENT_FIELDS:
        known = [entry[field] for entry in entries if entry.get(field) is not None]
        missing = len(entries) - len(known)
        totals[field] = round(sum(known), 2) if known else None
        incomplete[field] = missing > 0
    return {"logged": True, "entries": len(entries), "incomplete": incomplete, **totals}


def weight_trend(entries: list[tuple[date, float]]) -> dict:
    """Use averages rather than one day's fluctuation."""
    if not entries:
        return {"latest": None, "change": None, "weekly_average": None, "monthly_average": None, "points": 0}
    ordered = sorted(entries, key=lambda item: item[0])
    latest_day, latest = ordered[-1]
    start = ordered[0][1]
    week_cut = latest_day - timedelta(days=6)
    month_cut = latest_day - timedelta(days=29)
    week_vals = [value for day, value in ordered if day >= week_cut]
    month_vals = [value for day, value in ordered if day >= month_cut]
    return {
        "latest": latest,
        "starting": start,
        "change": round(latest - start, 2),
        "weekly_average": round(sum(week_vals) / len(week_vals), 2),
        "monthly_average": round(sum(month_vals) / len(month_vals), 2),
        "points": len(ordered),
        "note": "A single heavier or lighter day is only a fluctuation until the weekly average moves.",
    }
