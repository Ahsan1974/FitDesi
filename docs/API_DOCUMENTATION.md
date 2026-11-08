# API

Base path: `/api/v1`. Successful JSON is `{"data": ...}`. Errors are `{"error": {"code", "message", "details"}}`. Interactive schemas are at `/docs` when the server is running.

Authentication: `Authorization: Bearer <access>`. Refresh with `POST /auth/refresh`. A reused refresh token revokes the user's outstanding refresh tokens.

| Area | Methods and paths |
| --- | --- |
| Auth | `POST /auth/register`, `/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/forgot-password`, `/auth/reset-password`, `/auth/verify-email` |
| Profile | `GET/PUT /users/me`, `GET/PUT /users/me/preferences`, `PUT /users/me/onboarding`, `DELETE /users/me`, `GET /users/me/export` |
| Foods | `GET /foods`, `/foods/search`, `/foods/categories`, `/foods/cuisines`, `/foods/{id}`, `/foods/favourites`; `POST /foods/favourites?food_id=`; `POST /foods/{id}/portion` |
| Diary | `GET/POST /food-diary`, `PUT/DELETE /food-diary/{id}`, `POST /food-diary/copy-day` |
| Recipes | `POST /recipes/calculate`, `GET/POST /recipes`, `GET/DELETE /recipes/{id}` |
| Summaries | `GET /nutrition/daily-summary`, `/nutrition/weekly-summary`, `/nutrition/monthly-summary` |
| Plans | `POST /plans/feasibility-check`, `POST /plans/generate`, `GET /plans/current`, `GET /plans/history`, `GET /plans/{id}`, `POST /plans/{id}/regenerate`, `POST /plans/{id}/replace-item` |
| Activity | `GET /activity/steps`, `POST /activity/steps/sync`, `GET /activity/history`, `GET/POST /activity/workouts`, `PUT /activity/workouts/{id}` |
| Body | `GET /weight/history`, `POST /weight`, `DELETE /weight/{id}`, `POST /weight/measurements`, `GET/POST /water`, `DELETE /water/{id}`, `GET/POST /sleep` |
| AI | `POST /ai/food-recognition`, `DELETE /ai/scans/{id}`, `POST /ai/consultant/chat` |
| Planning extras | `GET/POST /meal-plans`, `GET /meal-plans/{id}`, `GET/POST /grocery-lists`, `PUT /grocery-lists/{id}` |
| Consultants | `GET /consultants`, `GET /consultants/{id}`, `GET /consultants/{id}/availability`, `POST /consultant-bookings`, `GET /consultant-bookings`, `POST /consultant-bookings/{id}/cancel` |
| Reports | `GET /reports/weekly`, `GET /reports/monthly`, `GET /reports/export?fmt=csv` or `fmt=pdf` |
| Home | `GET /dashboard/today`, `GET /exercises`, `GET /notifications`, `GET /health` |
| Admin | `POST/PUT/DELETE /admin/foods`, `POST /admin/foods/import`, `POST /admin/foods/{id}/verify`, `GET /admin/foods/coverage`, `POST/PUT /admin/consultants`, `POST /admin/consultant-services?consultant_id=`, `PUT /admin/consultant-services/{id}` |

Diary, water, weight, workout and step writes accept `client_mutation_id`. Sending the same id again returns the original row.

`PUT /recipes/{id}` and a full saved-meal editor are not exposed yet. Meal plans created by the generator are read through `/plans/current`.
