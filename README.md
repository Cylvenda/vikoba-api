# VICOBA Collaborative Banking & Secure Meeting API

A Django and Django REST Framework backend for a Virtual Private Meeting and VICOBA (Village Community Banking) Collaborative Banking Platform. The project features custom email-based authentication, cookie-backed JWT login flows, group management, meeting workflows, in-app notifications, transactional ledger tracking, and real-time WebRTC audio/video integration.

## Current Scope

Implemented areas:

- **Authentication & Security**: Custom email-based user model, Djoser authentication endpoints, and cookie-based JWT flow (`access` & `refresh` cookies).
- **Group Management**: Group creation, membership registration, role-based controls (Chairperson, Treasurer, Secretary, Member), and invitation flows.
- **Meeting Workflows**: Complete meeting lifecycle (schedule, start, join, leave, end), automatic attendance tracking, minutes drafting, and Action Item generation.
- **VICOBA Bookkeeping (Finance)**: Ledger system tracking Contributions (Savings), custom Loan Request Categories (amount, duration, interest), Loan Requests, Approvals, Repayments, Fine issuance/payment, and dual-entry Group Transactions.
- **Real-time WebRTC Integration**: LiveKit Room JWT token generation and Webhook verification/signature validation for active meeting events.
- **Notifications & Alerts**: In-app push notification inbox with read/unread tracking.
- **API Documentation**: OpenAPI schema auto-generation with Swagger UI.
- **Django Administration**: Comprehensive administrative panel coverage.

Known gaps:
- Automated tests are currently scaffold-level.
- Email activation requires active SMTP config.
- Settings are configured for local development.

## Tech Stack

- Python
- Django 6
- Django REST Framework
- Djoser
- SimpleJWT
- drf-spectacular (OpenAPI 3.0 / Swagger UI)
- django-cors-headers
- SQLite for local development

## Project Structure

```text
backend/
|-- manage.py
|-- requirements.txt
|-- README.md
|-- config/                  # Django project settings and root routing
|-- apps/
|   |-- accounts/            # Custom user model and authentication flows
|   |-- finance/             # VICOBA financial bookkeeping: Savings, Loans, Repayments, Fines, Transactions
|   |-- groups/              # Groups, memberships, and invitations
|   |-- meetings/            # Meetings, agenda items, attendance, minutes, action items
|   |-- notifications/       # User notifications inbox
|   |-- realtime/            # WebRTC integration and LiveKit Room token services
|-- templates/
|   |-- email/               # Activation email template(s)
|-- venv/                    # Local virtual environment if created locally
```

## Installation

1. Create and activate a virtual environment.

```bash
python -m venv venv
source venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Apply migrations.

```bash
python manage.py migrate
```

4. Create a superuser if needed.

```bash
python manage.py createsuperuser
```

5. Run the development server.

```bash
python manage.py runserver 0.0.0.0:8000
```

For LAN testing, find your machine IP with:

```bash
ip a
```

Then open `http://<your-local-ip>:8000` from another device on the same network.

## Environment Notes

The project loads variables from a local `.env` file if present.

Relevant settings include:

- `EMAIL_BACKEND`
- `EMAIL_HOST`
- `EMAIL_PORT`
- `EMAIL_USE_TLS`
- `EMAIL_TIMEOUT`
- `EMAIL_HOST_USER`
- `EMAIL_HOST_PASSWORD`
- `DEFAULT_FROM_EMAIL`
- `LIVEKIT_URL`
- `LIVEKIT_API_KEY`
- `LIVEKIT_API_SECRET`
- `LIVEKIT_TOKEN_TTL_MINUTES`
- `ALLOWED_HOSTS`
- `DEV_ALLOW_ALL_HOSTS`
- `CORS_ALLOWED_ORIGINS`
- `CSRF_TRUSTED_ORIGINS`
- `CLICKPESA_CLIENT_ID`
- `CLICKPESA_API_KEY`
- `CLICKPESA_CHECKSUM_KEY`
- `CLICKPESA_SANDBOX`

### Supabase PostgreSQL

