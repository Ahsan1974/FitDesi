"""Idempotent FitDesi seed.

Demonstration users are created only when SEED_DEMO=true and are marked is_demo.
Consultant fees in demo mode are sample administrator configuration, not market prices,
and the profile stays unverified.
"""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import REPO_ROOT, get_settings
from app.core.security import hash_password, utcnow
from app.models import (
    Achievement,
    ApplicationSetting,
    ConsultantAvailability,
    ConsultantProfile,
    ConsultantService,
    Exercise,
    Food,
    FoodAlias,
    FoodCategory,
    FoodNutrition,
    FoodServing,
    FoodSource,
    FoodTranslation,
    Ingredient,
    Recipe,
    RecipeIngredient,
    RegionalCuisine,
    User,
    UserGoal,
    UserPreference,
    UserProfile,
)
from seeds.catalog import build_catalog, slugify

CATEGORIES = [
    ("breakfast", "Breakfast", "ناشتہ"),
    ("rice", "Rice dishes", "چاول"),
    ("chicken", "Chicken", "چکن"),
    ("beef_mutton", "Beef and mutton", "گوشت"),
    ("seafood", "Fish and seafood", "مچھلی"),
    ("lentils_vegetarian", "Lentils and vegetarian", "دال اور سبزی"),
    ("breads", "Breads", "روٹیاں"),
    ("street_food", "Street food", "اسٹریٹ فوڈ"),
    ("desserts", "Desserts", "میٹھے"),
    ("beverages", "Beverages", "مشروبات"),
    ("ingredients", "Ingredients", "اجزاء"),
    ("snacks", "Snacks", "اسنیکس"),
    ("condiments", "Condiments", "چٹنی اور اچار"),
]
CUISINES = [
    ("pakistani", "Pakistani", "پاکستانی"),
    ("sindhi", "Sindhi", "سندھی"),
    ("karachi", "Karachi", "کراچی"),
    ("punjabi", "Punjabi", "پنجابی"),
    ("balochi", "Balochi", "بلوچی"),
    ("pashtun", "Pashtun", "پشتون"),
    ("kpk", "Khyber Pakhtunkhwa", "خیبر پختونخوا"),
    ("kashmiri", "Kashmiri", "کشمیری"),
    ("gilgit_baltistan", "Gilgit-Baltistan", "گلگت بلتستان"),
    ("south_punjab", "South Punjab", "جنوبی پنجاب"),
    ("multani", "Multani", "ملتان"),
    ("general", "General reference", "عمومی"),
]
EXERCISES = [
    ("walk", "Brisk walk", "walking", "Walk at a pace where you can talk but not sing.", 3.5, "none", "beginner"),
    ("run", "Easy run", "running", "Keep the effort conversational. Stop if you feel chest pain.", 8.0, "none", "intermediate"),
    ("cycle", "Cycling", "cycling", "Use a steady cadence on flat ground.", 6.8, "bicycle", "beginner"),
    ("squat", "Sit to stand", "strength", "Stand up from a sturdy chair and sit back down with control.", 3.8, "chair", "beginner"),
    ("pushup", "Wall or floor push-up", "strength", "Keep the body in a line. Use a wall if the floor version is too hard.", 3.8, "none", "beginner"),
    ("row", "Band row", "strength", "Pull the elbows back without shrugging.", 3.5, "band", "beginner"),
    ("yoga", "Easy yoga flow", "yoga", "Move slowly and do not force a stretch.", 2.5, "mat", "beginner"),
    ("swim", "Easy swim", "swimming", "Swim at an easy pace if you can swim safely.", 6.0, "pool", "intermediate"),
]
ACHIEVEMENTS = [
    ("first_log", "First plate", "Log a food for the first time.", "first_food_log"),
    ("seven_day_logs", "Seven days", "Log food on seven different days.", "seven_log_days"),
    ("step_goal", "Step target", "Meet the step target on a saved day.", "step_goal_met"),
]


