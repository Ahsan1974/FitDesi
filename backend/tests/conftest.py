import pytest
from fastapi.testclient import TestClient

from app.core.security import hash_password
from app.main import app
from app.models import Food, FoodCategory, FoodNutrition, RegionalCuisine, User
from tests.db import Base, TestingSession, bind_app, engine

bind_app(app)


@pytest.fixture()
def client():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    with TestingSession() as db:
        category = FoodCategory(slug="chicken", name_en="Chicken", name_ur="چکن")
        cuisine = RegionalCuisine(slug="pakistani", name_en="Pakistani", name_ur="پاکستانی")
        db.add_all([category, cuisine])
        db.flush()
        samples = [
            ("chicken-karahi", "Chicken Karahi", False, 180, 16, 6, 10, 2),
            ("roti", "Roti", True, 280, 8, 48, 4, 4),
            ("daal-masoor", "Daal masoor", True, 120, 7, 16, 3, 4),
            ("boiled-egg", "Boiled egg", False, 155, 13, 1, 11, 0),
            ("chicken-biryani", "Chicken Biryani", False, 190, 9, 22, 7, 1),
            ("sweet-lassi", "Sweet lassi", True, 70, 3, 10, 2, 0),
            ("aloo-sabzi", "Aloo sabzi", True, 90, 2, 12, 4, 2),
        ]
        for slug, name, veg, kcal, protein, carb, fat, fibre in samples:
            food = Food(slug=slug, name_en=name, name_roman=name.lower(), search_text=name.lower(), category_id=category.id,
                        cuisine_id=cuisine.id, kind="dish", data_origin="recipe_estimate", is_vegetarian=veg, is_vegan=False)
            db.add(food)
            db.flush()
            db.add(FoodNutrition(food_id=food.id, energy_kcal=kcal, protein_g=protein, carbohydrate_g=carb, fat_g=fat, fibre_g=fibre, sugar_g=None, sodium_mg=None))
        db.add(User(email="admin@example.com", password_hash=hash_password("admin-password"), full_name="Admin", role="admin", email_verified=True, is_active=True))
        db.commit()
    return TestClient(app)
