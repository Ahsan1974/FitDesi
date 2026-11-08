"""Meal and workout plan generation from real food and exercise records."""

from __future__ import annotations

MEAL_SPLITS = {
    2: [("lunch", 0.55), ("dinner", 0.45)],
    3: [("breakfast", 0.28), ("lunch", 0.40), ("dinner", 0.32)],
    4: [("breakfast", 0.25), ("morning_snack", 0.10), ("lunch", 0.37), ("dinner", 0.28)],
    5: [("breakfast", 0.24), ("morning_snack", 0.08), ("lunch", 0.34), ("afternoon_snack", 0.08), ("dinner", 0.26)],
    6: [
        ("breakfast", 0.22),
        ("morning_snack", 0.08),
        ("lunch", 0.30),
        ("afternoon_snack", 0.08),
        ("dinner", 0.24),
        ("evening_snack", 0.08),
    ],
}

BREAKFAST_HINTS = ("egg", "paratha", "roti", "dahi", "yogurt", "poha", "halwa", "chai", "omelette", "toast")
SNACK_HINTS = ("fruit", "dahi", "yogurt", "lassi", "nuts", "chaat", "samosa", "apple", "banana", "guava")
STAPLE_HINTS = ("roti", "chapati", "naan", "rice", "biryani", "pulao", "khichdi")
CURRY_HINTS = ("karahi", "salan", "korma", "daal", "dal", "sabzi", "nihari", "haleem", "kebab", "curry")


def _allowed(food: dict, diet: str, allergies: list[str], disliked: list[str]) -> bool:
    name = f"{food.get('name_en', '')} {food.get('name_roman', '')}".lower()
    if diet == "vegetarian" and not food.get("is_vegetarian"):
        return False
    if diet == "vegan" and not food.get("is_vegan"):
        return False
    for token in [*(allergies or []), *(disliked or [])]:
        if token and token.lower() in name:
            return False
    kcal = (food.get("per_100g") or {}).get("energy_kcal")
    return kcal is not None and kcal > 20


def _prefer(pool: list[dict], hints: tuple[str, ...]) -> list[dict]:
    matched = [food for food in pool if any(hint in food["name_en"].lower() for hint in hints)]
    return matched or pool


def _grams_for_kcal(per_100: float, target: float, low: float, high: float) -> float:
    grams = target / per_100 * 100
    return round(min(max(grams, low), high), 1)


def _item(food: dict, grams: float) -> dict:
    per = food["per_100g"]
    factor = grams / 100
    def scaled(field):
        value = per.get(field)
        return None if value is None else round(value * factor, 2)
    return {
        "food_id": food["id"],
        "name": food["name_en"],
        "grams": grams,
        "energy_kcal": scaled("energy_kcal"),
        "protein_g": scaled("protein_g"),
        "carbohydrate_g": scaled("carbohydrate_g"),
        "fat_g": scaled("fat_g"),
        "fibre_g": scaled("fibre_g"),
    }


def _pick(pool: list[dict], index: int, used: set[int]) -> dict:
    if not pool:
        raise ValueError("No foods are available for this meal.")
    for offset in range(len(pool)):
        food = pool[(index + offset) % len(pool)]
        if food["id"] not in used:
            return food
    return pool[index % len(pool)]


def build_meal_plan_days(
    foods: list[dict],
    calorie_target: float,
    days: int,
    meals_per_day: int,
    diet: str = "non_vegetarian",
    allergies: list[str] | None = None,
    disliked: list[str] | None = None,
) -> list[dict]:
    pool = [food for food in foods if _allowed(food, diet, allergies or [], disliked or [])]
    if len(pool) < 4:
        raise ValueError("Not enough suitable foods to build a meal plan.")
    pool = sorted(pool, key=lambda food: food["id"])
    splits = MEAL_SPLITS.get(meals_per_day) or MEAL_SPLITS[3]
    plan_days = []
    for day_index in range(days):
        meals = []
        used: set[int] = set()
        for slot_index, (meal_type, share) in enumerate(splits):
            target = calorie_target * share
            if "snack" in meal_type:
                choices = _prefer(pool, SNACK_HINTS)
                food = _pick(choices, day_index * 5 + slot_index, used)
                grams = _grams_for_kcal(food["per_100g"]["energy_kcal"], target, 40, 250)
                items = [_item(food, grams)]
            elif meal_type == "breakfast":
                choices = _prefer(pool, BREAKFAST_HINTS)
                food = _pick(choices, day_index + slot_index, used)
                grams = _grams_for_kcal(food["per_100g"]["energy_kcal"], target, 50, 350)
                items = [_item(food, grams)]
            else:
                staples = _prefer(pool, STAPLE_HINTS)
                curries = _prefer(pool, CURRY_HINTS)
                staple = _pick(staples, day_index + slot_index, used)
                curry = _pick(curries, day_index * 3 + slot_index + 7, used | {staple["id"]})
                staple_grams = _grams_for_kcal(staple["per_100g"]["energy_kcal"], target * 0.45, 40, 300)
                curry_grams = _grams_for_kcal(curry["per_100g"]["energy_kcal"], target * 0.55, 80, 400)
                items = [_item(staple, staple_grams), _item(curry, curry_grams)]
            for item in items:
                used.add(item["food_id"])
            meals.append({
                "meal_type": meal_type,
                "name": meal_type.replace("_", " ").title(),
                "items": items,
                "energy_kcal": round(sum(item["energy_kcal"] or 0 for item in items), 1),
                "protein_g": round(sum(item["protein_g"] or 0 for item in items), 1),
                "carbohydrate_g": round(sum(item["carbohydrate_g"] or 0 for item in items), 1),
                "fat_g": round(sum(item["fat_g"] or 0 for item in items), 1),
                "fibre_g": round(sum(item["fibre_g"] or 0 for item in items), 1),
            })
        plan_days.append({
            "day_index": day_index,
            "meals": meals,
            "energy_kcal": round(sum(meal["energy_kcal"] for meal in meals), 1),
        })
    return plan_days


