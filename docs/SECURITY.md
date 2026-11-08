# Security

- Passwords are hashed with bcrypt. Access tokens are HS256 JWTs lasting 30 minutes. Refresh tokens are random, stored as SHA-256 hashes, rotated on use, and revoked as a family if a used token is presented again.
- `.env` is gitignored. `.env.example` contains placeholders only. The Flutter app does not embed API keys. OpenAI, SMTP and payment secrets stay on the server.
- Routes that read or write a person's logs require that person's token. Admin routes require `role=admin`.
- Account deletion anonymises the email, deactivates the user and revokes refresh tokens. `GET /users/me/export` returns profile, food logs and weights.
- Uploads are limited to 5 MB and to JPEG, PNG or WebP. Images are re-encoded to JPEG before they are stored.
- Login, registration and password reset are rate limited in memory per process. Put a shared limiter in front of the API if you run more than one worker.
- Serve the API over HTTPS in production and set `DEBUG=false` so reset tokens are not returned in JSON. Configure SMTP before relying on email.
- Audit rows record food verification, food edits and consultant fee changes.
