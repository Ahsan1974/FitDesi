from datetime import date, datetime, timedelta

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import case, func, or_, select
from sqlalchemy.orm import Session

from app.api.v1.common import audit, day_window, find_mutation, food_out, load_food_bundle, num, nutrition_out, ok, parse_day, rate_limit
from app.core.config import get_settings
from app.core.database import get_db
from app.core.deps import get_admin, get_current_user
from app.core.errors import AppError
from app.core.security import create_access_token, hash_password, hash_token, new_token, utcnow, verify_password
from app.models import (
    Achievement,
    AiChatMessage,
    AiChatSession,
    AiFoodScan,
    ApplicationSetting,
    AuthToken,
    BodyMeasurement,
    ConsultantAvailability,
    ConsultantBooking,
    ConsultantProfile,
    ConsultantService,
    DailyFoodLog,
    DailySteps,
    Exercise,
    Food,
    FoodAlias,
    FoodCategory,
    FoodFavourite,
    FoodNutrition,
    FoodServing,
    FoodSource,
    GroceryList,
    GroceryListItem,
    MealPlan,
    MealPlanDay,
    MealPlanItem,
    MealPlanMeal,
    MealPlanVersion,
    Notification,
    PaymentRecord,
    PlanAdjustment,
    Recipe,
    RecipeIngredient,
    RefreshToken,
    RegionalCuisine,
    SleepLog,
    User,
    UserAchievement,
    UserAllergy,
    UserGoal,
    UserPreference,
    UserProfile,
    UserSavedRecipe,
    UserSession,
    WaterLog,
    WeightEntry,
    WellnessPlan,
    Workout,
    WorkoutExercise,
    WorkoutPlan,
    WorkoutPlanDay,
)
from app.services.ai_service import choose_meal, consultant_reply, daily_tip, explain_plan, recognise_foods
from app.services.calc import (
    SOURCE_PRIORITY,
    assess_feasibility,
    choose_step_source,
    estimate_activity_kcal,
    scale_profile,
    summarize_nutrients,
    walking_distance_m,
    walking_minutes,
    weight_trend,
)
from app.services.planning import build_meal_plan_days, build_workout_week, suggest_replacement

router = APIRouter()


class RegisterIn(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenIn(BaseModel):
    refresh_token: str


class EmailIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str
    password: str = Field(min_length=8, max_length=128)


class VerifyIn(BaseModel):
    token: str


class ProfileIn(BaseModel):
    full_name: str | None = None
    timezone: str | None = None
    currency: str | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    height_cm: float | None = None
    current_weight_kg: float | None = None
    target_weight_kg: float | None = None
    waist_cm: float | None = None
    activity_level: str | None = None
    fitness_experience: str | None = None
    walking_ability: str | None = None
    exercise_preference: str | None = None
    gym_available: bool | None = None
    home_workout: bool | None = None
    pregnant: bool | None = None
    breastfeeding: bool | None = None
    medical_conditions: str | None = None
    eating_disorder_history: bool | None = None
    exercise_minutes_available: int | None = None
    daily_food_budget_pkr: float | None = None
    work_schedule: str | None = None


class PreferencesIn(BaseModel):
    diet_type: str | None = None
    meals_per_day: int | None = Field(default=None, ge=2, le=6)
    meal_times: dict | None = None
    cuisines: list[str] | None = None
    disliked_foods: list[str] | None = None
    regional_cuisines: list[str] | None = None
    language: str | None = None
    theme: str | None = None
    step_target: int | None = None
    water_goal_ml: int | None = None
    quiet_hours_start: str | None = None
    quiet_hours_end: str | None = None
    notification_flags: dict | None = None
    allergies: list[str] | None = None
    intolerances: list[str] | None = None


class OnboardingIn(ProfileIn, PreferencesIn):
    goal_date: date | None = None
    pace: str | None = None
    consent_health: bool = False
    consent_ai: bool = False


class CopyDayIn(BaseModel):
    from_date: date
    to_date: date | None = None


class DiaryIn(BaseModel):
    food_id: int | None = None
    meal_type: str = "other"
    grams: float = Field(gt=0)
    serving_label: str | None = None
    logged_at: datetime | None = None
    client_mutation_id: str | None = None
    custom_name: str | None = None
    scan_id: int | None = None


class PortionIn(BaseModel):
    grams: float = Field(gt=0)


class RecipeCalcIn(BaseModel):
    ingredients: list[dict]
    added_water_g: float = 0
    water_loss_g: float = 0
    servings: float = Field(default=1, gt=0)


class RecipeIn(BaseModel):
    name_en: str
    name_ur: str = ""
    name_roman: str = ""
    instructions: str | None = None
    method: str | None = None
    ingredients: list[dict]
    added_water_g: float = 0
    water_loss_g: float = 0
    servings: float = 1


class PlanIn(BaseModel):
    current_weight_kg: float
    target_weight_kg: float
    height_cm: float
    age: int | None = None
    date_of_birth: date | None = None
    gender: str | None = None
    activity_level: str = "sedentary"
    goal_date: date | None = None
    days: int = Field(default=7, ge=7, le=30)
    meals_per_day: int = Field(default=3, ge=2, le=6)
    diet_type: str = "non_vegetarian"
    allergies: list[str] = []
    disliked_foods: list[str] = []
    pregnant: bool = False
    breastfeeding: bool = False
    eating_disorder_history: bool = False
    medical_conditions: str | None = None
    gym_available: bool = False
    home_workout: bool = True
    walking_ability: str = "comfortable"
    fitness_experience: str = "beginner"
    exercise_minutes_available: int = 30


class StepsIn(BaseModel):
    day: date
    steps: int = Field(ge=0)
    distance_m: float | None = None
    duration_min: float | None = None
    active_kcal: float | None = None
    source: str = "manual"
    timezone: str = "Asia/Karachi"


class WorkoutIn(BaseModel):
    name: str
    category: str = "custom"
    status: str = "completed"
    started_at: datetime
    ended_at: datetime | None = None
    duration_min: float | None = None
    distance_m: float | None = None
    notes: str | None = None
    client_mutation_id: str | None = None
    exercises: list[dict] = []


class WeightIn(BaseModel):
    weight_kg: float = Field(gt=0, lt=500)
    logged_at: datetime | None = None
    note: str | None = None
    client_mutation_id: str | None = None


class MeasureIn(BaseModel):
    waist_cm: float | None = None
    chest_cm: float | None = None
    hip_cm: float | None = None
    arm_cm: float | None = None
    body_fat_percent: float | None = None
    note: str | None = None


class WaterIn(BaseModel):
    amount_ml: int = Field(gt=0, le=3000)
    logged_at: datetime | None = None
    client_mutation_id: str | None = None


class SleepIn(BaseModel):
    sleep_start: datetime
    sleep_end: datetime
    source: str = "manual"
    client_mutation_id: str | None = None


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=2000)
    language: str = "en"
    session_id: int | None = None


class BookingIn(BaseModel):
    consultant_id: int
    service_id: int
    start_at: datetime
    notes: str | None = None


class CancelIn(BaseModel):
    reason: str | None = None


class GroceryIn(BaseModel):
    name: str = "Shopping list"
    meal_plan_id: int | None = None
    budget_pkr: float | None = None
    items: list[dict] = []


class FoodAdminIn(BaseModel):
    name_en: str
    name_ur: str = ""
    name_roman: str = ""
    category_id: int | None = None
    cuisine_id: int | None = None
    kind: str = "dish"
    is_vegetarian: bool = False
    is_vegan: bool = False
    per_100g: dict
    servings: list[dict] = []
    aliases: list[str] = []
    nutrition_note: str | None = None
    data_origin: str = "manual"
    data_confidence: str = "low"


def _tokens(user: User, db: Session, request: Request) -> dict:
    session = UserSession(user_id=user.id, user_agent=request.headers.get("user-agent"), ip_address=request.client.host if request.client else None)
    db.add(session)
    db.flush()
    raw = new_token()
    settings = get_settings()
    db.add(RefreshToken(user_id=user.id, session_id=session.id, token_hash=hash_token(raw), expires_at=utcnow() + timedelta(days=settings.refresh_token_days)))
    return {
        "access_token": create_access_token(user.id, user.role),
        "refresh_token": raw,
        "token_type": "bearer",
        "email_verified": user.email_verified,
    }


def _issue_auth_token(db: Session, user: User, purpose: str) -> str:
    raw = new_token()
    db.add(AuthToken(user_id=user.id, purpose=purpose, token_hash=hash_token(raw), expires_at=utcnow() + timedelta(hours=24)))
    return raw


def _profile_dict(user: User, profile: UserProfile | None, prefs: UserPreference | None, goal: UserGoal | None) -> dict:
    return {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "role": user.role,
        "email_verified": user.email_verified,
        "timezone": user.timezone,
        "currency": user.currency,
        "is_demo": user.is_demo,
        "profile": None if profile is None else {
            "date_of_birth": profile.date_of_birth.isoformat() if profile.date_of_birth else None,
            "gender": profile.gender,
            "height_cm": profile.height_cm,
            "current_weight_kg": profile.current_weight_kg,
            "target_weight_kg": profile.target_weight_kg,
            "start_weight_kg": profile.start_weight_kg,
            "waist_cm": profile.waist_cm,
            "activity_level": profile.activity_level,
            "fitness_experience": profile.fitness_experience,
            "walking_ability": profile.walking_ability,
            "exercise_preference": profile.exercise_preference,
            "gym_available": profile.gym_available,
            "home_workout": profile.home_workout,
            "pregnant": profile.pregnant,
            "breastfeeding": profile.breastfeeding,
            "medical_conditions": profile.medical_conditions,
            "eating_disorder_history": profile.eating_disorder_history,
            "onboarding_completed": profile.onboarding_completed,
            "exercise_minutes_available": profile.exercise_minutes_available,
            "daily_food_budget_pkr": profile.daily_food_budget_pkr,
            "work_schedule": profile.work_schedule,
        },
        "preferences": None if prefs is None else {
            "diet_type": prefs.diet_type,
            "meals_per_day": prefs.meals_per_day,
            "meal_times": prefs.meal_times,
            "cuisines": prefs.cuisines,
            "disliked_foods": prefs.disliked_foods,
            "regional_cuisines": prefs.regional_cuisines,
            "language": prefs.language,
            "theme": prefs.theme,
            "step_target": prefs.step_target,
            "water_goal_ml": prefs.water_goal_ml,
            "quiet_hours_start": prefs.quiet_hours_start,
            "quiet_hours_end": prefs.quiet_hours_end,
            "notification_flags": prefs.notification_flags,
        },
        "goals": None if goal is None else {
            "goal_date": goal.goal_date.isoformat() if goal.goal_date else None,
            "pace": goal.pace,
            "calorie_target": goal.calorie_target,
            "protein_g": goal.protein_g,
            "carbohydrate_g": goal.carbohydrate_g,
            "fat_g": goal.fat_g,
            "fibre_g": goal.fibre_g,
            "hydration_ml": goal.hydration_ml,
            "active_plan_id": goal.active_plan_id,
        },
    }