def suggest_replacement(foods: list[dict], current_food_id: int, target_kcal: float, diet: str, allergies, disliked) -> dict | None:
    pool = [food for food in foods if food["id"] != current_food_id and _allowed(food, diet, allergies or [], disliked or [])]
    if not pool:
        return None
    ranked = sorted(
        pool,
        key=lambda food: abs((food["per_100g"]["energy_kcal"] or 0) - (target_kcal or 0)),
    )
    food = ranked[0]
    grams = _grams_for_kcal(food["per_100g"]["energy_kcal"], target_kcal or food["per_100g"]["energy_kcal"], 40, 400)
    return _item(food, grams)


def build_workout_week(level: str, gym: bool, home: bool, minutes: int, walking: str) -> list[dict]:
    minutes = max(10, min(minutes or 30, 90))
    easy = walking == "limited" or level == "beginner"
    walk = {
        "name": "Brisk walk",
        "duration_min": minutes,
        "sets": None,
        "reps": None,
        "rest_sec": None,
        "instructions": "Walk at a pace where talking is possible but singing is not. Use comfortable shoes.",
        "modification": "Split the walk into two shorter outings if needed." if easy else "Add a few short faster minutes.",
    }
    if gym:
        strength = [
            {"name": "Goblet squat or leg press", "sets": 3, "reps": 8, "rest_sec": 90, "duration_min": 12,
             "instructions": "Lower under control and stand tall. Stop if a joint is painful.",
             "modified": "Use a chair squat if balance is new."},
            {"name": "Seated row or band row", "sets": 3, "reps": 10, "rest_sec": 75, "duration_min": 10,
             "instructions": "Pull the elbows back without shrugging.",
             "modified": "Use a lighter band."},
            {"name": "Push-up or chest press", "sets": 3, "reps": 8, "rest_sec": 75, "duration_min": 10,
             "instructions": "Keep the body in a line and move through a comfortable range.",
             "modified": "Push from a wall or a raised surface."},
        ]
    elif home:
        strength = [
            {"name": "Sit-to-stand", "sets": 3, "reps": 10, "rest_sec": 60, "duration_min": 8,
             "instructions": "Stand up from a sturdy chair without using momentum.",
             "modified": "Use hands on the chair if needed."},
            {"name": "Wall push-up", "sets": 3, "reps": 8, "rest_sec": 60, "duration_min": 8,
             "instructions": "Hands on a wall, lower the chest, then press away.",
             "modified": "Step closer to the wall to make it easier."},
            {"name": "Glute bridge", "sets": 3, "reps": 10, "rest_sec": 45, "duration_min": 8,
             "instructions": "Lie down, feet flat, lift hips, and lower slowly.",
             "modified": "Shorten the pause at the top."},
        ]
    else:
        strength = [walk]
    titles = ["Walk", "Strength", "Walk", "Rest", "Strength", "Walk", "Rest"]
    days = []
    for index, title in enumerate(titles):
        if title == "Rest":
            days.append({"day_index": index, "title": "Rest", "is_rest": True, "details": [
                {"name": "Rest or gentle stretch", "duration_min": 10, "instructions": "Easy movement only. Recovery is part of the plan."}
            ]})
        elif title == "Strength":
            days.append({"day_index": index, "title": "Strength and a short walk", "is_rest": False, "details": [*strength, walk]})
        else:
            days.append({"day_index": index, "title": "Walking", "is_rest": False, "details": [walk]})
    return days
