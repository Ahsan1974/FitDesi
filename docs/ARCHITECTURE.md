# Architecture

FitDesi is three processes that share one API.

- `mobile/` is a Flutter app. Riverpod holds the session. GoRouter sends signed-out users to the welcome screen and signed-in users through onboarding into a five-tab shell. Dio talks to `/api/v1`. sqflite keeps a food cache and an outbox for diary, water, weight, sleep, steps and workouts.
- `backend/` is a FastAPI application. Routes validate input, services in `app/services/calc.py` and `app/services/planning.py` do the nutrition and plan math, and SQLAlchemy models in `app/models/entities.py` map the database.
- `admin/index.html` is a static page mounted at `/admin`. It calls the same API with an administrator token.

The database defaults to SQLite (`backend/fitdesi.db`) so the project runs without Docker. `DATABASE_URL` can point at PostgreSQL. Alembic's initial revision is `backend/alembic/versions/6698bba64737_initial_schema.py`.

Critical numbers are not produced by a language model. The AI adapter only explains records the services already computed, and it refuses to invent a meal from a photo when no vision key is configured.

User rows are filtered by the authenticated user id. Administrator routes use `get_admin`. Timestamps are stored as naive UTC. The API converts a user's day, default `Asia/Karachi`, into a UTC window before querying logs.
