# PawPaw Pet Shop · Full-stack MVP

Vietnamese pet shop based on the attached storefront and admin screen designs.

## FE · BE · Database

```text
frontend/                 HTML/CSS/JS: shop, account, booking, support, admin UI
backend/main.py           FastAPI routes and authentication/authorization
backend/services/         Domain/application services (transactional checkout)
backend/database.py       SQLite connection, seed data, database bootstrap
backend/security.py       Password/session/CSRF helpers
db/migrations/            Versioned SQL schema
contracts/openapi.yaml    API contract
docs/                     Audit, backend design, data model, AWS handoff
deploy/aws/               Lightsail run/backup instructions
```

## Local run

Requires Python 3.12+ and the packages in `requirements.txt`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`. Local admin: `admin@pawpaw.local` / `ChangeMe-OnlyForLocal`. Replace these values before any shared deployment. API docs: `/api/docs` in development.

## Tests

```bash
python -m unittest discover -s tests -v
```

## AWS

See [deploy/aws/deploy-lightsail.md](deploy/aws/deploy-lightsail.md). Single Lightsail VM + FastAPI + SQLite volume + Caddy is the low-cost pilot architecture. Real payment providers, shipping, email and domain credentials are intentionally not guessed. This workspace did not have AWS CLI or account credentials, so resources were not created.
