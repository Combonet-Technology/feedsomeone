# AGENTS.md

Workspace instructions for AI coding agents working in this repository.

## Owner Context

You are collaborating with Oluwafemi Olanrewaju Ebenezer, a senior software engineer and AI systems builder with an entrepreneurial mindset.

Default collaboration style:

- Be concise, technically precise, structured, and actionable.
- Think in systems: problem, architecture, interfaces, implementation.
- Prefer practical engineering guidance over vague or motivational language.
- Consider technical feasibility, scalability, automation potential, product value, and long-term maintainability.
- When implementation details are open, choose maintainable architecture over quick hacks.

Engineering principles to respect:

- SOLID
- DRY
- Dependency Inversion
- Separation of Concerns
- Modular architecture
- Replaceable infrastructure dependencies
- Clear abstractions and explicit interfaces

## Project Context

This repository is the `feedsomeone` codebase, an NGO/foundation web application.

Current stack:

- Python 3.10
- Django 3.2
- Docker Compose is the primary full local app runtime
- `uv` is used for quick local checks, test runs, and debugger-style workflows
- Poetry and Pipfile dependency files are legacy metadata and are not the preferred runtime path
- Main Django settings live under `config/settings/`
- Django apps include `mainsite`, `user`, `blog`, `contact`, `events`, `payment`, `errors`, and `utils`
- Static and template assets live in `static/`, `assets/`, `media/`, and `templates/`

Treat this directory as the project workspace root:

```text
C:\Users\HP\PycharmProjects\feedsomeone\feedsomeone
```

## Operating Rules

- Read the existing code before changing behavior.
- Use Graphify as the first repository-context step for every coding task:
  - From the repository root, check `graphify-out/graph.json` and run a focused
    `graphify query "..."` for the task when the index exists.
  - If the index does not exist, build it with `graphify .` before inspecting
    application code in depth.
  - Treat Graphify results as navigation context, then verify important details
    against the source files before editing.
- Preserve current project structure unless a change clearly improves modularity or maintainability.
- Do not introduce unrelated refactors while fixing a focused issue.
- Do not overwrite local changes you did not make.
- Do not commit secrets, `.env` values, database dumps, private keys, generated coverage files, or local IDE state.
- Be careful with files such as `.env`, `db.sqlite3`, `cert.key`, `cert.crt`, `media/`, `htmlcov/`, and `test-reports/`.
- Prefer small, reviewable changes with clear verification steps.

## Commit, Push, and Deploy Preferences

- When Oluwafemi accepts changes on a Render-backed project, push the accepted code after verification.
- For Render-backed projects, deploy after pushing unless he explicitly asks not to deploy.
- Prefer small incremental commits grouped by fix or feature instead of one large mixed commit.
- Before committing, separate unrelated local changes from the accepted work and preserve them.
- Before deploying to Render, confirm required secret environment variables are already configured or report the missing variables clearly.
- After deployment, verify the Render deploy status and the live site where tool access allows it.

## Architecture Preferences

- Keep business rules out of views when they become non-trivial.
- Prefer service/helper modules for reusable domain workflows.
- Keep models focused on persistence and core domain behavior.
- Keep forms responsible for validation and input shaping.
- Keep templates presentation-oriented.
- Isolate payment, email, storage, and third-party integrations behind thin internal interfaces where practical.
- Avoid duplicating query logic across views; centralize when reuse or complexity grows.
- Favor explicit names over clever abstractions.

## Development Commands

Use the existing project tooling where possible. Read `RUNBOOK.md` before
starting or changing runtime setup. For this repo, prefer Docker Compose when
running the full app because it already defines the web service and Postgres
dependency. Use `uv` for quick local commands and debugger workflows.

Docker full-app commands:

```powershell
docker compose ps
docker compose up -d postgres web
docker compose logs --tail 80 web
```

Quick local `uv` commands:

```powershell
$env:UV_CACHE_DIR = (Resolve-Path '.uv-cache').Path
uv run --no-project --python 3.10 python manage.py check --settings=config.settings.test
uv run --no-project --python 3.10 python manage.py test contact --settings=config.settings.test
```

Use `--no-project` because this repository's `pyproject.toml` is Poetry-style
and does not contain a uv/PEP 621 `[project]` table. Use the repo-local
`.uv-cache` because the machine-level uv cache may be unavailable.

When running Django from the Windows host against the Compose database, use
`POSTGRES_HOST=127.0.0.1` and `POSTGRES_PORT=5444`. Inside Compose, use the
service hostname `postgres` and port `5432`.

The default settings module is resolved in `manage.py` from the `SETTINGS` environment variable, falling back to:

```text
config.settings.local
```

For detailed run/test/debug workflow, see `RUNBOOK.md`.

## Testing and Verification

- Run targeted tests for the changed app when possible.
- Run `python manage.py check` after settings, model, URL, view, or template changes.
- For payment, auth, donation, user, or data migration work, prefer explicit tests and manual verification notes.
- If tests cannot be run because dependencies, network, secrets, or local services are unavailable, state that clearly.

## UI Verification Hook

For every template, CSS, or frontend behavior change:

1. Run `powershell -ExecutionPolicy Bypass -File scripts\verify_ui.ps1 -Url http://127.0.0.1:8000/<route>/`.
2. Inspect both generated screenshots with the visual inspection tool at desktop and mobile sizes.
3. Fix any clipping, overflow, alignment, or responsive regressions found.
4. Do not report a UI fix as complete based only on an HTTP 200 response or Django checks.

The script is the project UI-verification hook; its screenshots are written to the system temporary directory by default.

## Security Notes

- Treat this as a production-facing web application.
- Avoid leaking secrets from `.env`, settings files, database files, or logs.
- Validate and sanitize user input at forms, serializers, and view boundaries.
- Be cautious with authentication, authorization, password reset, email confirmation, donation/payment, file upload, and admin flows.
- Do not weaken CSRF, authentication, allowed hosts, storage, email, payment, or SSL behavior without explicit approval.

## Response Style

- Lead with the concrete result or finding.
- Include file paths and commands when relevant.
- Explain trade-offs for architectural decisions.
- Keep final responses brief unless the task requires deeper analysis.
