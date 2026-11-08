# Deployment

## API

1. Create a PostgreSQL database and set `DATABASE_URL=postgresql+psycopg://...` .
2. Set `SECRET_KEY` to a long random string, `DEBUG=false`, and `CORS_ORIGINS` to the real admin origin.
3. From `backend`: `alembic upgrade head`, then `python -m seeds.seed`.
4. Run `uvicorn app.main:app --host 0.0.0.0 --port 8000` behind HTTPS. One worker is enough to start. The in-memory rate limit does not span workers.
5. Put `backend/storage` on a persistent disk, or switch `STORAGE_BACKEND` once an S3-compatible bucket and keys exist. The local backend is what the scan route uses today.
6. Take database backups with `pg_dump`. SQLite deployments can copy `fitdesi.db` while the process is stopped.

## Admin

The admin page is served by the API at `/admin`. Sign in with an `admin` user. Create that user by setting `ADMIN_EMAIL` and `ADMIN_PASSWORD` before the seed, or insert one directly. Do not leave `change-me-admin` in a shared environment.

## Android release

The Gradle release build type still uses the debug signing config so a local release APK can be installed. For Play Store, create a keystore, add a `signingConfigs.release` block in `mobile/android/app/build.gradle.kts`, and build with `flutter build appbundle --release`.

## iOS release

Archive `Runner` from Xcode on macOS with a distribution certificate. HealthKit capability must be enabled on the App ID if you ship step reading.
