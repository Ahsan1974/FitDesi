from datetime import date, datetime, timedelta, timezone

from tests.db import TestingSession
from tests.helpers import auth


def test_register_login_and_onboarding(client):
    headers = auth(client)
    me = client.get("/api/v1/users/me", headers=headers)
    assert me.status_code == 200
    onboard = client.put("/api/v1/users/me/onboarding", headers=headers, json={
        "full_name": "Ayesha Khan",
        "date_of_birth": "1994-05-12",
        "gender": "female",
        "height_cm": 162,
        "current_weight_kg": 78,
        "target_weight_kg": 68,
        "activity_level": "lightly_active",
        "diet_type": "non_vegetarian",
        "meals_per_day": 3,
        "allergies": ["peanut"],
        "consent_health": True,
        "consent_ai": True,
        "goal_date": "2027-02-01",
    })
    assert onboard.status_code == 200
    assert onboard.json()["data"]["profile"]["onboarding_completed"] is True


def test_food_search_and_diary_math(client):
    headers = auth(client, "diary@example.com")
    found = client.get("/api/v1/foods/search", params={"q": "karahi"})
    assert found.status_code == 200, found.text
    assert found.json()["data"]["items"], found.text
    food = found.json()["data"]["items"][0]
    portion = client.post(f"/api/v1/foods/{food['id']}/portion", json={"grams": 200})
    assert portion.status_code == 200
    assert portion.json()["data"]["consumed"]["energy_kcal"] == round(food["per_100g"]["energy_kcal"] * 2, 2)
    logged = client.post("/api/v1/food-diary", headers=headers, json={
        "food_id": food["id"], "meal_type": "lunch", "grams": 200, "client_mutation_id": "same-key",
    })
    again = client.post("/api/v1/food-diary", headers=headers, json={
        "food_id": food["id"], "meal_type": "lunch", "grams": 200, "client_mutation_id": "same-key",
    })
    assert logged.json()["data"]["id"] == again.json()["data"]["id"]
    summary = client.get("/api/v1/nutrition/daily-summary", headers=headers)
    assert summary.json()["data"]["days"][0]["energy_kcal"] == logged.json()["data"]["energy_kcal"]


def test_empty_summary_is_not_zero(client):
    headers = auth(client, "empty@example.com")
    summary = client.get("/api/v1/nutrition/daily-summary", headers=headers)
    assert summary.json()["data"]["days"][0]["logged"] is False
    assert summary.json()["data"]["days"][0]["energy_kcal"] is None


def test_plan_blocks_a_minor(client):
    headers = auth(client, "minor@example.com")
    response = client.post("/api/v1/plans/generate", headers=headers, json={
        "current_weight_kg": 70, "target_weight_kg": 60, "height_cm": 165, "age": 16,
        "gender": "female", "activity_level": "sedentary", "days": 7,
    })
    assert response.status_code == 201
    assert response.json()["data"]["safety_status"] == "blocked"
    assert response.json()["data"]["meals"] == []


def test_plan_generates_meals_for_an_adult(client):
    headers = auth(client, "plan@example.com")
    response = client.post("/api/v1/plans/generate", headers=headers, json={
        "current_weight_kg": 90, "target_weight_kg": 78, "height_cm": 175, "age": 34,
        "gender": "male", "activity_level": "moderately_active",
        "goal_date": (date.today() + timedelta(days=140)).isoformat(),
        "days": 7, "meals_per_day": 3, "diet_type": "non_vegetarian",
    })
    assert response.status_code == 201, response.text
    body = response.json()["data"]
    assert body["safety_status"] in {"ok", "adjusted"}
    assert body["calorie_target"] >= 1500
    assert body["meals"]
    assert body["meals"][0]["meals"][0]["items"]


