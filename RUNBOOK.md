# Feedsomeone Local Runbook

This repository is a Django 3.2 application. The full local app is Docker-first;
`uv` is used for fast local checks, tests, and debugger workflows.

## Runtime Map

- Production-like web process: `Dockerfile`, using Python 3.10 and `requirements.txt`.
- Full local app: `docker-compose.yml`, with `web` plus `postgres`.
- Fast local/test runner: `uv run --no-project --python 3.10 ...`.
- Default Django settings: `config.settings.local`, unless `SETTINGS` is set.
- Isolated test settings: `config.settings.test`, SQLite in memory, app migrations disabled.

## Docker Full App

Use this when you want the website running as a service.

```powershell
docker compose ps
docker compose up -d postgres web
docker compose logs --tail 80 web
```

Expected services:

- `feedsomeone-web` on `http://127.0.0.1:8000/`
- `feedsomeone-postgres` on host port `5444`, container port `5432`

The Compose runtime injects these important settings for the container:

- `SETTINGS=config.settings.local`
- `POSTGRES_HOST=postgres`
- `POSTGRES_PORT=5432`
- `POSTGRES_DB_USER=postgres`
- `POSTGRES_DB_PASS=postgres`

Verify:

```powershell
$ProgressPreference='SilentlyContinue'
Invoke-WebRequest -Uri 'http://127.0.0.1:8000/' -UseBasicParsing -TimeoutSec 10
```

The `web` service mounts the repo into `/code`, so Python/template edits reload
through Django's development autoreloader.

Rebuild only when dependency or image inputs change:

```powershell
docker compose build web
docker compose up -d web
```

Run Django checks/tests inside the container when you want to verify the exact
Docker environment:

```powershell
docker compose exec web python manage.py check
docker compose exec web python manage.py test contact --settings=config.settings.test
```

## Local Debugger / Quick Run With uv

Use this when you want fast checks or IDE debugger control without rebuilding
the app container.

First point uv at the repo-local cache:

```powershell
$env:UV_CACHE_DIR = (Resolve-Path '.uv-cache').Path
```

Run Python 3.10 through uv:

```powershell
uv run --no-project --python 3.10 python --version
```

Use `--no-project` because `pyproject.toml` is Poetry-style legacy metadata, not
a uv-native `[project]` file.

If dependencies are missing, create or refresh the local virtual environment
with Python 3.10:

```powershell
$env:UV_CACHE_DIR = (Resolve-Path '.uv-cache').Path
uv venv --python 3.10
uv pip install -r requirements.txt
```

Then run quick commands through uv:

```powershell
$env:UV_CACHE_DIR = (Resolve-Path '.uv-cache').Path
uv run --no-project --python 3.10 python manage.py check --settings=config.settings.test
```

## Quick Tests

Prefer the isolated test settings for feature-level tests:

```powershell
$env:UV_CACHE_DIR = (Resolve-Path '.uv-cache').Path
uv run --no-project --python 3.10 python manage.py check --settings=config.settings.test
uv run --no-project --python 3.10 python manage.py test contact --settings=config.settings.test
uv run --no-project --python 3.10 python manage.py test blog contact --settings=config.settings.test
```

`config.settings.test` uses SQLite in memory and avoids the legacy app migrations
for speed. Use it for most form/view/service tests.

Do not default to Python 3.12 for this project. The app image and `.python-version`
are Python 3.10, and some pinned dependencies can require native compilation on
newer Python versions.

## Local Django Against Docker Postgres

Use this only when you specifically need local debugger control while keeping
Postgres in Docker.

Start Postgres:

```powershell
docker compose up -d postgres
```

Use temporary env overrides so Django connects from the host to the published
Postgres port:

```powershell
$env:UV_CACHE_DIR = (Resolve-Path '.uv-cache').Path
$env:SETTINGS = 'config.settings.local'
$env:POSTGRES_HOST = '127.0.0.1'
$env:POSTGRES_PORT = '5444'
$env:POSTGRES_DB_USER = 'postgres'
$env:POSTGRES_DB_PASS = 'postgres'
uv run --no-project --python 3.10 python manage.py runserver 127.0.0.1:8001
```

Use port `8001` when Docker `web` is already publishing port `8000`.

The hostname changes depending on where Django runs:

- Inside Docker Compose: `POSTGRES_HOST=postgres`, `POSTGRES_PORT=5432`.
- On the Windows host: `POSTGRES_HOST=127.0.0.1`, `POSTGRES_PORT=5444`.

## IDE Debugger

For VS Code, PyCharm, or another debugger:

- Use the Python 3.10 interpreter from `.venv` if you created it with `uv venv`.
- Keep `docker compose up -d postgres` running if you need the real local database.
- Set the same temporary env vars shown in "Local Django Against Docker Postgres".
- Run `manage.py runserver 127.0.0.1:8001` when Docker `web` owns port `8000`.

The debugger should not invent a separate database path. It should either use
`config.settings.test` for isolated SQLite tests or connect to the Compose
Postgres instance through `127.0.0.1:5444`.

## Common Blockers

- Docker Desktop not running: `docker compose ps` fails to connect to the Docker engine.
- Port conflict: Docker `web` publishes host port `8000`; use `8001` for a local debugger process.
- uv cache issue: set `UV_CACHE_DIR` to `.uv-cache` before `uv run`.
- uv project discovery issue: use `--no-project` because this repo has Poetry-style `pyproject.toml`.
- Broken `.venv`: do not assume `.venv\Scripts\python.exe` works; use Docker or uv.
- Wrong Postgres host: use `postgres:5432` from inside Compose, but `127.0.0.1:5444` from the host.
- Dependency build failure on newer Python: use Python 3.10, matching `.python-version` and `Dockerfile`.

## Before Changing Runtime Setup

Check the existing runtime files before adding new tooling:

- `docker-compose.yml`
- `Dockerfile`
- `.python-version`
- `requirements.txt`
- `pyproject.toml`
- `config/settings/local.py`
- `config/settings/test.py`

If the goal is a quick check, use `uv`. If the goal is to run the application
like the project is deployed locally, use Docker Compose.

## Email Provider Notes

Brevo is the current email provider.

- Django app API key env var: `BREVO_API_KEY`
- Codex MCP token env var: `BREVO_MCP_TOKEN`
- Verified sender: `info@oluwafemiebenezerfoundation.org`
- Newsletter list ID: `2`

Do not confuse the Brevo MCP token with the REST API key. The MCP token is used
by Codex tooling only; Django uses the REST API key.
