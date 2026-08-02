# Render deployment

Create a Render Blueprint from this repository's `render.yaml`. It provisions
the Django service and PostgreSQL database, collects static assets, runs
migrations, starts Gunicorn, and monitors `/health/`.

Before deployment, provide every variable marked `sync: false` in Render:

- LiveKit URL, API key, and secret
- SMTP username, app password, and sender address
- ClickPesa client ID, API key, and checksum key

Keep `CLICKPESA_SANDBOX=true` until payment credentials and webhook delivery
have been tested. Switch it to `false` only for the approved production launch.

If the final frontend or API domains differ from `vikoba.cylvenda.co.tz` and
`vikoba-api.onrender.com`, update `DOMAIN`, `FRONTEND_URL`, email frontend,
CORS, and CSRF values. Never commit secrets or `.env` files.

After deployment, verify `/health/`, migrations, account activation/reset
email links, LiveKit joins, and a sandbox payment/webhook cycle.