def _coverage_markdown(stats: dict) -> str:
    lines = [
        "# FitDesi food database coverage",
        "",
        "These counts come from the seed catalogue. Verified means an administrator reviewed the row.",
        "Imported USDA values are copied from FoodData Central SR Legacy and keep their FDC ids.",
        "Recipe rows are calculated from ingredient weights and a cooked yield. They are estimates.",
        "Compiled references are rounded published-style values used when a USDA row did not match a recipe ingredient.",
        "",
        f"- Total foods: {stats['total']}",
        f"- Verified foods: {stats['verified']}",
        f"- Awaiting verification: {stats['awaiting_verification']}",
        f"- USDA imports: {stats['imported_usda']}",
        f"- Compiled references: {stats['compiled_reference']}",
        f"- Recipe estimates: {stats['recipe_estimate']}",
        f"- Ingredient records: {stats['ingredients']}",
        "",
        "## Foods by cuisine label",
        "",
    ]
    for name, count in sorted(stats["by_cuisine"].items()):
        lines.append(f"- {name}: {count}")
    lines.extend([
        "",
        "## Coverage notes",
        "",
        "- Pakistan Food Composition Table files are not bundled. The CSV/JSON importer can load them when a usable file is available.",
        "- Branded restaurant plates and current supermarket prices are not invented.",
        "- Missing nutrients stay empty. They are not stored as zero.",
        "- A food can be verified in the admin screen after a person checks the source.",
        "",
    ])
    return "\n".join(lines)


