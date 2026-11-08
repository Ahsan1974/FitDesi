# Troubleshooting

**The phone cannot reach the API.** The emulator uses `http://10.0.2.2:8000`. A real phone uses the computer's LAN IP and the API must be started with `--host 0.0.0.0`. Windows Firewall has to allow inbound TCP 8000.

**Sign-in says the email is invalid.** Use a normal domain such as `example.com`. The validator rejects special-use domains such as `.test` and `.local` for new registration. The seeded admin address `admin@fitdesi.local` is inserted directly and can still log in.

**`alembic upgrade` fails because tables exist.** The seed used `create_all` on SQLite. Run `alembic stamp head` on that database. Use `upgrade head` on an empty PostgreSQL database.

**Food search is empty.** Run `python -m seeds.seed` from `backend`. Confirm `GET /api/v1/foods/search?q=karahi` returns recipe rows.

**A photo scan says the provider is not configured.** That is the expected result without `OPENAI_API_KEY`. Search for the food and log it manually. The scan must not invent a dish.

**Two step counts appeared and the total looks doubled.** The dashboard uses the selected source only. Health platform data outranks a manual entry for the same day. Refresh the home screen after a sync.

**Pytest cannot import `app`.** Set `PYTHONPATH` to `E:\FitDesi\backend` or run pytest from that directory.

**Flutter is not recognised.** The SDK in this workspace is `E:\FitDesi\.tools\flutter\bin\flutter.bat`. Add that `bin` directory to PATH, or call the batch file directly.