def test_weight_water_workout_and_dashboard(client):
    headers = auth(client, "track@example.com")
    client.put("/api/v1/users/me/onboarding", headers=headers, json={
        "gender": "male", "height_cm": 175, "current_weight_kg": 90, "activity_level": "sedentary", "consent_health": True,
    })
    weight = client.post("/api/v1/weight", headers=headers, json={"weight_kg": 90, "client_mutation_id": "w1"})
    assert weight.status_code == 201
    water = client.post("/api/v1/water", headers=headers, json={"amount_ml": 250, "client_mutation_id": "h1"})
    assert water.status_code == 201
    steps = client.post("/api/v1/activity/steps/sync", headers=headers, json={"day": date.today().isoformat(), "steps": 3200, "source": "manual"})
    assert steps.json()["data"]["selected"]["steps"] == 3200
    client.post("/api/v1/activity/steps/sync", headers=headers, json={"day": date.today().isoformat(), "steps": 8000, "source": "health_connect"})
    chosen = client.get("/api/v1/activity/steps", headers=headers)
    assert chosen.json()["data"]["source"] == "health_connect"
    assert chosen.json()["data"]["steps"] == 8000
    started = datetime.now(timezone.utc) - timedelta(minutes=30)
    workout = client.post("/api/v1/activity/workouts", headers=headers, json={
        "name": "Evening walk", "category": "walking", "started_at": started.isoformat(), "duration_min": 30,
    })
    assert workout.status_code == 201
    assert workout.json()["data"]["energy_is_estimate"] is True
    sleep = client.post("/api/v1/sleep", headers=headers, json={
        "sleep_start": (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat(),
        "sleep_end": datetime.now(timezone.utc).isoformat(),
        "source": "manual",
    })
    assert sleep.status_code == 201
    home = client.get("/api/v1/dashboard/today", headers=headers)
    assert home.status_code == 200
    assert home.json()["data"]["water_ml"] == 250
    assert home.json()["data"]["calories_consumed"] is None


def test_admin_forbidden_and_allowed(client):
    user = auth(client, "member@example.com")
    denied = client.get("/api/v1/admin/foods/coverage", headers=user)
    assert denied.status_code == 403
    login = client.post("/api/v1/auth/login", json={"email": "admin@example.com", "password": "admin-password"})
    assert login.status_code == 200, login.text
    admin = {"Authorization": f"Bearer {login.json()['data']['access_token']}"}
    coverage = client.get("/api/v1/admin/foods/coverage", headers=admin)
    assert coverage.status_code == 200
    assert coverage.json()["data"]["total"] >= 1


def test_consultant_booking_does_not_charge(client):
    from app.models import ConsultantProfile, ConsultantService
    with TestingSession() as db:
        consultant = ConsultantProfile(display_name="Sample", verification_status="unverified", is_demo=True,
                                       fee_disclaimer="Development sample, not a market price.")
        db.add(consultant)
        db.flush()
        service = ConsultantService(consultant_id=consultant.id, service_type="initial", title="Sample", price_amount=1500, price_source="admin_configured")
        db.add(service)
        db.commit()
        service_id = service.id
        consultant_id = consultant.id
    headers = auth(client, "book@example.com")
    start = (datetime.now(timezone.utc) + timedelta(days=2)).isoformat()
    booking = client.post("/api/v1/consultant-bookings", headers=headers, json={
        "consultant_id": consultant_id, "service_id": service_id, "start_at": start,
    })
    assert booking.status_code == 201, booking.text
    assert booking.json()["data"]["payment_status"] == "not_configured"


def test_ai_without_key_does_not_invent_a_photo(client):
    headers = auth(client, "scan@example.com")
    from io import BytesIO
    from PIL import Image
    buffer = BytesIO()
    Image.new("RGB", (40, 40), "white").save(buffer, format="JPEG")
    response = client.post("/api/v1/ai/food-recognition", headers=headers, files={"file": ("meal.jpg", buffer.getvalue(), "image/jpeg")})
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "provider_not_configured"
    assert response.json()["data"]["predictions"] == []
    chat = client.post("/api/v1/ai/consultant/chat", headers=headers, json={"message": "How many calories are in my breakfast?", "language": "en"})
    assert chat.status_code == 200
    assert "no" in chat.json()["data"]["reply"].lower() or "not" in chat.json()["data"]["reply"].lower()