The backend supports either a Supabase `DATABASE_URL` or separate PostgreSQL
variables. Keep these values in `.env` locally and in the hosting provider's
environment settings in production; never commit the database password.

Using the connection string copied from Supabase:

```env
USE_SQLITE=False
DATABASE_URL=postgresql://postgres:YOUR_URL_ENCODED_PASSWORD@db.htbrlgfgnhiycsasqygv.supabase.co:5432/postgres?sslmode=require
```

Alternatively, separate variables avoid URL-encoding special characters in the
password:

```env
USE_SQLITE=False
DB_NAME=postgres
DB_USER=postgres
DB_PASSWORD=YOUR_DATABASE_PASSWORD
DB_HOST=db.htbrlgfgnhiycsasqygv.supabase.co
DB_PORT=5432
DB_SSLMODE=require
```

Supabase direct connections require IPv6. If the development or deployment
network is IPv4-only, copy the Session pooler parameters from Supabase's
**Connect** dialog instead. For a serverless deployment, use the Transaction
pooler parameters.

After configuring the variables, install dependencies and create the schema:

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py check --database default
```

If these are not configured, Djoser activation emails will not work end-to-end.
If the LiveKit variables are not configured, meeting join requests will return a
service-unavailable response instead of a connection token.

### Production email (Render)

Account registration sends a Djoser activation email synchronously. Configure a
working SMTP provider in Render's **Environment** settings; do not rely on a
local `.env` file, which is not deployed. A 10-second SMTP timeout prevents a
slow mail server from holding a Gunicorn worker for its entire request timeout.

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_TIMEOUT=10
EMAIL_HOST_USER=your-sending-address@gmail.com
EMAIL_HOST_PASSWORD=your-16-character-google-app-password
DEFAULT_FROM_EMAIL=VICOBA Community Hub <your-sending-address@gmail.com>
SITE_NAME=VICOBA Community Hub
EMAIL_FRONTEND_DOMAIN=your-project.vercel.app
EMAIL_FRONTEND_PROTOCOL=https
```

For Gmail, `EMAIL_HOST_PASSWORD` must be a Google App Password, not the normal
Google account password. If SMTP remains unreachable from Render, use a
transactional provider that offers SMTP (such as Brevo, Resend, Postmark, or SendGrid)
and replace the `EMAIL_HOST`, `EMAIL_PORT`, credentials, and TLS values with
the provider's SMTP settings.

Render free web services block outbound SMTP ports. For that plan, use the
built-in Brevo HTTPS backend instead of SMTP. Create a Brevo account, verify
your sending email address, generate an API key, and set:

```env
EMAIL_BACKEND=apps.accounts.email_backend.BrevoEmailBackend
BREVO_API_KEY=xkeysib-xxxxxxxxxxxxxxxxxxxxxxxx
BREVO_EMAIL_TIMEOUT=10
BREVO_SENDER_EMAIL=your_verified_email@example.com
BREVO_SENDER_NAME=Community Hub
DEFAULT_FROM_EMAIL=Community Hub <your_verified_email@example.com>
```

Do not set Gmail SMTP variables when using this backend. Brevo's HTTPS API is
used over port 443, which is not affected by Render's SMTP-port restriction.

For development on a shared Wi-Fi or LAN:

- `DEV_ALLOW_ALL_HOSTS=True` lets Django accept requests from changing local IPs.
- If your frontend talks to Django directly from another origin, add that origin to
  `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS`.

## ClickPesa Payments And Loan Payouts

Collections and loan payouts use the ClickPesa SDK. Keep
`CLICKPESA_SANDBOX=True` while testing. Before enabling real-money payouts:

See the complete [ClickPesa Payment Gateway Guide](docs/PAYMENT_GATEWAY.md)
for architecture, API flows, wallet behavior, testing, and troubleshooting.

1. Add the production client ID, API key, and checksum key to the deployment
   environment.
2. Set `CLICKPESA_SANDBOX=False`.
3. Configure the application webhook in the ClickPesa dashboard as:
   `https://<backend-domain>/api/payments/webhook/clickpesa/`