def _ensure_profile(db: Session, user: User) -> tuple[UserProfile, UserPreference, UserGoal]:
    profile = db.get(UserProfile, user.id)
    prefs = db.get(UserPreference, user.id)
    goal = db.get(UserGoal, user.id)
    if profile is None:
        profile = UserProfile(user_id=user.id)
        db.add(profile)
    if prefs is None:
        prefs = UserPreference(user_id=user.id)
        db.add(prefs)
    if goal is None:
        goal = UserGoal(user_id=user.id)
        db.add(goal)
    db.flush()
    return profile, prefs, goal


@router.post("/auth/register", status_code=201)
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "register")
    email = body.email.lower()
    if db.scalar(select(User).where(User.email == email, User.deleted_at.is_(None))):
        raise AppError(409, "email_taken", "An account with this email already exists.")
    user = User(email=email, password_hash=hash_password(body.password), full_name=body.full_name.strip())
    db.add(user)
    db.flush()
    _ensure_profile(db, user)
    token = _issue_auth_token(db, user, "verify_email")
    payload = _tokens(user, db, request)
    db.commit()
    if get_settings().debug:
        payload["verification_token"] = token
    else:
        payload["verification_token"] = None
    return ok(payload)


@router.post("/auth/login")
def login(body: LoginIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "login")
    user = db.scalar(select(User).where(User.email == body.email.lower(), User.deleted_at.is_(None)))
    if user is None or not verify_password(body.password, user.password_hash) or not user.is_active:
        raise AppError(401, "invalid_credentials", "The email or password is incorrect.")
    payload = _tokens(user, db, request)
    db.commit()
    return ok(payload)


@router.post("/auth/refresh")
def refresh(body: TokenIn, db: Session = Depends(get_db)):
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(body.refresh_token)))
    if stored is None:
        raise AppError(401, "unauthorized", "The refresh token is not valid.")
    if stored.revoked_at is not None:
        db.query(RefreshToken).filter(RefreshToken.user_id == stored.user_id, RefreshToken.revoked_at.is_(None)).update({"revoked_at": utcnow()})
        db.commit()
        raise AppError(401, "token_reused", "This refresh token was already used. Sign in again.")
    if stored.expires_at < utcnow():
        raise AppError(401, "unauthorized", "The refresh token has expired.")
    user = db.get(User, stored.user_id)
    if user is None or user.deleted_at is not None:
        raise AppError(401, "unauthorized", "This account is not available.")
    stored.revoked_at = utcnow()
    raw = new_token()
    settings = get_settings()
    replacement = RefreshToken(user_id=user.id, session_id=stored.session_id, token_hash=hash_token(raw), expires_at=utcnow() + timedelta(days=settings.refresh_token_days))
    db.add(replacement)
    db.flush()
    stored.replaced_by_id = replacement.id
    db.commit()
    return ok({"access_token": create_access_token(user.id, user.role), "refresh_token": raw, "token_type": "bearer"})


@router.post("/auth/logout")
def logout(body: TokenIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    stored = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_token(body.refresh_token), RefreshToken.user_id == user.id))
    if stored and stored.revoked_at is None:
        stored.revoked_at = utcnow()
        session = db.get(UserSession, stored.session_id)
        if session:
            session.revoked_at = utcnow()
    db.commit()
    return ok({"logged_out": True})


@router.post("/auth/forgot-password")
def forgot(body: EmailIn, request: Request, db: Session = Depends(get_db)):
    rate_limit(request, "forgot", limit=6)
    user = db.scalar(select(User).where(User.email == body.email.lower(), User.deleted_at.is_(None)))
    token = None
    if user:
        token = _issue_auth_token(db, user, "reset_password")
        db.commit()
    payload = {"sent": True}
    if get_settings().debug and token:
        payload["reset_token"] = token
    return ok(payload)


@router.post("/auth/reset-password")
def reset_password(body: ResetIn, db: Session = Depends(get_db)):
    stored = db.scalar(select(AuthToken).where(AuthToken.token_hash == hash_token(body.token), AuthToken.purpose == "reset_password"))
    if stored is None or stored.used_at is not None or stored.expires_at < utcnow():
        raise AppError(400, "invalid_token", "This reset link is invalid or expired.")
    user = db.get(User, stored.user_id)
    user.password_hash = hash_password(body.password)
    stored.used_at = utcnow()
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)).update({"revoked_at": utcnow()})
    db.commit()
    return ok({"reset": True})


@router.post("/auth/verify-email")
def verify_email(body: VerifyIn, db: Session = Depends(get_db)):
    stored = db.scalar(select(AuthToken).where(AuthToken.token_hash == hash_token(body.token), AuthToken.purpose == "verify_email"))
    if stored is None or stored.used_at is not None or stored.expires_at < utcnow():
        raise AppError(400, "invalid_token", "This verification link is invalid or expired.")
    user = db.get(User, stored.user_id)
    user.email_verified = True
    stored.used_at = utcnow()
    db.commit()
    return ok({"verified": True})


@router.get("/users/me")
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile, prefs, goal = _ensure_profile(db, user)
    db.commit()
    return ok(_profile_dict(user, profile, prefs, goal))


