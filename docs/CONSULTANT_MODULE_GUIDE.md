# Consultant module

Two services stay separate.

The in-app consultant is the AI chat endpoint. It has a daily quota and does not bill anyone. Subscriptions are stored as records only. `PAYMENT_PROVIDER=none` until a merchant account exists.

Human consultations are directory records:

- An administrator creates a profile with `POST /admin/consultants`. New profiles stay `unverified` unless the administrator explicitly sets another status after checking credentials.
- Fees are created with `POST /admin/consultant-services?consultant_id=`. The amount, currency, source (`admin_configured`) and update time are stored. The app shows that amount. It does not look up a market rate.
- The seeded demo consultant, if `SEED_DEMO=true`, is named as a development sample, is unverified, and has a fee of 0. That zero is a sample configuration, not a price.
- `POST /consultant-bookings` creates a requested booking and a payment row with status `not_configured`. No charge is made. Cancel with `POST /consultant-bookings/{id}/cancel`.
- Reviews are a table for later use. The seed does not invent ratings.
