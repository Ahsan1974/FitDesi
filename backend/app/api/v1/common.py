from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.core.security import utcnow
from app.models import AuditLog, Food, FoodAlias, FoodNutrition, FoodServing, User
from app.services.calc import NUTRIENT_FIELDS

_BUCKETS: dict[str, list[float]] = {}


def ok(data, meta: dict | None = None) -> dict:
    body = {"data": data}
    if meta:
        body["meta"] = meta
    return body


def num(value):
    return None if value is None else float(value)


def nutrition_out(row: FoodNutrition | None) -> dict:
    if row is None:
        return {field: None for field in NUTRIENT_FIELDS}
    return {field: num(getattr(row, field)) for field in NUTRIENT_FIELDS}


def food_out(food: Food, nutrition: FoodNutrition | None = None, servings: list[FoodServing] | None = None, aliases: list[str] | None = None) -> dict:
    return {
        "id": food.id,
        "slug": food.slug,
        "name_en": food.name_en,
        "name_ur": food.name_ur,
        "name_roman": food.name_roman,
        "category_id": food.category_id,
        "subcategory": food.subcategory,
        "cuisine_id": food.cuisine_id,
        "kind": food.kind,
        "preparation": food.preparation,
        "is_vegetarian": food.is_vegetarian,
        "is_vegan": food.is_vegan,
        "default_serving_label": food.default_serving_label,
        "default_serving_g": food.default_serving_g,
        "image_url": food.image_url,
        "data_origin": food.data_origin,
        "verification_status": food.verification_status,
        "data_confidence": food.data_confidence,
        "nutrition_note": food.nutrition_note,
        "per_100g": nutrition_out(nutrition),
        "servings": [
            {"id": serving.id, "label": serving.label, "grams": serving.grams, "unit_kind": serving.unit_kind, "source_note": serving.source_note}
            for serving in servings or []
        ],
        "aliases": aliases or [],
    }


def load_food_bundle(db: Session, food: Food) -> dict:
    nutrition = db.get(FoodNutrition, food.id)
    servings = db.scalars(select(FoodServing).where(FoodServing.food_id == food.id)).all()
    aliases = db.scalars(select(FoodAlias.alias).where(FoodAlias.food_id == food.id)).all()
    return food_out(food, nutrition, list(servings), list(aliases))


def user_zone(user: User) -> ZoneInfo:
    try:
        return ZoneInfo(user.timezone or "Asia/Karachi")
    except Exception:
        return ZoneInfo("Asia/Karachi")


def day_window(user: User, day: date) -> tuple[datetime, datetime]:
    zone = user_zone(user)
    start = datetime.combine(day, time.min, tzinfo=zone).astimezone(timezone.utc).replace(tzinfo=None)
    return start, start + timedelta(days=1)


def parse_day(value: str | None, user: User) -> date:
    if not value:
        return datetime.now(user_zone(user)).date()
    return date.fromisoformat(value)


def audit(db: Session, actor_id: int | None, action: str, entity: str, entity_id: str | None, data: dict | None = None) -> None:
    db.add(AuditLog(actor_id=actor_id, action=action, entity=entity, entity_id=entity_id, data_json=data))


def rate_limit(request: Request, scope: str, limit: int = 12) -> None:
    now = utcnow().timestamp()
    key = f"{scope}:{request.client.host if request.client else 'local'}"
    hits = [item for item in _BUCKETS.get(key, []) if now - item < 60]
    if len(hits) >= limit:
        raise AppError(429, "rate_limited", "Too many attempts. Wait a minute and try again.")
    hits.append(now)
    _BUCKETS[key] = hits


def find_mutation(db: Session, model, user_id: int, mutation_id: str | None):
    if not mutation_id:
        return None
    return db.scalar(select(model).where(model.user_id == user_id, model.client_mutation_id == mutation_id))