@router.put("/users/me")
def update_me(body: ProfileIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile, prefs, goal = _ensure_profile(db, user)
    data = body.model_dump(exclude_unset=True)
    if "full_name" in data and data["full_name"]:
        user.full_name = data.pop("full_name")
    if "timezone" in data and data["timezone"]:
        user.timezone = data.pop("timezone")
    if "currency" in data and data["currency"]:
        user.currency = data.pop("currency")
    for key, value in data.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
    if profile.start_weight_kg is None and profile.current_weight_kg:
        profile.start_weight_kg = profile.current_weight_kg
    user.updated_at = utcnow()
    db.commit()
    return ok(_profile_dict(user, profile, prefs, goal))


@router.get("/users/me/preferences")
def get_preferences(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _, prefs, _ = _ensure_profile(db, user)
    allergies = db.scalars(select(UserAllergy).where(UserAllergy.user_id == user.id)).all()
    db.commit()
    return ok({"preferences": _profile_dict(user, None, prefs, None)["preferences"], "allergies": [{"name": item.name, "kind": item.kind} for item in allergies]})


@router.put("/users/me/preferences")
def update_preferences(body: PreferencesIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _, prefs, _ = _ensure_profile(db, user)
    data = body.model_dump(exclude_unset=True)
    allergies = data.pop("allergies", None)
    intolerances = data.pop("intolerances", None)
    for key, value in data.items():
        if hasattr(prefs, key):
            setattr(prefs, key, value)
    if allergies is not None or intolerances is not None:
        db.query(UserAllergy).filter(UserAllergy.user_id == user.id).delete()
        for name in allergies or []:
            db.add(UserAllergy(user_id=user.id, name=name.strip().lower(), kind="allergy"))
        for name in intolerances or []:
            db.add(UserAllergy(user_id=user.id, name=name.strip().lower(), kind="intolerance"))
    db.commit()
    return get_preferences(user, db)


@router.put("/users/me/onboarding")
def onboarding(body: OnboardingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile, prefs, goal = _ensure_profile(db, user)
    data = body.model_dump(exclude_unset=True)
    for key in ("full_name", "timezone", "currency"):
        if data.get(key):
            setattr(user, key, data.pop(key))
    if data.get("goal_date"):
        goal.goal_date = data.pop("goal_date")
    if data.get("pace"):
        goal.pace = data.pop("pace")
    allergies = data.pop("allergies", None) or []
    intolerances = data.pop("intolerances", None) or []
    data.pop("consent_health", None)
    data.pop("consent_ai", None)
    for key, value in data.items():
        if hasattr(profile, key):
            setattr(profile, key, value)
        elif hasattr(prefs, key):
            setattr(prefs, key, value)
    if profile.start_weight_kg is None and profile.current_weight_kg:
        profile.start_weight_kg = profile.current_weight_kg
    profile.onboarding_completed = True
    db.query(UserAllergy).filter(UserAllergy.user_id == user.id).delete()
    for name in allergies:
        db.add(UserAllergy(user_id=user.id, name=name.strip().lower(), kind="allergy"))
    for name in intolerances:
        db.add(UserAllergy(user_id=user.id, name=name.strip().lower(), kind="intolerance"))
    from app.models import ConsentRecord
    db.add(ConsentRecord(user_id=user.id, purpose="health_data", granted=body.consent_health))
    db.add(ConsentRecord(user_id=user.id, purpose="ai_processing", granted=body.consent_ai))
    db.commit()
    return ok(_profile_dict(user, profile, prefs, goal))


@router.delete("/users/me")
def delete_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.deleted_at = utcnow()
    user.is_active = False
    user.email = f"deleted-{user.id}@deleted.fitdesi.local"
    user.full_name = "Deleted user"
    db.query(RefreshToken).filter(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None)).update({"revoked_at": utcnow()})
    audit(db, user.id, "account_deleted", "user", str(user.id), None)
    db.commit()
    return ok({"deleted": True})


@router.get("/users/me/export")
def export_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    profile, prefs, goal = _ensure_profile(db, user)
    logs = db.scalars(select(DailyFoodLog).where(DailyFoodLog.user_id == user.id)).all()
    weights = db.scalars(select(WeightEntry).where(WeightEntry.user_id == user.id)).all()
    return ok({
        "profile": _profile_dict(user, profile, prefs, goal),
        "food_logs": [{"id": item.id, "logged_at": item.logged_at.isoformat(), "meal_type": item.meal_type, "grams": item.grams, "energy_kcal": item.energy_kcal} for item in logs],
        "weights": [{"logged_at": item.logged_at.isoformat(), "weight_kg": item.weight_kg} for item in weights],
    })


def _food_query(db: Session, q: str | None, category: str | None, cuisine: str | None, diet: str | None, page: int, page_size: int):
    stmt = select(Food).where(Food.deleted_at.is_(None), Food.archived_at.is_(None))
    if category:
        stmt = stmt.join(FoodCategory, Food.category_id == FoodCategory.id).where(FoodCategory.slug == category)
    if cuisine:
        stmt = stmt.join(RegionalCuisine, Food.cuisine_id == RegionalCuisine.id).where(RegionalCuisine.slug == cuisine)
    if diet == "vegetarian":
        stmt = stmt.where(Food.is_vegetarian.is_(True))
    if diet == "vegan":
        stmt = stmt.where(Food.is_vegan.is_(True))
    if q:
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(or_(Food.search_text.ilike(like), Food.name_en.ilike(like), Food.name_ur.ilike(like)))
    total = db.scalar(select(func.count()).select_from(stmt.subquery()))
    stmt = stmt.order_by((Food.data_origin == "recipe_estimate").desc(), Food.name_en)
    rows = db.scalars(stmt.offset((page - 1) * page_size).limit(page_size)).all()
    items = _foods_with_nutrition(db, rows)
    if q and len(items) < 3 and len(q.strip()) >= 3:
        from rapidfuzz import fuzz
        candidates = db.scalars(select(Food).where(Food.deleted_at.is_(None)).limit(120)).all()
        ranked = sorted(candidates, key=lambda food: fuzz.token_set_ratio(q.lower(), food.search_text or food.name_en.lower()), reverse=True)
        seen = {item["id"] for item in items}
        extra = []
        for food in ranked:
            if food.id in seen:
                continue
            if fuzz.token_set_ratio(q.lower(), (food.search_text or food.name_en).lower()) < 72:
                break
            extra.append(food)
            if len(items) + len(extra) >= page_size:
                break
        items.extend(_foods_with_nutrition(db, extra))
    return items, total or 0


def _foods_with_nutrition(db: Session, rows: list[Food]) -> list[dict]:
    if not rows:
        return []
    ids = [food.id for food in rows]
    nutrition_rows = db.scalars(select(FoodNutrition).where(FoodNutrition.food_id.in_(ids))).all()
    by_id = {row.food_id: row for row in nutrition_rows}
    return [food_out(food, by_id.get(food.id)) for food in rows]


@router.get("/foods/categories")
def food_categories(db: Session = Depends(get_db)):
    rows = db.scalars(select(FoodCategory).order_by(FoodCategory.sort_order)).all()
    return ok([{"id": row.id, "slug": row.slug, "name_en": row.name_en, "name_ur": row.name_ur} for row in rows])


@router.get("/foods/cuisines")
def food_cuisines(db: Session = Depends(get_db)):
    rows = db.scalars(select(RegionalCuisine).order_by(RegionalCuisine.name_en)).all()
    return ok([{"id": row.id, "slug": row.slug, "name_en": row.name_en, "name_ur": row.name_ur} for row in rows])


@router.get("/foods/suggest")
def suggest_foods(q: str = "", limit: int = 8, db: Session = Depends(get_db)):
    """Prefix and contains matches for the search box. No full-table count."""
    term = " ".join(q.lower().split())
    if len(term) < 2:
        return ok({"items": []})
    cap = min(max(limit, 1), 12)
    prefix = f"{term}%"
    contains = f"%{term}%"
    rows = db.execute(
        select(Food, FoodNutrition)
        .join(FoodNutrition, FoodNutrition.food_id == Food.id)
        .where(
            Food.deleted_at.is_(None),
            Food.archived_at.is_(None),
            or_(Food.name_en.ilike(contains), Food.name_roman.ilike(contains), Food.search_text.ilike(contains)),
        )
        .order_by(
            case((Food.name_en.ilike(prefix), 0), else_=1),
            case((Food.data_origin == "recipe_estimate", 0), else_=1),
            func.length(Food.name_en),
        )
        .limit(cap)
    ).all()
    items = []
    for food, nutrition in rows:
        items.append({
            "id": food.id,
            "name_en": food.name_en,
            "default_serving_g": food.default_serving_g,
            "data_origin": food.data_origin,
            "nutrition_note": food.nutrition_note,
            "per_100g": {"energy_kcal": num(nutrition.energy_kcal) if nutrition else None},
        })
    return ok({"items": items})


@router.get("/foods/search")
def search_foods(q: str = "", category: str | None = None, cuisine: str | None = None, diet: str | None = None, page: int = 1, page_size: int = 20, db: Session = Depends(get_db)):
    items, total = _food_query(db, q, category, cuisine, diet, max(page, 1), min(page_size, 50))
    return ok({"items": items, "total": total, "page": page, "page_size": page_size})


@router.get("/foods")
def list_foods(q: str | None = None, category: str | None = None, cuisine: str | None = None, diet: str | None = None, page: int = 1, page_size: int = 20, db: Session = Depends(get_db)):
    items, total = _food_query(db, q, category, cuisine, diet, max(page, 1), min(page_size, 50))
    return ok({"items": items, "total": total, "page": page, "page_size": page_size})


@router.get("/foods/favourites")
def favourites(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(FoodFavourite).where(FoodFavourite.user_id == user.id)).all()
    items = []
    for row in rows:
        food = db.get(Food, row.food_id)
        if food and food.deleted_at is None:
            items.append(food_out(food, db.get(FoodNutrition, food.id)))
    return ok(items)


@router.post("/foods/favourites", status_code=201)
def add_favourite(food_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    food = db.get(Food, food_id)
    if food is None or food.deleted_at is not None:
        raise AppError(404, "not_found", "That food was not found.")
    existing = db.scalar(select(FoodFavourite).where(FoodFavourite.user_id == user.id, FoodFavourite.food_id == food_id))
    if existing is None:
        db.add(FoodFavourite(user_id=user.id, food_id=food_id))
        db.commit()
    return ok({"food_id": food_id, "favourite": True})


@router.get("/foods/{food_id}")
def get_food(food_id: int, db: Session = Depends(get_db)):
    food = db.get(Food, food_id)
    if food is None or food.deleted_at is not None:
        raise AppError(404, "not_found", "That food was not found.")
    return ok(load_food_bundle(db, food))


@router.post("/foods/{food_id}/portion")
def portion(food_id: int, body: PortionIn, db: Session = Depends(get_db)):
    food = db.get(Food, food_id)
    if food is None:
        raise AppError(404, "not_found", "That food was not found.")
    nutrition = db.get(FoodNutrition, food.id)
    scaled = scale_profile(nutrition_out(nutrition), body.grams)
    return ok({"food_id": food.id, "grams": body.grams, "per_100g": nutrition_out(nutrition), "consumed": scaled, "estimate": food.data_origin != "imported_usda"})


def _diary_out(row: DailyFoodLog) -> dict:
    return {
        "id": row.id,
        "logged_at": row.logged_at.isoformat(),
        "meal_type": row.meal_type,
        "food_id": row.food_id,
        "custom_name": row.custom_name,
        "grams": row.grams,
        "serving_label": row.serving_label,
        "energy_kcal": row.energy_kcal,
        "protein_g": row.protein_g,
        "carbohydrate_g": row.carbohydrate_g,
        "fat_g": row.fat_g,
        "fibre_g": row.fibre_g,
        "sugar_g": row.sugar_g,
        "sodium_mg": row.sodium_mg,
        "source": row.source,
        "client_mutation_id": row.client_mutation_id,
    }


@router.get("/food-diary")
def diary(date_value: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = parse_day(date_value, user)
    start, end = day_window(user, day)
    rows = db.scalars(select(DailyFoodLog).where(DailyFoodLog.user_id == user.id, DailyFoodLog.logged_at >= start, DailyFoodLog.logged_at < end).order_by(DailyFoodLog.logged_at)).all()
    summary = summarize_nutrients([
        {field: getattr(row, field) for field in ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "saturated_fat_g", "fibre_g", "sugar_g", "sodium_mg")}
        for row in rows
    ])
    return ok({"date": day.isoformat(), "items": [_diary_out(row) for row in rows], "summary": summary})


@router.post("/food-diary", status_code=201)
def add_diary(body: DiaryIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = find_mutation(db, DailyFoodLog, user.id, body.client_mutation_id)
    if existing:
        return ok(_diary_out(existing))
    name = body.custom_name
    scaled = {field: None for field in ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "fibre_g", "sugar_g", "sodium_mg")}
    if body.food_id:
        food = db.get(Food, body.food_id)
        if food is None or food.deleted_at is not None:
            raise AppError(404, "not_found", "That food was not found.")
        name = name or food.name_en
        scaled = scale_profile(nutrition_out(db.get(FoodNutrition, food.id)), body.grams)
    elif not name:
        raise AppError(422, "validation_error", "Choose a food or enter a name.")
    row = DailyFoodLog(
        user_id=user.id,
        logged_at=body.logged_at or utcnow(),
        meal_type=body.meal_type,
        food_id=body.food_id,
        custom_name=name,
        grams=body.grams,
        serving_label=body.serving_label,
        energy_kcal=scaled.get("energy_kcal"),
        protein_g=scaled.get("protein_g"),
        carbohydrate_g=scaled.get("carbohydrate_g"),
        fat_g=scaled.get("fat_g"),
        fibre_g=scaled.get("fibre_g"),
        sugar_g=scaled.get("sugar_g"),
        sodium_mg=scaled.get("sodium_mg"),
        client_mutation_id=body.client_mutation_id,
        source="scan" if body.scan_id else "manual",
        scan_id=body.scan_id,
    )
    db.add(row)
    if body.scan_id:
        scan = db.get(AiFoodScan, body.scan_id)
        if scan and scan.user_id == user.id:
            scan.confirmed = True
    db.commit()
    db.refresh(row)
    return ok(_diary_out(row))


@router.put("/food-diary/{entry_id}")
def update_diary(entry_id: int, body: DiaryIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(DailyFoodLog, entry_id)
    if row is None or row.user_id != user.id:
        raise AppError(404, "not_found", "That diary entry was not found.")
    row.meal_type = body.meal_type
    row.grams = body.grams
    row.serving_label = body.serving_label
    if body.logged_at:
        row.logged_at = body.logged_at
    if body.food_id:
        food = db.get(Food, body.food_id)
        if food is None:
            raise AppError(404, "not_found", "That food was not found.")
        row.food_id = food.id
        row.custom_name = food.name_en
        scaled = scale_profile(nutrition_out(db.get(FoodNutrition, food.id)), body.grams)
        for field, value in scaled.items():
            if hasattr(row, field):
                setattr(row, field, value)
    db.commit()
    return ok(_diary_out(row))


@router.post("/food-diary/copy-day", status_code=201)
def copy_diary_day(body: CopyDayIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    source_start, source_end = day_window(user, body.from_date)
    target = body.to_date or parse_day(None, user)
    rows = db.scalars(select(DailyFoodLog).where(DailyFoodLog.user_id == user.id, DailyFoodLog.logged_at >= source_start, DailyFoodLog.logged_at < source_end)).all()
    created = []
    target_start, _ = day_window(user, target)
    for row in rows:
        offset = row.logged_at - source_start
        clone = DailyFoodLog(
            user_id=user.id,
            logged_at=target_start + offset,
            meal_type=row.meal_type,
            food_id=row.food_id,
            custom_name=row.custom_name,
            grams=row.grams,
            serving_label=row.serving_label,
            energy_kcal=row.energy_kcal,
            protein_g=row.protein_g,
            carbohydrate_g=row.carbohydrate_g,
            fat_g=row.fat_g,
            saturated_fat_g=row.saturated_fat_g,
            fibre_g=row.fibre_g,
            sugar_g=row.sugar_g,
            sodium_mg=row.sodium_mg,
            source="copy",
            client_mutation_id=new_token(),
        )
        db.add(clone)
        created.append(clone)
    db.commit()
    for clone in created:
        db.refresh(clone)
    return ok({"copied": len(created), "items": [_diary_out(item) for item in created]})


@router.delete("/food-diary/{entry_id}")
def delete_diary(entry_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(DailyFoodLog, entry_id)
    if row is None or row.user_id != user.id:
        raise AppError(404, "not_found", "That diary entry was not found.")
    db.delete(row)
    db.commit()
    return ok({"deleted": True})


@router.post("/recipes/calculate")
def calculate_recipe(body: RecipeCalcIn, db: Session = Depends(get_db)):
    from app.services.calc import combine_ingredients, per_serving
    items = []
    for ingredient in body.ingredients:
        food = db.get(Food, ingredient.get("food_id")) if ingredient.get("food_id") else None
        if food is None:
            raise AppError(422, "validation_error", "Each ingredient needs a food from the catalogue.")
        items.append((nutrition_out(db.get(FoodNutrition, food.id)), float(ingredient["grams"])))
    cooked = combine_ingredients(items, body.added_water_g, body.water_loss_g)
    return ok({**cooked, "per_serving": per_serving(cooked["totals"], body.servings), "estimate": True,
               "note": "Cooked values use the cooked weight. Raw and cooked weights are not treated as the same."})


@router.get("/recipes")
def list_recipes(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Recipe).where(or_(Recipe.owner_user_id == user.id, Recipe.is_public.is_(True)), Recipe.deleted_at.is_(None)).limit(100)).all()
    return ok([{"id": row.id, "name_en": row.name_en, "name_ur": row.name_ur, "cooked_weight_g": row.cooked_weight_g, "servings": row.servings} for row in rows])


@router.post("/recipes", status_code=201)
def create_recipe(body: RecipeIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from app.services.calc import combine_ingredients
    items = []
    resolved = []
    for ingredient in body.ingredients:
        food = db.get(Food, ingredient.get("food_id"))
        if food is None:
            raise AppError(422, "validation_error", "Each ingredient needs a food from the catalogue.")
        grams = float(ingredient["grams"])
        items.append((nutrition_out(db.get(FoodNutrition, food.id)), grams))
        resolved.append((food, grams))
    cooked = combine_ingredients(items, body.added_water_g, body.water_loss_g)
    recipe = Recipe(owner_user_id=user.id, name_en=body.name_en, name_ur=body.name_ur, name_roman=body.name_roman or body.name_en.lower(),
                    instructions=body.instructions, method=body.method, raw_weight_g=cooked["raw_weight_g"], cooked_weight_g=cooked["cooked_weight_g"],
                    servings=body.servings, yield_notes="User recipe. Nutrition is an estimate from ingredient references and the cooked weight.")
    db.add(recipe)
    db.flush()
    for food, grams in resolved:
        db.add(RecipeIngredient(recipe_id=recipe.id, ingredient_food_id=food.id, name_snapshot=food.name_en, grams=grams))
    db.add(UserSavedRecipe(user_id=user.id, recipe_id=recipe.id))
    db.commit()
    return ok({"id": recipe.id, "cooked": cooked, "estimate": True})


@router.get("/recipes/{recipe_id}")
def get_recipe(recipe_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipe = db.get(Recipe, recipe_id)
    if recipe is None or recipe.deleted_at is not None or (recipe.owner_user_id not in (None, user.id) and not recipe.is_public):
        raise AppError(404, "not_found", "That recipe was not found.")
    ingredients = db.scalars(select(RecipeIngredient).where(RecipeIngredient.recipe_id == recipe.id)).all()
    return ok({"id": recipe.id, "name_en": recipe.name_en, "name_ur": recipe.name_ur, "instructions": recipe.instructions,
               "raw_weight_g": recipe.raw_weight_g, "cooked_weight_g": recipe.cooked_weight_g, "servings": recipe.servings,
               "ingredients": [{"food_id": item.ingredient_food_id, "name": item.name_snapshot, "grams": item.grams} for item in ingredients]})


@router.delete("/recipes/{recipe_id}")
def delete_recipe(recipe_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    recipe = db.get(Recipe, recipe_id)
    if recipe is None or recipe.owner_user_id != user.id:
        raise AppError(404, "not_found", "That recipe was not found.")
    recipe.deleted_at = utcnow()
    db.commit()
    return ok({"deleted": True})


def _range_summary(db: Session, user: User, start: date, end: date) -> dict:
    days = []
    cursor = start
    while cursor <= end:
        window_start, window_end = day_window(user, cursor)
        rows = db.scalars(select(DailyFoodLog).where(DailyFoodLog.user_id == user.id, DailyFoodLog.logged_at >= window_start, DailyFoodLog.logged_at < window_end)).all()
        summary = summarize_nutrients([{field: getattr(row, field) for field in ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "saturated_fat_g", "fibre_g", "sugar_g", "sodium_mg")} for row in rows])
        days.append({"date": cursor.isoformat(), **summary})
        cursor += timedelta(days=1)
    logged = [day for day in days if day["logged"]]
    def avg(field):
        values = [day[field] for day in logged if day.get(field) is not None and not day["incomplete"].get(field)]
        if not values:
            return None
        return round(sum(values) / len(values), 2)
    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "days": days,
        "days_with_logs": len(logged),
        "average_of_logged_days": {field: avg(field) for field in ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "fibre_g")},
        "note": "Days without a food log are missing, not zero.",
    }


@router.get("/nutrition/daily-summary")
def daily_summary(date_value: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = parse_day(date_value, user)
    return ok(_range_summary(db, user, day, day))


@router.get("/nutrition/weekly-summary")
def weekly_summary(date_value: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = parse_day(date_value, user)
    return ok(_range_summary(db, user, day - timedelta(days=6), day))


@router.get("/nutrition/monthly-summary")
def monthly_summary(date_value: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = parse_day(date_value, user)
    return ok(_range_summary(db, user, day - timedelta(days=29), day))


def _plan_foods(db: Session) -> list[dict]:
    rows = db.execute(select(Food, FoodNutrition).join(FoodNutrition, FoodNutrition.food_id == Food.id).where(
        Food.deleted_at.is_(None), Food.kind == "dish", Food.data_origin == "recipe_estimate")).all()
    return [{"id": food.id, "name_en": food.name_en, "name_roman": food.name_roman, "is_vegetarian": food.is_vegetarian, "is_vegan": food.is_vegan, "per_100g": nutrition_out(nutrition)} for food, nutrition in rows]


def _store_plan(db: Session, user: User, body: PlanIn, reason: str) -> WellnessPlan:
    profile, prefs, goal = _ensure_profile(db, user)
    payload = body.model_dump()
    payload["date_of_birth"] = profile.date_of_birth
    if payload.get("age") is None and profile.date_of_birth:
        payload["date_of_birth"] = profile.date_of_birth
    feasibility = assess_feasibility(payload)
    previous = db.scalar(select(WellnessPlan).where(WellnessPlan.user_id == user.id, WellnessPlan.status == "active"))
    if previous:
        previous.status = "archived"
        db.add(PlanAdjustment(user_id=user.id, wellness_plan_id=previous.id, previous_calorie_target=previous.calorie_target,
                              new_calorie_target=feasibility.get("calorie_target"), reason=reason))
    version = (previous.version + 1) if previous else 1
    plan = WellnessPlan(
        user_id=user.id, version=version, title="FitDesi weight plan", status="active",
        safety_status=feasibility["safety_status"], blocked_reason=feasibility.get("blocked_reason"),
        calorie_target=feasibility.get("calorie_target"), protein_g=feasibility.get("protein_g"),
        carbohydrate_g=feasibility.get("carbohydrate_g"), fat_g=feasibility.get("fat_g"),
        fibre_g=feasibility.get("fibre_g"), hydration_ml=feasibility.get("hydration_ml"),
        inputs_json=feasibility.get("inputs"), outputs_json={key: feasibility.get(key) for key in ("bmr", "tdee", "calorie_target", "weekly_change_kg")},
        assumptions_json=feasibility.get("assumptions"), feasibility_json=feasibility,
        start_date=parse_day(None, user), end_date=date.fromisoformat(feasibility["goal_date"]) if feasibility.get("goal_date") else None,
    )
    db.add(plan)
    db.flush()
    if feasibility["safety_status"] != "blocked" and feasibility.get("calorie_target"):
        days = build_meal_plan_days(_plan_foods(db), feasibility["calorie_target"], body.days, body.meals_per_day, body.diet_type, body.allergies, body.disliked_foods)
        meal_plan = MealPlan(user_id=user.id, wellness_plan_id=plan.id, name=f"{body.days}-day Pakistani plan", days=body.days)
        db.add(meal_plan)
        db.flush()
        for day in days:
            day_row = MealPlanDay(meal_plan_id=meal_plan.id, day_index=day["day_index"])
            db.add(day_row)
            db.flush()
            for meal in day["meals"]:
                meal_row = MealPlanMeal(day_id=day_row.id, meal_type=meal["meal_type"], name=meal["name"])
                db.add(meal_row)
                db.flush()
                for item in meal["items"]:
                    db.add(MealPlanItem(meal_id=meal_row.id, food_id=item["food_id"], name_snapshot=item["name"], grams=item["grams"],
                                        energy_kcal=item["energy_kcal"], protein_g=item["protein_g"], carbohydrate_g=item["carbohydrate_g"],
                                        fat_g=item["fat_g"], fibre_g=item["fibre_g"]))
        workout = WorkoutPlan(user_id=user.id, wellness_plan_id=plan.id, name="Weekly movement", level=body.fitness_experience)
        db.add(workout)
        db.flush()
        for day in build_workout_week(body.fitness_experience, body.gym_available, body.home_workout, body.exercise_minutes_available, body.walking_ability):
            db.add(WorkoutPlanDay(plan_id=workout.id, day_index=day["day_index"], title=day["title"], is_rest=day["is_rest"], details_json=day["details"]))
        plan.meal_plan_id = meal_plan.id
        plan.workout_plan_id = workout.id
        db.add(MealPlanVersion(meal_plan_id=meal_plan.id, version=version, reason=reason, snapshot_json={"calorie_target": feasibility["calorie_target"]}))
        goal.calorie_target = feasibility["calorie_target"]
        goal.protein_g = feasibility.get("protein_g")
        goal.carbohydrate_g = feasibility.get("carbohydrate_g")
        goal.fat_g = feasibility.get("fat_g")
        goal.fibre_g = feasibility.get("fibre_g")
        goal.hydration_ml = feasibility.get("hydration_ml")
        goal.active_plan_id = plan.id
        if feasibility.get("goal_date"):
            goal.goal_date = date.fromisoformat(feasibility["goal_date"])
        prefs.water_goal_ml = feasibility.get("hydration_ml") or prefs.water_goal_ml
    profile.current_weight_kg = body.current_weight_kg
    profile.target_weight_kg = feasibility.get("adjusted_target_weight_kg", body.target_weight_kg)
    profile.height_cm = body.height_cm
    profile.activity_level = body.activity_level
    db.add(Notification(user_id=user.id, type="plan", title="Plan updated", body=feasibility.get("blocked_reason") or "A new plan version was saved."))
    return plan


def _plan_out(db: Session, plan: WellnessPlan) -> dict:
    meals = []
    if plan.meal_plan_id:
        days = db.scalars(select(MealPlanDay).where(MealPlanDay.meal_plan_id == plan.meal_plan_id).order_by(MealPlanDay.day_index)).all()
        for day in days:
            day_meals = []
            for meal in db.scalars(select(MealPlanMeal).where(MealPlanMeal.day_id == day.id)).all():
                items = db.scalars(select(MealPlanItem).where(MealPlanItem.meal_id == meal.id)).all()
                day_meals.append({"id": meal.id, "meal_type": meal.meal_type, "items": [
                    {"id": item.id, "food_id": item.food_id, "name": item.name_snapshot, "grams": item.grams, "energy_kcal": item.energy_kcal,
                     "protein_g": item.protein_g, "carbohydrate_g": item.carbohydrate_g, "fat_g": item.fat_g, "fibre_g": item.fibre_g}
                    for item in items
                ]})
            meals.append({"day_index": day.day_index, "meals": day_meals})
    workout_days = []
    if plan.workout_plan_id:
        workout_days = [{"day_index": day.day_index, "title": day.title, "is_rest": day.is_rest, "details": day.details_json}
                        for day in db.scalars(select(WorkoutPlanDay).where(WorkoutPlanDay.plan_id == plan.workout_plan_id)).all()]
    return {
        "id": plan.id, "meal_plan_id": plan.meal_plan_id, "version": plan.version, "status": plan.status, "title": plan.title,
        "safety_status": plan.safety_status, "blocked_reason": plan.blocked_reason,
        "calorie_target": plan.calorie_target, "protein_g": plan.protein_g, "carbohydrate_g": plan.carbohydrate_g,
        "fat_g": plan.fat_g, "fibre_g": plan.fibre_g, "hydration_ml": plan.hydration_ml,
        "formula_name": plan.formula_name, "formula_version": plan.formula_version,
        "feasibility": plan.feasibility_json, "coach_note": (plan.feasibility_json or {}).get("coach_note"), "meals": meals, "workouts": workout_days,
        "created_at": plan.created_at.isoformat(),
    }


@router.post("/plans/feasibility-check")
def feasibility(body: PlanIn, user: User = Depends(get_current_user)):
    return ok(assess_feasibility(body.model_dump()))


@router.post("/plans/generate", status_code=201)
def generate_plan(body: PlanIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = _store_plan(db, user, body, "Generated from the questionnaire.")
    note = explain_plan({
        "calorie_target": plan.calorie_target,
        "protein_g": plan.protein_g,
        "safety_status": plan.safety_status,
        "blocked_reason": plan.blocked_reason,
    })
    feasibility = dict(plan.feasibility_json or {})
    feasibility["coach_note"] = note
    plan.feasibility_json = feasibility
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(plan, "feasibility_json")
    db.commit()
    return ok(_plan_out(db, plan))


@router.get("/plans/current")
def current_plan(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = db.scalar(select(WellnessPlan).where(WellnessPlan.user_id == user.id, WellnessPlan.status == "active"))
    return ok(_plan_out(db, plan) if plan else None)


@router.get("/plans/history")
def plan_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(WellnessPlan).where(WellnessPlan.user_id == user.id).order_by(WellnessPlan.version.desc())).all()
    return ok([{"id": row.id, "version": row.version, "status": row.status, "calorie_target": row.calorie_target, "safety_status": row.safety_status, "created_at": row.created_at.isoformat()} for row in rows])


@router.get("/plans/{plan_id}")
def get_plan(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = db.get(WellnessPlan, plan_id)
    if plan is None or plan.user_id != user.id:
        raise AppError(404, "not_found", "That plan was not found.")
    return ok(_plan_out(db, plan))


@router.post("/plans/{plan_id}/regenerate")
def regenerate(plan_id: int, body: PlanIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current = db.get(WellnessPlan, plan_id)
    if current is None or current.user_id != user.id:
        raise AppError(404, "not_found", "That plan was not found.")
    plan = _store_plan(db, user, body, "Regenerated from the previous plan.")
    db.commit()
    return ok(_plan_out(db, plan))


@router.post("/plans/{plan_id}/replace-item")
def replace_item(plan_id: int, item_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = db.get(WellnessPlan, plan_id)
    item = db.get(MealPlanItem, item_id)
    if plan is None or plan.user_id != user.id or item is None:
        raise AppError(404, "not_found", "That meal item was not found.")
    _, prefs, _ = _ensure_profile(db, user)
    allergies = [row.name for row in db.scalars(select(UserAllergy).where(UserAllergy.user_id == user.id)).all()]
    suggestion = suggest_replacement(_plan_foods(db), item.food_id or 0, item.energy_kcal or 0, prefs.diet_type, allergies, prefs.disliked_foods or [])
    if suggestion is None:
        raise AppError(404, "no_alternative", "No alternative food fitted this meal.")
    item.food_id = suggestion["food_id"]
    item.name_snapshot = suggestion["name"]
    item.grams = suggestion["grams"]
    item.energy_kcal = suggestion["energy_kcal"]
    item.protein_g = suggestion["protein_g"]
    item.carbohydrate_g = suggestion["carbohydrate_g"]
    item.fat_g = suggestion["fat_g"]
    item.fibre_g = suggestion["fibre_g"]
    db.commit()
    return ok(suggestion)


def _select_steps(db: Session, user_id: int, day: date) -> dict | None:
    rows = db.scalars(select(DailySteps).where(DailySteps.user_id == user_id, DailySteps.day == day)).all()
    chosen = choose_step_source([{"id": row.id, "source": row.source, "steps": row.steps, "distance_m": row.distance_m, "duration_min": row.duration_min, "active_kcal": row.active_kcal} for row in rows])
    if chosen is None:
        return None
    for row in rows:
        row.selected = row.id == chosen["id"]
    return chosen


@router.get("/activity/steps")
def get_steps(date_value: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = parse_day(date_value, user)
    chosen = _select_steps(db, user.id, day)
    db.commit()
    if chosen is None:
        return ok({"date": day.isoformat(), "logged": False, "steps": None, "source": None})
    return ok({"date": day.isoformat(), "logged": True, **chosen, "distance_m": chosen.get("distance_m") or walking_distance_m(chosen["steps"]), "duration_min": chosen.get("duration_min") or walking_minutes(chosen["steps"])})


@router.post("/activity/steps/sync")
def sync_steps(body: StepsIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.scalar(select(DailySteps).where(DailySteps.user_id == user.id, DailySteps.day == body.day, DailySteps.source == body.source))
    if row is None:
        row = DailySteps(user_id=user.id, day=body.day, source=body.source)
        db.add(row)
    row.steps = body.steps
    row.distance_m = body.distance_m if body.distance_m is not None else walking_distance_m(body.steps)
    row.duration_min = body.duration_min if body.duration_min is not None else walking_minutes(body.steps)
    row.active_kcal = body.active_kcal
    row.timezone = body.timezone
    row.synced_at = utcnow()
    db.flush()
    chosen = _select_steps(db, user.id, body.day)
    db.commit()
    return ok({"saved_source": body.source, "selected": chosen})


@router.get("/activity/history")
def activity_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(DailySteps).where(DailySteps.user_id == user.id).order_by(DailySteps.day.desc()).limit(60)).all()
    return ok([{"day": row.day.isoformat(), "steps": row.steps, "source": row.source, "selected": row.selected} for row in rows])


@router.get("/activity/workouts")
def list_workouts(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Workout).where(Workout.user_id == user.id).order_by(Workout.started_at.desc()).limit(50)).all()
    return ok([{"id": row.id, "name": row.name, "category": row.category, "status": row.status, "started_at": row.started_at.isoformat(), "duration_min": row.duration_min, "energy_kcal": row.energy_kcal, "distance_m": row.distance_m} for row in rows])


@router.post("/activity/workouts", status_code=201)
def create_workout(body: WorkoutIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = find_mutation(db, Workout, user.id, body.client_mutation_id)
    if existing:
        return ok({"id": existing.id, "duplicate": True})
    profile = db.get(UserProfile, user.id)
    weight = profile.current_weight_kg if profile and profile.current_weight_kg else None
    duration = body.duration_min
    if duration is None and body.ended_at:
        duration = round((body.ended_at - body.started_at).total_seconds() / 60, 1)
    exercise = db.scalar(select(Exercise).where(Exercise.category == body.category))
    kcal = None
    if weight and duration:
        kcal = estimate_activity_kcal(exercise.met if exercise else 4.0, weight, duration)
    row = Workout(user_id=user.id, name=body.name, category=body.category, status=body.status, started_at=body.started_at,
                  ended_at=body.ended_at, duration_min=duration, distance_m=body.distance_m, energy_kcal=kcal, notes=body.notes,
                  client_mutation_id=body.client_mutation_id, exercise_id=exercise.id if exercise else None)
    db.add(row)
    db.flush()
    for item in body.exercises:
        db.add(WorkoutExercise(workout_id=row.id, name=item.get("name", body.name), sets=item.get("sets"), reps=item.get("reps"), weight_kg=item.get("weight_kg"), rest_sec=item.get("rest_sec"), notes=item.get("notes")))
    db.commit()
    return ok({"id": row.id, "energy_kcal": kcal, "energy_is_estimate": True})


@router.put("/activity/workouts/{workout_id}")
def update_workout(workout_id: int, body: WorkoutIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(Workout, workout_id)
    if row is None or row.user_id != user.id:
        raise AppError(404, "not_found", "That workout was not found.")
    row.status = body.status
    row.ended_at = body.ended_at
    row.notes = body.notes
    if body.duration_min is not None:
        row.duration_min = body.duration_min
    db.commit()
    return ok({"id": row.id, "status": row.status})


@router.get("/weight/history")
def weight_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(WeightEntry).where(WeightEntry.user_id == user.id).order_by(WeightEntry.logged_at)).all()
    points = [(row.logged_at.date(), row.weight_kg) for row in rows]
    return ok({"entries": [{"id": row.id, "logged_at": row.logged_at.isoformat(), "weight_kg": row.weight_kg, "note": row.note} for row in rows], "trend": weight_trend(points)})


@router.post("/weight", status_code=201)
def add_weight(body: WeightIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = find_mutation(db, WeightEntry, user.id, body.client_mutation_id)
    if existing:
        return ok({"id": existing.id, "duplicate": True})
    row = WeightEntry(user_id=user.id, weight_kg=body.weight_kg, logged_at=body.logged_at or utcnow(), note=body.note, client_mutation_id=body.client_mutation_id)
    db.add(row)
    profile, _, _ = _ensure_profile(db, user)
    if profile.start_weight_kg is None:
        profile.start_weight_kg = body.weight_kg
    profile.current_weight_kg = body.weight_kg
    db.commit()
    return ok({"id": row.id, "weight_kg": row.weight_kg})


@router.delete("/weight/{entry_id}")
def delete_weight(entry_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(WeightEntry, entry_id)
    if row is None or row.user_id != user.id:
        raise AppError(404, "not_found", "That weight entry was not found.")
    db.delete(row)
    db.commit()
    return ok({"deleted": True})


@router.post("/weight/measurements", status_code=201)
def add_measurement(body: MeasureIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = BodyMeasurement(user_id=user.id, **body.model_dump())
    db.add(row)
    db.commit()
    return ok({"id": row.id})


@router.get("/water/daily")
def water_daily(date_value: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = parse_day(date_value, user)
    start, end = day_window(user, day)
    rows = db.scalars(select(WaterLog).where(WaterLog.user_id == user.id, WaterLog.logged_at >= start, WaterLog.logged_at < end)).all()
    prefs = db.get(UserPreference, user.id)
    total = sum(row.amount_ml for row in rows) if rows else None
    return ok({"date": day.isoformat(), "logged": bool(rows), "amount_ml": total, "goal_ml": prefs.water_goal_ml if prefs else None,
               "items": [{"id": row.id, "amount_ml": row.amount_ml, "logged_at": row.logged_at.isoformat()} for row in rows]})


@router.post("/water", status_code=201)
def add_water(body: WaterIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = find_mutation(db, WaterLog, user.id, body.client_mutation_id)
    if existing:
        return ok({"id": existing.id, "duplicate": True})
    row = WaterLog(user_id=user.id, amount_ml=body.amount_ml, logged_at=body.logged_at or utcnow(), client_mutation_id=body.client_mutation_id)
    db.add(row)
    db.commit()
    return ok({"id": row.id, "amount_ml": row.amount_ml})


@router.delete("/water/{entry_id}")
def delete_water(entry_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(WaterLog, entry_id)
    if row is None or row.user_id != user.id:
        raise AppError(404, "not_found", "That water entry was not found.")
    db.delete(row)
    db.commit()
    return ok({"deleted": True})


@router.get("/sleep/history")
def sleep_history(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(SleepLog).where(SleepLog.user_id == user.id).order_by(SleepLog.sleep_start.desc()).limit(30)).all()
    return ok([{"id": row.id, "sleep_start": row.sleep_start.isoformat(), "sleep_end": row.sleep_end.isoformat(), "duration_min": row.duration_min, "source": row.source} for row in rows])


@router.post("/sleep", status_code=201)
def add_sleep(body: SleepIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    existing = find_mutation(db, SleepLog, user.id, body.client_mutation_id)
    if existing:
        return ok({"id": existing.id, "duplicate": True})
    if body.sleep_end <= body.sleep_start:
        raise AppError(422, "validation_error", "Wake time must be after sleep time.")
    minutes = round((body.sleep_end - body.sleep_start).total_seconds() / 60, 1)
    row = SleepLog(user_id=user.id, sleep_start=body.sleep_start, sleep_end=body.sleep_end, duration_min=minutes, source=body.source, client_mutation_id=body.client_mutation_id)
    db.add(row)
    db.commit()
    return ok({"id": row.id, "duration_min": minutes, "source": body.source})


@router.post("/ai/food-recognition")
async def food_recognition(file: UploadFile = File(...), user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise AppError(413, "file_too_large", "Images must be 5 MB or smaller.")
    if file.content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise AppError(415, "unsupported_file", "Use a JPEG, PNG, or WebP photo.")
    from io import BytesIO
    from PIL import Image
    from app.core.config import get_settings
    image = Image.open(BytesIO(content))
    image.thumbnail((1280, 1280))
    out = BytesIO()
    image.convert("RGB").save(out, format="JPEG", quality=80)
    path = get_settings().storage_path / "scans" / f"{user.id}-{new_token()[:10]}.jpg"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(out.getvalue())
    result = recognise_foods(out.getvalue(), "image/jpeg")
    predictions = []
    for item in result.get("predictions") or []:
        name = item.get("name") or ""
        match = db.scalar(select(Food).where(Food.search_text.ilike(f"%{name.lower()}%"), Food.deleted_at.is_(None))) if name else None
        predictions.append({"name": name, "confidence": item.get("confidence"), "portion_note": item.get("portion_note"), "food_id": match.id if match else None, "matched_name": match.name_en if match else None})
    scan = AiFoodScan(user_id=user.id, image_path=str(path), provider=result.get("provider") or "unconfigured", status=result.get("status") or "estimated", predictions_json={"items": predictions, "message": result.get("message")}, confirmed=False)
    db.add(scan)
    db.commit()
    return ok({"scan_id": scan.id, "status": scan.status, "message": result.get("message"), "predictions": predictions, "requires_confirmation": True})


@router.delete("/ai/scans/{scan_id}")
def delete_scan(scan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    scan = db.get(AiFoodScan, scan_id)
    if scan is None or scan.user_id != user.id:
        raise AppError(404, "not_found", "That scan was not found.")
    if scan.image_path:
        from pathlib import Path
        Path(scan.image_path).unlink(missing_ok=True)
    scan.deleted_at = utcnow()
    scan.image_path = None
    db.commit()
    return ok({"deleted": True})


@router.post("/ai/consultant/chat")
def chat(body: ChatIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = parse_day(None, user)
    start, end = day_window(user, today)
    logs = db.scalars(select(DailyFoodLog).where(DailyFoodLog.user_id == user.id, DailyFoodLog.logged_at >= start, DailyFoodLog.logged_at < end)).all()
    summary = summarize_nutrients([{field: getattr(row, field) for field in ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "saturated_fat_g", "fibre_g", "sugar_g", "sodium_mg")} for row in logs])
    breakfast = [row.energy_kcal for row in logs if row.meal_type == "breakfast" and row.energy_kcal is not None]
    summary["breakfast_kcal"] = round(sum(breakfast), 1) if breakfast else None
    goal = db.get(UserGoal, user.id)
    plan = db.scalar(select(WellnessPlan).where(WellnessPlan.user_id == user.id, WellnessPlan.status == "active"))
    weights = db.scalars(select(WeightEntry).where(WeightEntry.user_id == user.id)).all()
    steps = _select_steps(db, user.id, today)
    prefs = db.get(UserPreference, user.id)
    quota = 30
    setting = db.get(ApplicationSetting, "ai_daily_quota")
    if setting and isinstance(setting.value_json, int):
        quota = setting.value_json
    since = utcnow() - timedelta(days=1)
    used = db.scalar(select(func.count()).select_from(AiChatMessage).join(AiChatSession).where(AiChatSession.user_id == user.id, AiChatMessage.role == "user", AiChatMessage.created_at >= since))
    if (used or 0) >= quota:
        raise AppError(429, "quota", "The daily consultant quota is reached. No charge has been made.")
    matches = db.scalars(select(Food).where(Food.search_text.ilike(f"%{body.message.lower().split()[0]}%"), Food.deleted_at.is_(None)).limit(3)).all() if body.message.strip() else []
    context = {
        "today": summary,
        "plan": {"calorie_target": plan.calorie_target if plan else (goal.calorie_target if goal else None), "safety_status": plan.safety_status if plan else None},
        "weight": weight_trend([(row.logged_at.date(), row.weight_kg) for row in weights]),
        "steps": steps["steps"] if steps else None,
        "step_target": prefs.step_target if prefs else None,
        "food_matches": [{"name": food.name_en, "energy_kcal": num(db.get(FoodNutrition, food.id).energy_kcal) if db.get(FoodNutrition, food.id) else None} for food in matches],
    }
    session = db.get(AiChatSession, body.session_id) if body.session_id else None
    if session is None or session.user_id != user.id:
        session = AiChatSession(user_id=user.id, language=body.language, title=body.message[:80])
        db.add(session)
        db.flush()
    reply = consultant_reply(body.message, context, "en")
    db.add(AiChatMessage(session_id=session.id, role="user", content=body.message, provider="user"))
    db.add(AiChatMessage(session_id=session.id, role="assistant", content=reply["content"], provider=reply["provider"], context_json=context))
    db.commit()
    return ok({"session_id": session.id, "reply": reply["content"], "provider": reply["provider"], "based_on_records": True})


@router.get("/ai/tip")
def ai_tip(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = parse_day(None, user)
    start, end = day_window(user, today)
    logs = db.scalars(select(DailyFoodLog).where(DailyFoodLog.user_id == user.id, DailyFoodLog.logged_at >= start, DailyFoodLog.logged_at < end)).all()
    summary = summarize_nutrients([{field: getattr(row, field) for field in ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g")} for row in logs])
    goal = db.get(UserGoal, user.id)
    plan = db.scalar(select(WellnessPlan).where(WellnessPlan.user_id == user.id, WellnessPlan.status == "active"))
    steps = _select_steps(db, user.id, today)
    context = {
        "today": {"energy_kcal": summary.get("energy_kcal"), "logged": summary.get("logged")},
        "plan": {"calorie_target": plan.calorie_target if plan else (goal.calorie_target if goal else None)},
        "steps": steps["steps"] if steps else None,
    }
    return ok({"tip": daily_tip(context)})


@router.post("/ai/meal-idea")
def meal_idea(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    today = parse_day(None, user)
    start, end = day_window(user, today)
    logs = db.scalars(select(DailyFoodLog).where(DailyFoodLog.user_id == user.id, DailyFoodLog.logged_at >= start, DailyFoodLog.logged_at < end)).all()
    summary = summarize_nutrients([{"energy_kcal": row.energy_kcal} for row in logs])
    goal = db.get(UserGoal, user.id)
    plan = db.scalar(select(WellnessPlan).where(WellnessPlan.user_id == user.id, WellnessPlan.status == "active"))
    target = plan.calorie_target if plan and plan.calorie_target else (goal.calorie_target if goal else None)
    consumed = summary.get("energy_kcal") if summary.get("logged") else None
    remaining = None if target is None or consumed is None else round(target - consumed, 1)
    rows = db.execute(
        select(Food, FoodNutrition)
        .join(FoodNutrition, FoodNutrition.food_id == Food.id)
        .where(Food.deleted_at.is_(None), Food.data_origin == "recipe_estimate", FoodNutrition.energy_kcal.is_not(None))
        .order_by(Food.name_en)
        .limit(12)
    ).all()
    candidates = [{
        "id": food.id,
        "name": food.name_en,
        "energy_kcal": num(nutrition.energy_kcal),
        "default_serving_g": food.default_serving_g,
    } for food, nutrition in rows]
    choice = choose_meal(candidates, remaining)
    return ok({**choice, "remaining_kcal": remaining})


@router.get("/meal-plans")
def meal_plans(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(MealPlan).where(MealPlan.user_id == user.id).order_by(MealPlan.created_at.desc())).all()
    return ok([{"id": row.id, "name": row.name, "days": row.days, "status": row.status} for row in rows])


@router.post("/meal-plans", status_code=201)
def create_meal_plan(body: PlanIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    plan = _store_plan(db, user, body, "Created from the meal planner.")
    db.commit()
    return ok(_plan_out(db, plan))


@router.get("/meal-plans/{plan_id}")
def get_meal_plan(plan_id: int, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(MealPlan, plan_id)
    if row is None or row.user_id != user.id:
        raise AppError(404, "not_found", "That meal plan was not found.")
    parent = db.scalar(select(WellnessPlan).where(WellnessPlan.meal_plan_id == row.id))
    if parent:
        return ok(_plan_out(db, parent))
    return ok({"id": row.id, "name": row.name, "days": row.days})


def _grocery_out(db: Session, row: GroceryList) -> dict:
    items = db.scalars(select(GroceryListItem).where(GroceryListItem.list_id == row.id)).all()
    return {
        "id": row.id,
        "name": row.name,
        "budget_pkr": row.budget_pkr,
        "items": [
            {
                "id": item.id,
                "name": item.name,
                "quantity_g": item.quantity_g,
                "purchased": item.purchased,
                "price_amount": item.price_amount,
                "currency": item.currency,
                "price_source": item.price_source,
                "price_updated_at": item.price_updated_at.isoformat() if item.price_updated_at else None,
            }
            for item in items
        ],
    }


@router.get("/grocery-lists")
def grocery_lists(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(GroceryList).where(GroceryList.user_id == user.id)).all()
    return ok([_grocery_out(db, row) for row in rows])


@router.post("/grocery-lists", status_code=201)
def create_grocery(body: GroceryIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = GroceryList(user_id=user.id, name=body.name, meal_plan_id=body.meal_plan_id, budget_pkr=body.budget_pkr)
    db.add(row)
    db.flush()
    if body.meal_plan_id:
        plan = db.get(MealPlan, body.meal_plan_id)
        if plan and plan.user_id == user.id:
            days = db.scalars(select(MealPlanDay).where(MealPlanDay.meal_plan_id == plan.id)).all()
            totals: dict[str, float] = {}
            for day in days:
                meals = db.scalars(select(MealPlanMeal).where(MealPlanMeal.day_id == day.id)).all()
                for meal in meals:
                    for item in db.scalars(select(MealPlanItem).where(MealPlanItem.meal_id == meal.id)).all():
                        totals[item.name_snapshot] = totals.get(item.name_snapshot, 0) + item.grams
            for name, grams in totals.items():
                db.add(GroceryListItem(list_id=row.id, name=name, quantity_g=round(grams, 1), price_amount=None, price_source=None))
    for item in body.items:
        db.add(GroceryListItem(list_id=row.id, name=item["name"], quantity_g=item.get("quantity_g"), price_amount=item.get("price_amount"),
                               currency=item.get("currency") or "PKR", price_source="manual_entry" if item.get("price_amount") is not None else None,
                               price_updated_at=utcnow() if item.get("price_amount") is not None else None, is_custom=True))
    db.commit()
    return ok({"id": row.id, "note": "Prices are saved only when you enter them. FitDesi does not invent supermarket prices."})


@router.put("/grocery-lists/{list_id}")
def update_grocery(list_id: int, body: GroceryIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(GroceryList, list_id)
    if row is None or row.user_id != user.id:
        raise AppError(404, "not_found", "That list was not found.")
    row.name = body.name or row.name
    row.budget_pkr = body.budget_pkr
    for item in body.items:
        stored = db.get(GroceryListItem, item.get("id")) if item.get("id") else None
        if stored is None or stored.list_id != row.id:
            continue
        if "purchased" in item:
            stored.purchased = bool(item["purchased"])
        if item.get("price_amount") is not None:
            stored.price_amount = item["price_amount"]
            stored.currency = item.get("currency") or "PKR"
            stored.price_source = "manual_entry"
            stored.price_updated_at = utcnow()
    db.commit()
    return ok(_grocery_out(db, row))


@router.get("/consultants")
def consultants(db: Session = Depends(get_db)):
    rows = db.scalars(select(ConsultantProfile).where(ConsultantProfile.active.is_(True))).all()
    return ok([_consultant_out(db, row) for row in rows])


def _consultant_out(db: Session, row: ConsultantProfile) -> dict:
    services = db.scalars(select(ConsultantService).where(ConsultantService.consultant_id == row.id, ConsultantService.active.is_(True))).all()
    return {
        "id": row.id, "display_name": row.display_name, "qualifications": row.qualifications, "bio": row.bio,
        "specialization": row.specialization, "experience_years": row.experience_years, "languages": row.languages,
        "online_available": row.online_available, "in_person_available": row.in_person_available,
        "verification_status": row.verification_status, "is_demo": row.is_demo, "fee_disclaimer": row.fee_disclaimer,
        "services": [{"id": item.id, "service_type": item.service_type, "title": item.title, "duration_min": item.duration_min,
                      "price_amount": item.price_amount, "currency": item.currency, "price_source": item.price_source,
                      "platform_fee_amount": item.platform_fee_amount, "tax_amount": item.tax_amount} for item in services],
    }


@router.get("/consultants/{consultant_id}")
def consultant_detail(consultant_id: int, db: Session = Depends(get_db)):
    row = db.get(ConsultantProfile, consultant_id)
    if row is None:
        raise AppError(404, "not_found", "That consultant was not found.")
    return ok(_consultant_out(db, row))


@router.get("/consultants/{consultant_id}/availability")
def consultant_availability(consultant_id: int, db: Session = Depends(get_db)):
    rows = db.scalars(select(ConsultantAvailability).where(ConsultantAvailability.consultant_id == consultant_id)).all()
    return ok([{"weekday": row.weekday, "start_time": row.start_time, "end_time": row.end_time} for row in rows])


@router.post("/consultant-bookings", status_code=201)
def book(body: BookingIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    service = db.get(ConsultantService, body.service_id)
    if service is None or service.consultant_id != body.consultant_id or not service.active:
        raise AppError(404, "not_found", "That consultation service was not found.")
    end = body.start_at + timedelta(minutes=service.duration_min)
    overlap = db.scalar(select(ConsultantBooking).where(ConsultantBooking.consultant_id == body.consultant_id, ConsultantBooking.status.in_(["requested", "confirmed"]), ConsultantBooking.start_at < end, ConsultantBooking.end_at > body.start_at))
    if overlap:
        raise AppError(409, "slot_taken", "That time is already booked.")
    booking = ConsultantBooking(user_id=user.id, consultant_id=body.consultant_id, service_id=service.id, start_at=body.start_at, end_at=end, status="requested", payment_status="unpaid", notes=body.notes)
    db.add(booking)
    db.flush()
    db.add(PaymentRecord(user_id=user.id, booking_id=booking.id, provider=get_settings().payment_provider or "none", amount=service.price_amount + service.platform_fee_amount + service.tax_amount, currency=service.currency, status="not_configured"))
    db.commit()
    return ok({"id": booking.id, "status": booking.status, "payment_status": "not_configured", "message": "The booking is saved. No payment was taken because a payment provider is not configured."})


@router.get("/consultant-bookings")
def my_bookings(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(ConsultantBooking).where(ConsultantBooking.user_id == user.id).order_by(ConsultantBooking.start_at.desc())).all()
    return ok([{"id": row.id, "consultant_id": row.consultant_id, "start_at": row.start_at.isoformat(), "end_at": row.end_at.isoformat(), "status": row.status, "payment_status": row.payment_status} for row in rows])


@router.post("/consultant-bookings/{booking_id}/cancel")
def cancel_booking(booking_id: int, body: CancelIn, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    row = db.get(ConsultantBooking, booking_id)
    if row is None or row.user_id != user.id:
        raise AppError(404, "not_found", "That booking was not found.")
    row.status = "cancelled"
    row.cancel_reason = body.reason
    db.commit()
    return ok({"id": row.id, "status": row.status, "refund": "No payment was captured, so there is nothing to refund."})


@router.get("/reports/weekly")
def report_weekly(date_value: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = parse_day(date_value, user)
    nutrition = _range_summary(db, user, day - timedelta(days=6), day)
    weights = db.scalars(select(WeightEntry).where(WeightEntry.user_id == user.id)).all()
    return ok({"nutrition": nutrition, "weight": weight_trend([(row.logged_at.date(), row.weight_kg) for row in weights])})


@router.get("/reports/monthly")
def report_monthly(date_value: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = parse_day(date_value, user)
    return ok(_range_summary(db, user, day - timedelta(days=29), day))


@router.get("/reports/export")
def export_report(fmt: str = "csv", date_value: str | None = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    from fastapi.responses import Response
    day = parse_day(date_value, user)
    summary = _range_summary(db, user, day - timedelta(days=6), day)
    if fmt == "pdf":
        from io import BytesIO
        from reportlab.pdfgen import canvas
        buffer = BytesIO()
        pdf = canvas.Canvas(buffer)
        pdf.drawString(40, 800, "FitDesi weekly report")
        pdf.drawString(40, 780, "Days without logs are missing, not zero.")
        y = 750
        for item in summary["days"]:
            pdf.drawString(40, y, f"{item['date']}: logged={item['logged']} kcal={item['energy_kcal']}")
            y -= 18
        pdf.save()
        return Response(buffer.getvalue(), media_type="application/pdf", headers={"Content-Disposition": "attachment; filename=fitdesi-week.pdf"})
    lines = ["date,logged,energy_kcal,protein_g,carbohydrate_g,fat_g"]
    for item in summary["days"]:
        lines.append(",".join(str(item[key] if item[key] is not None else "") for key in ("date", "logged", "energy_kcal", "protein_g", "carbohydrate_g", "fat_g")))
    return Response("\n".join(lines), media_type="text/csv", headers={"Content-Disposition": "attachment; filename=fitdesi-week.csv"})


@router.get("/dashboard/today")
def dashboard(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    day = parse_day(None, user)
    start, end = day_window(user, day)
    logs = db.scalars(select(DailyFoodLog).where(DailyFoodLog.user_id == user.id, DailyFoodLog.logged_at >= start, DailyFoodLog.logged_at < end)).all()
    nutrition = summarize_nutrients([{field: getattr(row, field) for field in ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "saturated_fat_g", "fibre_g", "sugar_g", "sodium_mg")} for row in logs])
    meals = {}
    for row in logs:
        meals.setdefault(row.meal_type, 0)
        if row.energy_kcal is not None:
            meals[row.meal_type] = round(meals[row.meal_type] + row.energy_kcal, 1)
    goal = db.get(UserGoal, user.id)
    profile = db.get(UserProfile, user.id)
    plan = db.scalar(select(WellnessPlan).where(WellnessPlan.user_id == user.id, WellnessPlan.status == "active"))
    steps = _select_steps(db, user.id, day)
    water_rows = db.scalars(select(WaterLog).where(WaterLog.user_id == user.id, WaterLog.logged_at >= start, WaterLog.logged_at < end)).all()
    workouts = db.scalars(select(Workout).where(Workout.user_id == user.id, Workout.started_at >= start, Workout.started_at < end)).all()
    weights = db.scalars(select(WeightEntry).where(WeightEntry.user_id == user.id).order_by(WeightEntry.logged_at)).all()
    prefs = db.get(UserPreference, user.id)
    earned = _achievements(db, user)
    db.commit()
    target = plan.calorie_target if plan and plan.calorie_target else (goal.calorie_target if goal else None)
    consumed = nutrition["energy_kcal"] if nutrition["logged"] else None
    return ok({
        "date": day.isoformat(),
        "calorie_target": target,
        "calories_consumed": consumed,
        "remaining": None if consumed is None or target is None else round(target - consumed, 1),
        "meals": meals if logs else None,
        "macros": nutrition,
        "expenditure": {"tdee": (plan.feasibility_json or {}).get("tdee") if plan else None, "active_exercise_kcal": round(sum(row.energy_kcal or 0 for row in workouts), 1) if workouts else None,
                        "note": "Active exercise calories are shown separately and are not added back to the food budget."},
        "steps": steps,
        "step_target": prefs.step_target if prefs else None,
        "water_ml": sum(row.amount_ml for row in water_rows) if water_rows else None,
        "water_goal_ml": prefs.water_goal_ml if prefs else None,
        "weight": weight_trend([(row.logged_at.date(), row.weight_kg) for row in weights]),
        "targets": {"current_weight_kg": profile.current_weight_kg if profile else None, "target_weight_kg": profile.target_weight_kg if profile else None, "start_weight_kg": profile.start_weight_kg if profile else None},
        "plan": {"id": plan.id, "safety_status": plan.safety_status, "calorie_target": plan.calorie_target} if plan else None,
        "achievements": earned,
    })


def _achievements(db: Session, user: User) -> list[dict]:
    codes = set()
    if db.scalar(select(DailyFoodLog.id).where(DailyFoodLog.user_id == user.id)):
        codes.add("first_log")
    days = db.scalars(select(func.date(DailyFoodLog.logged_at)).where(DailyFoodLog.user_id == user.id).distinct()).all()
    if len(days) >= 7:
        codes.add("seven_day_logs")
    prefs = db.get(UserPreference, user.id)
    today = parse_day(None, user)
    steps = db.scalar(select(DailySteps).where(DailySteps.user_id == user.id, DailySteps.day == today, DailySteps.selected.is_(True)))
    if steps and prefs and steps.steps >= prefs.step_target:
        codes.add("step_goal")
    earned = []
    for code in codes:
        achievement = db.scalar(select(Achievement).where(Achievement.code == code))
        if achievement is None:
            continue
        if db.scalar(select(UserAchievement).where(UserAchievement.user_id == user.id, UserAchievement.achievement_id == achievement.id)) is None:
            db.add(UserAchievement(user_id=user.id, achievement_id=achievement.id))
        earned.append({"code": code, "name": achievement.name})
    return earned


@router.get("/exercises")
def exercises(db: Session = Depends(get_db)):
    rows = db.scalars(select(Exercise).order_by(Exercise.name)).all()
    return ok([{"id": row.id, "name": row.name, "category": row.category, "instructions": row.instructions, "met": row.met, "level": row.level} for row in rows])


@router.get("/notifications")
def notifications(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    rows = db.scalars(select(Notification).where(Notification.user_id == user.id).order_by(Notification.created_at.desc()).limit(30)).all()
    return ok([{"id": row.id, "type": row.type, "title": row.title, "body": row.body, "read": row.read} for row in rows])


@router.post("/admin/foods", status_code=201)
def admin_add_food(body: FoodAdminIn, admin: User = Depends(get_admin), db: Session = Depends(get_db)):
    from seeds.catalog import slugify
    food = Food(slug=slugify(body.name_en) + f"-{int(utcnow().timestamp())}", name_en=body.name_en, name_ur=body.name_ur, name_roman=body.name_roman or body.name_en.lower(),
                category_id=body.category_id, cuisine_id=body.cuisine_id, kind=body.kind, is_vegetarian=body.is_vegetarian, is_vegan=body.is_vegan,
                data_origin=body.data_origin, data_confidence=body.data_confidence, nutrition_note=body.nutrition_note, verification_status="awaiting_verification",
                search_text=" ".join([body.name_en, body.name_ur, body.name_roman, *body.aliases]).lower())
    db.add(food)
    db.flush()
    db.add(FoodNutrition(food_id=food.id, **{key: body.per_100g.get(key) for key in ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "saturated_fat_g", "fibre_g", "sugar_g", "sodium_mg")}))
    for alias in body.aliases:
        db.add(FoodAlias(food_id=food.id, alias=alias))
    for serving in body.servings or [{"label": "100 g", "grams": 100}]:
        db.add(FoodServing(food_id=food.id, label=serving["label"], grams=serving["grams"]))
    audit(db, admin.id, "food_created", "food", str(food.id), {"name": food.name_en})
    db.commit()
    return ok({"id": food.id})


@router.put("/admin/foods/{food_id}")
def admin_update_food(food_id: int, body: FoodAdminIn, admin: User = Depends(get_admin), db: Session = Depends(get_db)):
    food = db.get(Food, food_id)
    if food is None:
        raise AppError(404, "not_found", "That food was not found.")
    food.name_en = body.name_en
    food.name_ur = body.name_ur
    food.nutrition_note = body.nutrition_note
    food.updated_at = utcnow()
    nutrition = db.get(FoodNutrition, food.id)
    if nutrition:
        for key in ("energy_kcal", "protein_g", "carbohydrate_g", "fat_g", "saturated_fat_g", "fibre_g", "sugar_g", "sodium_mg"):
            if key in body.per_100g:
                setattr(nutrition, key, body.per_100g[key])
    audit(db, admin.id, "food_updated", "food", str(food.id), None)
    db.commit()
    return ok({"id": food.id})


@router.delete("/admin/foods/{food_id}")
def admin_delete_food(food_id: int, admin: User = Depends(get_admin), db: Session = Depends(get_db)):
    food = db.get(Food, food_id)
    if food is None:
        raise AppError(404, "not_found", "That food was not found.")
    food.archived_at = utcnow()
    food.deleted_at = utcnow()
    audit(db, admin.id, "food_archived", "food", str(food.id), None)
    db.commit()
    return ok({"archived": True})


@router.post("/admin/foods/{food_id}/verify")
def verify_food(food_id: int, admin: User = Depends(get_admin), db: Session = Depends(get_db)):
    food = db.get(Food, food_id)
    if food is None:
        raise AppError(404, "not_found", "That food was not found.")
    food.verification_status = "verified"
    food.last_reviewed_at = utcnow()
    audit(db, admin.id, "food_verified", "food", str(food.id), None)
    db.commit()
    return ok({"id": food.id, "verification_status": "verified"})


@router.get("/admin/foods/coverage")
def admin_coverage(admin: User = Depends(get_admin), db: Session = Depends(get_db)):
    foods = db.scalars(select(Food).where(Food.deleted_at.is_(None))).all()
    return ok({
        "total": len(foods),
        "verified": sum(1 for food in foods if food.verification_status == "verified"),
        "recipe_estimate": sum(1 for food in foods if food.data_origin == "recipe_estimate"),
        "imported_usda": sum(1 for food in foods if food.data_origin == "imported_usda"),
        "compiled_reference": sum(1 for food in foods if food.data_origin == "compiled_reference"),
        "awaiting_verification": sum(1 for food in foods if food.verification_status != "verified"),
    })


@router.post("/admin/foods/import")
async def import_foods(file: UploadFile = File(...), admin: User = Depends(get_admin), db: Session = Depends(get_db)):
    import csv
    import io
    import json
    raw = (await file.read()).decode("utf-8-sig")
    records = json.loads(raw) if file.filename and file.filename.endswith(".json") else list(csv.DictReader(io.StringIO(raw)))
    created = 0
    from seeds.catalog import slugify
    for record in records:
        name = record.get("name_en") or record.get("name")
        if not name or record.get("energy_kcal") in (None, ""):
            continue
        slug = slugify(str(record.get("slug") or name))
        if db.scalar(select(Food).where(Food.slug == slug)):
            continue
        food = Food(slug=slug, name_en=name, name_ur=record.get("name_ur") or "", name_roman=record.get("name_roman") or name.lower(),
                    kind=record.get("kind") or "dish", data_origin=record.get("data_origin") or "manual", verification_status="awaiting_verification",
                    search_text=name.lower(), nutrition_note=record.get("nutrition_note") or "Imported by an administrator.")
        db.add(food)
        db.flush()
        def maybe(field):
            value = record.get(field)
            return None if value in (None, "") else float(value)
        db.add(FoodNutrition(food_id=food.id, energy_kcal=maybe("energy_kcal"), protein_g=maybe("protein_g"), carbohydrate_g=maybe("carbohydrate_g"), fat_g=maybe("fat_g"), fibre_g=maybe("fibre_g"), sugar_g=maybe("sugar_g"), sodium_mg=maybe("sodium_mg")))
        created += 1
    audit(db, admin.id, "food_import", "food", None, {"created": created})
    db.commit()
    return ok({"created": created})


class ConsultantIn(BaseModel):
    display_name: str
    qualifications: str | None = None
    bio: str | None = None
    specialization: str | None = None
    experience_years: int | None = None
    languages: list[str] = []
    verification_status: str = "unverified"
    fee_disclaimer: str | None = None


class ServiceIn(BaseModel):
    service_type: str
    title: str
    duration_min: int = 45
    price_amount: float
    currency: str = "PKR"
    platform_fee_amount: float = 0
    tax_amount: float = 0


@router.post("/admin/consultants", status_code=201)
def admin_consultant(body: ConsultantIn, admin: User = Depends(get_admin), db: Session = Depends(get_db)):
    if body.verification_status not in {"unverified", "pending", "verified"}:
        raise AppError(422, "validation_error", "Verification status is not recognised.")
    row = ConsultantProfile(display_name=body.display_name, qualifications=body.qualifications, bio=body.bio, specialization=body.specialization,
                            experience_years=body.experience_years, languages=body.languages, verification_status=body.verification_status,
                            fee_disclaimer=body.fee_disclaimer or "Fees are entered by an administrator. FitDesi does not invent market prices.")
    db.add(row)
    db.commit()
    return ok({"id": row.id, "verification_status": row.verification_status})


@router.put("/admin/consultants/{consultant_id}")
def admin_update_consultant(consultant_id: int, body: ConsultantIn, admin: User = Depends(get_admin), db: Session = Depends(get_db)):
    row = db.get(ConsultantProfile, consultant_id)
    if row is None:
        raise AppError(404, "not_found", "That consultant was not found.")
    row.display_name = body.display_name
    row.verification_status = body.verification_status
    row.qualifications = body.qualifications
    row.fee_disclaimer = body.fee_disclaimer
    audit(db, admin.id, "consultant_updated", "consultant", str(row.id), {"verification_status": row.verification_status})
    db.commit()
    return ok({"id": row.id})


@router.put("/admin/consultant-services/{service_id}")
def admin_service(service_id: int, body: ServiceIn, admin: User = Depends(get_admin), db: Session = Depends(get_db)):
    row = db.get(ConsultantService, service_id)
    if row is None:
        raise AppError(404, "not_found", "That service was not found.")
    row.price_amount = body.price_amount
    row.duration_min = body.duration_min
    row.platform_fee_amount = body.platform_fee_amount
    row.tax_amount = body.tax_amount
    row.price_source = "admin_configured"
    row.price_updated_at = utcnow()
    audit(db, admin.id, "fee_updated", "consultant_service", str(row.id), {"price_amount": body.price_amount})
    db.commit()
    return ok({"id": row.id, "price_amount": row.price_amount, "currency": row.currency})


@router.post("/admin/consultant-services", status_code=201)
def admin_add_service(consultant_id: int, body: ServiceIn, admin: User = Depends(get_admin), db: Session = Depends(get_db)):
    if db.get(ConsultantProfile, consultant_id) is None:
        raise AppError(404, "not_found", "That consultant was not found.")
    row = ConsultantService(consultant_id=consultant_id, service_type=body.service_type, title=body.title, duration_min=body.duration_min,
                            price_amount=body.price_amount, currency=body.currency, platform_fee_amount=body.platform_fee_amount,
                            tax_amount=body.tax_amount, price_source="admin_configured")
    db.add(row)
    db.commit()
    return ok({"id": row.id})


@router.get("/health")
def health():
    return ok({"status": "ok", "app": "FitDesi"})
