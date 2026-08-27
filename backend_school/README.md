# School Backend

Backend for the school platform built with Django + Django REST Framework.

## Stack
- Django 5
- Django REST Framework
- Celery
- Redis
- django-celery-beat
- django-celery-results
- SQLite (local dev default)

## Main Features
- Session auth endpoints (`register`, `login`, `logout`, `me`)
- Teachers list and availability endpoints
- Trial lesson request flow:
  - create
  - list student requests
  - student cancel
  - teacher list/update
- Free consultation request endpoint
- Forgot password flow:
  - request reset email
  - confirm reset with `uid` + `token`
- Email notifications and status update emails

## Requirements
- Python 3.11+
- pip
- Redis (for Celery in non-test runs)

## Environment files
- Local dev: `.env`
- Docker: `.env.docker`

Key variables used:
- `DEBUG`
- `SECRET_KEY`
- `FRONT_SITE_ORIGIN`
- `SITE_ORIGIN`
- `EMAIL_HOST`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`
- `CELERY_BROKER_URL`

## Local setup (without Docker)
```bash
python -m venv ..\venv
..\venv\Scripts\activate
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

Backend URL: http://127.0.0.1:8000

## Run tests
```bash
python manage.py test api -v 1
```

Notes:
- Test mode is configured to avoid sending real emails.
- Celery runs in eager/in-memory mode during tests.

## Docker setup (recommended for full dev stack)
From `school_back/`:
```bash
docker compose up --build
```

Services:
- `web` (Django)
- `celery_worker`
- `celery_beat`
- `redis`

## API base
All backend routes are under:
- `/api/`

Core endpoints are defined in `api/urls.py`.

## Project structure
```text
backend_school/
  api/
    models.py
    serializers.py
    views.py
    services.py
    tasks.py
    signals.py
    tests.py
  backend_school/
    settings.py
    urls.py
```