4. Apply migrations with `python manage.py migrate`.
5. Make a small controlled collection and payout before enabling treasurers.

The loan remains approved while a payout is pending. It becomes active only
after ClickPesa reports `SUCCESS`. Failed or reversed payouts restore the
reserved group wallet funds.

## Authentication

### Djoser endpoints

Mounted under:

- `/api/auth/`

Examples include:

- `POST /api/auth/users/`
- `POST /api/auth/jwt/create/`
- `POST /api/auth/jwt/refresh/`
- `POST /api/auth/users/activation/`

### Cookie-based auth endpoints

Mounted under:

- `/api/me/auth/login/`
- `/api/me/auth/refresh/`
- `/api/me/auth/verify/`
- `/api/me/auth/logout/`
- `/api/me/auth/csrf/`
- `/api/me/auth/me/`

The project uses a custom cookie JWT flow in the `accounts` app, with cookies named:

- `access`
- `refresh`

Notes:

- `/api/me/auth/refresh/` is the primary refresh endpoint
- `/api/me/auth/csrf/` is still available as a backward-compatible alias
- `/api/me/auth/verify/` verifies the current access token

## API Surface

### Documentation

- `GET /` - Swagger UI
- `GET /api/schema/` - OpenAPI schema

### Groups

Base path:

- `/api/groups/`

Available routes include:

- `GET /api/groups/`
- `POST /api/groups/`
- `GET /api/groups/<uuid>/`
- `GET /api/groups/<uuid>/members/`
- `POST /api/groups/<group_uuid>/members/add/`
- `PATCH /api/groups/<group_uuid>/members/<membership_uuid>/verify/`
- `PATCH /api/groups/<group_uuid>/members/<membership_uuid>/activate/`
- `POST /api/groups/<group_uuid>/invitations/send/`
- `GET /api/groups/<group_uuid>/invitations/`
- `GET /api/groups/invitations/my/`
- `POST /api/groups/invitations/<invitation_uuid>/respond/`
- `POST /api/groups/<group_uuid>/invitations/<invitation_uuid>/cancel/`

### Meetings

Base path:

- `/api/meetings/`
- `/api/agenda-items/`

Router-backed endpoints include standard CRUD operations plus custom meeting actions:

- `POST /api/meetings/<id>/start/`
- `POST /api/meetings/<id>/end/`
- `POST /api/meetings/<id>/join/`
- `POST /api/meetings/<id>/leave/`
- `GET /api/meetings/<id>/participants/`
- `GET /api/meetings/<id>/attendance/`
- `GET /api/meetings/<id>/minutes/`
- `POST /api/meetings/<id>/minutes/`
- `PATCH /api/meetings/<id>/minutes/`

### Notifications

Base path:

- `/api/notifications/`

Routes:

- `GET /api/notifications/`
- PATCH /api/notifications/<notification_uuid>/read/

### Finance (VICOBA)

Base path:

- `/api/finance/`

Routes:

- `POST /api/finance/contributions/create/` - Record group membership contributions (Savings)
- `POST /api/finance/loans/request/` - Formulate and submit loan requests

### Real-time WebRTC (LiveKit)

Base path:

- `/api/realtime/`

Routes:

- `POST /api/realtime/livekit/` - LiveKit webhook receiver (updates participant states, session durations)
- `POST /api/realtime/meetings/<uuid:uuid>/token/` - Request safe token access to a specific ongoing virtual meeting room

## Running Checks

Basic Django project validation:

```bash
python manage.py check
```

Run tests:

```bash
python manage.py test
```

Note: test modules exist, but they are currently scaffold-level and do not provide meaningful coverage yet.

## Development Status

Current development assumptions:

- SQLite is used locally through `db.sqlite3`
- CSRF and auth cookie settings are configured for local development
- Trusted frontend origins currently target local Vite defaults

Before production use, review at minimum:

- `SECRET_KEY`
- `DEBUG`
- `ALLOWED_HOSTS`
- auth cookie security flags
- CSRF trusted origins
- database configuration
- frontend domain and CORS environment variables
- email backend configuration

## License

This project is licensed under the MIT License.
