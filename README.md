# KAYI Haustechnik OS

Production-grade operations platform for KAYI Haustechnik: customers, properties, projects, field work, documents, time tracking, catalog, offers, invoices, payments, email, reporting, AI assistance and guarded portal automation.

## Product scope

The application is intentionally broader than an MVP. The delivered codebase includes:

- role-based login for administration, office, project management, accounting, technicians and read-only users
- customer and property records
- complete project records with team, tasks, appointments, files, materials, time entries, offers and invoices
- responsive office interface plus installable employee PWA
- mobile time start/stop with optional geolocation and break tracking
- service/material catalog and CSV/XLSX imports
- ToolTime customer/project import
- offer and invoice builders with line items, tax, totals and PDF generation
- conversion of accepted offers into invoices
- partial/full payments and automatic invoice status updates
- expenses and project contribution reporting
- GMX inbox synchronization and SMTP sending
- mandatory human approval before sending email
- OpenAI Responses API integration from the backend only
- structured AI extraction for work-report-to-line-item suggestions
- deterministic catalog fallback when AI is unavailable
- mandatory human review before AI suggestions become a draft
- B&O Playwright adapter with configurable selectors and an enforced no-auto-submit gate
- file size, extension and magic-byte validation, SHA-256 tracking and bounded PDF extraction
- REST API, global search, notifications and audit logging
- PostgreSQL, Redis, Celery worker and Celery Beat
- Docker Compose deployment with Caddy HTTPS, health checks and pre-deploy database backups
- GitHub Actions for migrations, CI and production deployment

## Architecture

- Django 5.2 LTS
- Django REST Framework
- PostgreSQL 17
- Redis 8
- Celery 5.6
- Caddy 2
- vanilla CSS and JavaScript PWA
- OpenAI Responses API
- ReportLab PDF generation
- Playwright Chromium adapter

The server-rendered UI and REST API share the same domain model and permission rules. No API key is exposed to the browser.

## Local development

```bash
cp .env.example .env
# For a lightweight local run, remove POSTGRES_HOST from .env to use SQLite.
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py makemigrations erp
python manage.py migrate
python manage.py bootstrap_admin --credentials-file ./runtime/admin_credentials.txt
python manage.py runserver
```

Optional demo data:

```bash
python manage.py seed_demo
```

## Docker

```bash
cp .env.example .env
# Set secure values in .env
docker compose up -d --build
docker compose run --rm web python manage.py migrate
docker compose run --rm web python manage.py bootstrap_admin
```

## Production deployment

Pushes to `main` trigger `.github/workflows/deploy.yml`. Required repository secrets:

- `HOST`: server address
- `PASS`: root SSH password
- `OPENAIAPIKEY`: OpenAI API key

The workflow installs Docker when necessary, clones or refreshes `/opt/kayi`, generates persistent application/database secrets, creates a compressed pre-deploy PostgreSQL backup, builds containers, runs migrations, bootstraps the first administrator and performs a health check.

Initial administrator credentials are created only when no user exists and stored on the server at:

```text
/var/lib/docker/volumes/kayi_runtime/_data/admin_credentials.txt
```

or can be read from the running container:

```bash
docker compose -f /opt/kayi/compose.yaml exec web cat /runtime/admin_credentials.txt
```

Change the password immediately after first login.

## DNS

`kayi.smarbiz.sbs` must have an `A` record pointing to `91.107.144.64`. Until DNS is active, the service is also configured on `http://91.107.144.64`.

## Human approval rules

The following actions are deliberately never automatic:

- sending an email
- finalizing AI-generated invoice/offer positions
- submitting information to the B&O portal
- treating AI extraction as verified work performed

AI and automation jobs create reviewable drafts. An authorized human must approve them before a separate apply/send action becomes available.

## Private operational data

The repository is currently public. Customer data, supplier price lists, portal sessions, historical mail databases and raw operational archives must not be committed. Upload or import them through the authenticated application or move the repository to private before adding such files.

## Validation

CI runs migration consistency, database migration, Django checks, the test suite, Python compilation and Docker Compose validation.
