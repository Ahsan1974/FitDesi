# AI integration

Configuration is in `.env`.

- `OPENAI_API_KEY` empty: chat uses `backend/app/services/ai_service.py` fallback. It reads the day's diary summary, the active plan, weight trend and selected steps that the request already loaded. It does not invent meals the user did not log.
- With a key, chat is sent to `OPENAI_BASE_URL` using `OPENAI_CHAT_MODEL`. If that call fails, the same fallback is used and the reply is marked as a fallback.
- Vision uses `OPENAI_VISION_MODEL`. Without a key, `POST /ai/food-recognition` stores the resized JPEG, returns status `provider_not_configured`, and returns no predicted foods. Nothing is written to the diary until the user confirms a matched food.
- Photos are resized to at most 1280 px and saved under `backend/storage/scans`. `DELETE /ai/scans/{id}` removes the file and soft-deletes the row.
- The daily chat quota defaults to 30 messages and can be changed with the `ai_daily_quota` application setting. No fee is charged.
- The assistant is instructed, in the fallback and by the product rules, not to diagnose or to prescribe an extreme diet.

Set `consent_ai` during onboarding before relying on record-aware replies. The chat endpoint still answers from stored records when the user asks; the consent flag is what the onboarding screen records.
