from datetime import date, timedelta

from app.services.calc import (
    assess_feasibility,
    bmr_mifflin_st_jeor,
    choose_step_source,
    combine_ingredients,
    scale_nutrient,
    summarize_nutrients,
    tdee,
)


def test_portion_formula():
    assert scale_nutrient(250, 200) == 500
    assert scale_nutrient(None, 200) is None


def test_missing_nutrient_is_not_zero():
    cooked = combine_ingredients([
        ({"energy_kcal": 120, "protein_g": 22, "carbohydrate_g": 0, "fat_g": 3, "saturated_fat_g": None, "fibre_g": 0, "sugar_g": 0, "sodium_mg": 40}, 200),
        ({"energy_kcal": 884, "protein_g": 0, "carbohydrate_g": 0, "fat_g": 100, "saturated_fat_g": 14, "fibre_g": 0, "sugar_g": 0, "sodium_mg": 0}, 20),
    ], added_water_g=0, water_loss_g=40)
    assert cooked["cooked_weight_g"] != cooked["raw_weight_g"]
    assert cooked["per_100g"]["saturated_fat_g"] is None


def test_bmr_and_tdee_are_deterministic():
    bmr = bmr_mifflin_st_jeor("female", 78, 162, 32)
    assert bmr["bmr"] == round(10 * 78 + 6.25 * 162 - 5 * 32 - 161, 1)
    assert tdee(bmr["bmr"], "sedentary")["tdee"] == round(bmr["bmr"] * 1.2, 1)


def test_under_18_is_blocked():
    result = assess_feasibility({
        "current_weight_kg": 60, "target_weight_kg": 50, "height_cm": 160,
        "age": 16, "gender": "female", "activity_level": "sedentary",
    })
    assert result["safety_status"] == "blocked"
    assert result["calorie_target"] is None


def test_aggressive_date_is_slowed_down():
    result = assess_feasibility({
        "current_weight_kg": 90, "target_weight_kg": 75, "height_cm": 170,
        "age": 35, "gender": "male", "activity_level": "sedentary",
        "goal_date": date.today() + timedelta(days=14),
    }, today=date.today())
    assert result["safety_status"] == "adjusted"
    assert result["calorie_target"] >= 1500


def test_steps_are_not_added_across_sources():
    chosen = choose_step_source([
        {"source": "manual", "steps": 10000},
        {"source": "health_connect", "steps": 4200},
    ])
    assert chosen["source"] == "health_connect"
    assert chosen["steps"] == 4200


def test_empty_day_is_not_zero_intake():
    summary = summarize_nutrients([])
    assert summary["logged"] is False
    assert summary["energy_kcal"] is None