def seed(db: Session) -> dict:
    settings = get_settings()
    categories = {row.slug: row for row in db.scalars(select(FoodCategory)).all()}
    for index, (slug, en, ur) in enumerate(CATEGORIES):
        if slug not in categories:
            row = FoodCategory(slug=slug, name_en=en, name_ur=ur, sort_order=index)
            db.add(row)
            db.flush()
            categories[slug] = row
    cuisines = {row.slug: row for row in db.scalars(select(RegionalCuisine)).all()}
    for slug, en, ur in CUISINES:
        if slug not in cuisines:
            row = RegionalCuisine(slug=slug, name_en=en, name_ur=ur)
            db.add(row)
            db.flush()
            cuisines[slug] = row
    for slug, name, category, instructions, met, equipment, level in EXERCISES:
        if db.scalar(select(Exercise).where(Exercise.slug == slug)) is None:
            db.add(Exercise(slug=slug, name=name, category=category, instructions=instructions, met=met, equipment=equipment, level=level,
                            beginner_modification="Shorten the set or the distance.", advanced_modification="Add a little time or resistance only if the basic version feels easy."))
    for code, name, description, rule in ACHIEVEMENTS:
        if db.scalar(select(Achievement).where(Achievement.code == code)) is None:
            db.add(Achievement(code=code, name=name, description=description, rule=rule))
    defaults = {
        "ai_daily_quota": 30,
        "payments_enabled": False,
        "default_timezone": "Asia/Karachi",
        "default_currency": "PKR",
        "support_email": "support@fitdesi.local",
    }
    for key, value in defaults.items():
        if db.get(ApplicationSetting, key) is None:
            db.add(ApplicationSetting(key=key, value_json=value))

    existing = {slug: food_id for slug, food_id in db.execute(select(Food.slug, Food.id)).all()}
    catalog = build_catalog()
    inserted = []
    for record in catalog["foods"]:
        if record["slug"] in existing:
            continue
        food = Food(
            slug=record["slug"],
            name_en=record["name_en"][:180],
            name_ur=(record.get("name_ur") or "")[:180],
            name_roman=(record.get("name_roman") or "")[:180],
            category_id=categories.get(record.get("category") or "ingredients", categories["ingredients"]).id,
            subcategory=record.get("subcategory"),
            cuisine_id=cuisines.get(record.get("cuisine") or "general", cuisines["general"]).id,
            kind=record["kind"],
            preparation=record["preparation"],
            is_vegetarian=record["is_vegetarian"],
            is_vegan=record["is_vegan"],
            default_serving_label=record["default_serving_label"],
            default_serving_g=record["default_serving_g"],
            data_origin=record["data_origin"],
            verification_status=record["verification_status"],
            data_confidence=record["data_confidence"],
            nutrition_note=record.get("nutrition_note"),
            search_text=record.get("search_text") or record["name_en"].lower(),
        )
        db.add(food)
        inserted.append((food, record))
    db.flush()
    for food, record in inserted:
        per = record.get("per_100g") or {}
        db.add(FoodNutrition(
            food_id=food.id,
            energy_kcal=per.get("energy_kcal"),
            protein_g=per.get("protein_g"),
            carbohydrate_g=per.get("carbohydrate_g"),
            fat_g=per.get("fat_g"),
            saturated_fat_g=per.get("saturated_fat_g"),
            fibre_g=per.get("fibre_g"),
            sugar_g=per.get("sugar_g"),
            sodium_mg=per.get("sodium_mg"),
        ))
        for serving in record.get("servings") or [{"label": "100 g", "grams": 100, "unit_kind": "weight"}]:
            db.add(FoodServing(food_id=food.id, label=serving["label"], grams=serving["grams"], unit_kind=serving.get("unit_kind") or "weight", source_note=serving.get("source_note")))
        source = record.get("source") or {}
        db.add(FoodSource(food_id=food.id, source_name=source.get("source_name") or record["data_origin"], source_id=source.get("source_id"), source_url=source.get("source_url"), licence=source.get("licence"), attribution=source.get("attribution"), quality=source.get("quality")))
        if record["kind"] == "ingredient":
            db.add(Ingredient(food_id=food.id, edible_portion_note="Values are per 100 g edible portion as published or compiled."))
        if record.get("name_ur"):
            db.add(FoodTranslation(food_id=food.id, locale="ur", name=record["name_ur"][:180]))
        db.add(FoodTranslation(food_id=food.id, locale="en", name=food.name_en))
        for alias in record.get("aliases") or []:
            db.add(FoodAlias(food_id=food.id, alias=alias[:180]))
        existing[food.slug] = food.id
    db.flush()
    for food, record in inserted:
        if record["data_origin"] != "recipe_estimate":
            continue
        recipe = Recipe(
            food_id=food.id, name_en=food.name_en, name_ur=food.name_ur, name_roman=food.name_roman,
            instructions=record.get("instructions"), method=record.get("method"),
            raw_weight_g=record.get("raw_weight_g") or 0, cooked_weight_g=record.get("cooked_weight_g") or 0,
            servings=1, is_public=True, data_origin="recipe_estimate",
            yield_notes=record.get("nutrition_note"),
        )
        db.add(recipe)
        db.flush()
        for item in record.get("ingredients") or []:
            ingredient_id = existing.get(slugify(item["query"]))
            db.add(RecipeIngredient(recipe_id=recipe.id, ingredient_food_id=ingredient_id, name_snapshot=item["query"], grams=item["grams"]))
    db.commit()

    if settings.admin_email and settings.admin_password:
        _user(db, settings.admin_email, settings.admin_password, "FitDesi Admin", "admin", False)
    if settings.seed_demo:
        demo = _user(db, settings.demo_email, settings.demo_password, "Demo User", "user", True)
        profile = db.get(UserProfile, demo.id)
        if profile is None:
            profile = UserProfile(user_id=demo.id)
            db.add(profile)
            db.flush()
        profile.onboarding_completed = True
        profile.gender = "female"
        profile.height_cm = 162
        profile.current_weight_kg = 78
        profile.start_weight_kg = 78
        profile.target_weight_kg = 68
        profile.activity_level = "lightly_active"
        profile.date_of_birth = __import__("datetime").date(1994, 5, 12)
        if db.scalar(select(func.count()).select_from(ConsultantProfile)) == 0:
            consultant = ConsultantProfile(
                display_name="Demo consultant (unverified)",
                qualifications="Sample profile for development only",
                bio="This is not a real dietitian and the account is not verified.",
                specialization="Development sample",
                experience_years=None,
                languages=["English", "Urdu"],
                verification_status="unverified",
                is_demo=True,
                fee_disclaimer="Sample administrator configuration for development. This is not a market price and the person is not verified.",
            )
            db.add(consultant)
            db.flush()
            db.add(ConsultantService(consultant_id=consultant.id, service_type="initial", title="Sample initial session", duration_min=45, price_amount=0, price_source="development_sample"))
            db.add(ConsultantAvailability(consultant_id=consultant.id, weekday=0, start_time="10:00", end_time="16:00"))
    db.commit()
    stats = catalog["stats"]
    stats["verified"] = db.scalar(select(func.count()).select_from(Food).where(Food.verification_status == "verified", Food.deleted_at.is_(None))) or 0
    text = _coverage_markdown(stats)
    for path in (REPO_ROOT / "FOOD_DATABASE_COVERAGE.md", REPO_ROOT / "docs" / "FOOD_DATABASE_COVERAGE.md"):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return {"inserted": len(inserted), "stats": stats}


def _user(db: Session, email: str, password: str, name: str, role: str, demo: bool) -> User:
    email = email.lower()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        user = User(email=email, password_hash=hash_password(password), full_name=name, role=role, is_demo=demo, email_verified=True, is_active=True)
        db.add(user)
        db.flush()
    if db.get(UserProfile, user.id) is None:
        db.add(UserProfile(user_id=user.id))
    if db.get(UserPreference, user.id) is None:
        db.add(UserPreference(user_id=user.id))
    if db.get(UserGoal, user.id) is None:
        db.add(UserGoal(user_id=user.id))
    db.flush()
    return user


def main() -> None:
    from app.core.database import SessionLocal, engine
    from app.models.entities import Base

    Base.metadata.create_all(engine)
    with SessionLocal() as db:
        result = seed(db)
    print(result["stats"])


if __name__ == "__main__":
    main()
