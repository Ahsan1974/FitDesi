# FitDesi

Pakistani-first calorie tracker, meal planner and fitness companion.

The phone app is Flutter. The API is FastAPI. Nutrition, BMR, TDEE, recipe yield and weight-loss feasibility are calculated in Python. The food catalogue ships with USDA FoodData Central SR Legacy rows plus calculated Pakistani recipe estimates. Missing nutrients stay empty. Days without a food log are missing, not zero.

## Prerequisites

- Windows 10 or 11 for the commands below. iOS builds need a Mac with Xcode.
- Python 3.11 or newer. This workspace was developed with Python 3.13.
- Flutter 3.47 is already downloaded at `.tools/flutter` (gitignored). On another machine, install Flutter from https://docs.flutter.dev/get-started/install and put `flutter` on your PATH.
- Optional: Docker, only if you want PostgreSQL instead of the local SQLite file.

## First-time setup on Windows

```powershell
cd E:\FitDesi
Copy-Item .env.example .env
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
$env:PYTHONPATH = "E:\FitDesi\backend"
.\.venv\Scripts\python -m seeds.seed
```

The seed is safe to run again. Existing food slugs are skipped.

## Run everything

From any directory:

```powershell
E:\FitDesi\run.bat
```

That opens the API and then the Flutter app. The API stays at http://127.0.0.1:8000 and the admin page at http://127.0.0.1:8000/admin. Connect an Android emulator or phone before you run it so Flutter has a device. The emulator should use server `http://10.0.2.2:8000`.

## Start the API

From `E:\FitDesi\backend`:

```powershell
.\.venv\Scripts\python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

- API: http://127.0.0.1:8000/api/v1/health
- OpenAPI: http://127.0.0.1:8000/docs
- Admin: http://127.0.0.1:8000/admin

Seeded development accounts, only when `SEED_DEMO=true` and the admin variables in `.env` are set:

- Admin: `admin@fitdesi.local` / `change-me-admin`
- Demo user: `demo@fitdesi.local` / `change-me-demo`

Change these before any shared deployment. With `DEBUG=true`, password-reset and email-verification tokens are returned by the API because SMTP is not configured.

## Start the phone app

```powershell
cd E:\FitDesi\mobile
E:\FitDesi\.tools\flutter\bin\flutter.bat pub get
E:\FitDesi\.tools\flutter\bin\flutter.bat run
```

The Android emulator reaches the API at `http://10.0.2.2:8000`. A physical phone must use your computer's LAN address, for example `http://192.168.1.20:8000`. Type that into the server field on the sign-in screen. The API process must listen on `0.0.0.0`, and Windows Firewall must allow port 8000.

## Android phone

1. Enable Developer options and USB debugging.
2. Connect the phone and accept the debugging prompt.
3. `flutter devices` should list it.
4. `flutter run` installs the debug build.
5. On the sign-in screen, set the server to the computer's LAN IP.

Release packages, from `mobile`:

```powershell
E:\FitDesi\.tools\flutter\bin\flutter.bat build apk --release
E:\FitDesi\.tools\flutter\bin\flutter.bat build appbundle --release
```

The APK is `mobile/build/app/outputs/flutter-apk/app-release.apk`. The Play bundle is under `mobile/build/app/outputs/bundle/release/`. The release build is signed with the debug key until you add a release keystore. See `docs/DEPLOYMENT_GUIDE.md`.

## iOS

On a Mac, open `mobile/ios/Runner.xcworkspace` in Xcode, set a development team, and run on a simulator or device. HealthKit usage strings are already in `Info.plist`. Step reading still has to be confirmed on a device.

## PostgreSQL

```powershell
docker compose up -d
```

Set `DATABASE_URL=postgresql+psycopg://fitdesi:fitdesi@localhost:5432/fitdesi` in `.env`, then from `backend`:

```powershell
.\.venv\Scripts\alembic upgrade head
.\.venv\Scripts\python -m seeds.seed
```

The SQLite file created by the seed command already has tables. On that file, use `alembic stamp head` instead of `upgrade` so Alembic records the revision without trying to create tables again.

## Tests

```powershell
cd E:\FitDesi\backend
$env:PYTHONPATH = "E:\FitDesi\backend"
.\.venv\Scripts\python -m pytest tests -q
cd E:\FitDesi\mobile
E:\FitDesi\.tools\flutter\bin\flutter.bat test
```

## What is not live without extra accounts

- OpenAI vision and chat need `OPENAI_API_KEY`. Without it, chat uses the diary and plan already stored, and a photo scan returns `provider_not_configured` instead of inventing foods.
- Email delivery needs SMTP settings.
- Payments stay `not_configured`. Bookings are requests, not charges.
- Health Connect and Apple Health need a real phone and the user's permission.
- Pakistan Food Composition Table files are not bundled. Import them through the admin CSV/JSON importer when you have a usable file.
