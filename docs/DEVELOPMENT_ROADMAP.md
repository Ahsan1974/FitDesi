# Development roadmap

Shipped in this workspace: auth, onboarding, dashboard from live records, the seeded catalogue, diary with offline outbox, recipe calculation, feasibility and 7-day plans, manual and health-platform steps, workouts, weight, water, sleep, grocery lists, weekly report CSV/PDF, AI chat and scan adapters, consultant directory and unpaid booking, and the admin page.

Still to do before calling a feature finished on hardware:

- Confirm Health Connect and HealthKit on a phone, including a locked-screen step count if background collection is required.
- Add a release keystore and a real payment provider. Until then bookings stay `not_configured`.
- Import a Pakistan Food Composition Table extract and verify foods in the admin UI. Verified count starts at zero on purpose.
- Add more sourced recipes for Gilgit-Baltistan, Multan, Khyber Pakhtunkhwa, Kashmir and Balochistan. Do not fill those gaps with invented calories.
- Progress-photo upload and deletion. The table exists; the route does not.
- Saved-meal editor and `PUT /recipes/{id}`.
- Push notification delivery and quiet hours checked on a device. Preference fields are already stored.
- Move the rate limit to a shared store if the API runs as more than one process.
