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

- For any substantial feature, migration, cross-module change, or large refactor, stop at a local acceptance checkpoint before release. The required sequence is: implement locally, apply local migrations, rebuild the relevant Docker image when image or dependency inputs changed, run targeted checks/tests, present the locally verified result to Oluwafemi, and wait for his explicit approval before committing, pushing, or deploying.
- Never infer release approval from the original implementation request, prior deployment habits, or a successful local test. Approval to build is not approval to commit, push, or deploy.
- After presenting the local acceptance checkpoint, treat commit, push, and production deployment as a separate release phase that begins only when Oluwafemi expressly authorises it.
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

- Use `config.settings.test` with the existing PostgreSQL runtime for backend
  tests. Django uses a separate test-prefixed database and runs real migrations.
  Do not substitute SQLite or disable migrations to make a failing test pass.
  See RUNBOOK.md for the command, credentials boundary and test DB lifecycle.

- Keep verification proportional to the change. Do not create tests or run broad
  suites for every incremental edit.
- Use the smallest check that proves the changed behaviour: syntax/readback for
  tiny configuration or copy edits, and targeted tests for the affected module
  and its direct dependencies for scoped code changes.
- Run a full regression suite only for genuinely cross-cutting or high-risk
  changes, when the user explicitly requests it, or when a release/push gate
  requires it. Reuse fresh passing evidence when the code it covered has not
  changed.
- Explain why a broad regression run is necessary before starting one.
- Run `python manage.py check` after settings, model, URL, view, or template changes.
- For payment, auth, donation, user, or data migration work, prefer explicit tests and manual verification notes.
- If tests cannot be run because dependencies, network, secrets, or local services are unavailable, state that clearly.

## UI Verification Hook

Run UI verification only when Oluwafemi explicitly requests it. When requested:

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

## People, Recruitment and Access: Implementation Design Draft

This section records the direction approved for local implementation and the
reviewer's refinements. It is a code-review planning draft, not a published OEF
policy, a claim that the features exist, or permission to change live records.
The latest editorial decision uses three assignable capability presets: Writer,
Reviewer and Publisher. Preserve the release and manual-acceptance gates above.

### Domain boundaries and current scope

- Keep durable person identity, engagement, authentication account and backend
  access separate. Evolve TeamMember into a durable person record with an
  optional UserProfile link using SET_NULL. One person may have multiple
  Engagement records, including concurrent roles and later re-engagements.
- Engagement holds the paid/voluntary role title, engagement type, lifecycle,
  dates, onboarding evidence and optional source application. Content Writer,
  Grant and Research Writer and Programme Coordinator are role titles; Writer,
  Reviewer, Publisher and Recruitment Manager are backend capabilities, never
  engagement types or automatic consequences of a title.
- Support direct appointments from People without inventing an application.
  Event-only participants do not automatically become workforce members.
- Recruitment statuses are manager-entered descriptions, not an enforced state
  machine. A manager may correct or skip intermediate statuses. Selecting
  Appointed on an existing application atomically creates/links the person, a
  non-staff account and one active source-linked engagement, recording the
  appointment actor/time; repeating it must not create another engagement.
  Changing the application status later must not silently delete membership,
  end an engagement or revoke access. Declined offers, declined/pending
  agreements and failed onboarding remain distinct descriptive outcomes.
  An application submission alone creates no login account or TeamMember.
  Email delivery is not onboarding completion.
  Preserve recruitment history: remove appointed applications from the default
  active queue, not from the database. Provide authorised archive/filter access.
- People shows current/past engagements and a separate backend-access badge.
  Ending an engagement, suspending backend access and disabling account login
  are distinct operations. Ending the last eligible engagement must trigger an
  explicit access review/revocation decision; never silently retain access or
  disable an unrelated public account. Consider other active engagements.

### Authority and permissions

- Superuser controls protected administration. Staff Access Manager is a
  delegated capability, not a substitute superuser. Normal staff receive only
  selected functional groups. Job titles alone never confer permissions.
- Use a dedicated manage_team_access permission and curated People/access
  surface. Managers must not receive raw user/group administration or direct
  permission editing. Keep raw UserProfile and Group administration superuser-only.
- Enforce the delegable group allowlist server-side. Reject manager self-edits,
  manager/superuser targets, protected groups and direct-permission mutations.
  A manager must never be able to promote another manager or themselves.
- Present effective permissions before applying a desired-state access change.
  Membership, appointment and account creation must not automatically grant
  Recruitment Manager, is_staff or any other backend capability.
- Grant access separately from appointment/onboarding. Default to active
  engagements; any pre-activation exception requires an explicitly approved
  capability policy. Define the exact delegable group matrix before enabling
  delegation; do not infer finance, safeguarding or unrestricted recruitment access.
- People/onboarding surfaces expose only necessary contact and engagement
  information, not CVs, cover letters or confidential recruitment notes. Existing
  model-wide recruitment permissions must not be described as object-scoped.
- Maintain append-only BackendAccessChange history with target, actor, reason,
  timestamp and before/after capabilities. Use one access service with transaction
  and identity/concurrency safeguards. Invitation delivery happens after commit
  with recorded retryable outcomes; resend must not reset engagement state or
  reapply permissions. Report successful access change separately from failed email.

### Editorial workflow: Writers, Reviewers and Publishers

- A person may be both Writer and Reviewer. No recorded author or contributor
  may approve their own exact revision. Record immutable revision authorship
  separately from the submitting actor; changing the submitter must not bypass
  self-review protection. An editor who changes substantive content or SEO
  metadata becomes a contributor and needs another reviewer.
- Separate Draft, In review, Approved and Published states. Approval does not
  publish. Only a user with the Publisher capability may publish an independently
  approved exact revision. A supervisor needs that explicit capability, not just
  a title. An author does not receive publication rights merely through ownership.
- Reviewer and Publisher are separate assignable presets. A person may hold
  both and approve and publish another person's unchanged revision in one
  guarded action, or approve it for later publication. A distinct third person
  is not mandatory.
- A Publisher who finds a problem returns the revision for changes. If the
  Publisher edits content or SEO metadata, another Reviewer must approve it.
- Approval covers an immutable snapshot of all public content and metadata:
  author/contributors, title, excerpt, body, slug, feature/referenced media,
  relevant crop data, categories and tags. Any change invalidates approval.
  Validate the canonical payload/fingerprint at approval and publication under
  appropriate locks, including changes made through imports and M2M paths.
- Public pages, discovery and metadata must use the published revision. Editing
  a working draft must not change the live version before fresh approval/publication.
- Active staff explicitly granted `blog.publish_without_review`, and superusers
  implicitly, may publish drafts or current in-review snapshots without review.
  Only superusers grant this permission through protected account administration;
  do not add it to delegable Writer, Reviewer or Publisher presets. Record the
  immutable revision, actor, timestamp and bypass action; do not fabricate review
  actor/time. Reuse an unchanged in-review snapshot; reject stale submissions.
  Already approved revisions use normal publication, preserving their review.
  Revision sequence is named `iteration`; retain historical migration identifiers.
- A Publisher may unpublish an article without destroying its published revision
  or audit history. An unpublished article is absent from every public surface,
  including its direct URL, feeds, discovery and sitemap. Republishing unchanged
  approved content may reuse its approval; edits require a new review.

### Recruitment cohorts

- Add RecruitmentCohort with unique stable code, display name, lifecycle and
  transition timestamps: Draft, Open, Intake closed, Completed.
- Cohorts are optional batches. Vacancy.cohort is the current intake assignment;
  blank means Unbatched. VacancyApplication.cohort stores the submission's cohort
  independently, so moving a vacancy never reclassifies previous applicants.
  Managers may explicitly correct an application's cohort through admin.
- Closing a cohort closes its currently linked open vacancies atomically, not
  candidate outcomes, engagements or backend access. Individual vacancy closure
  does not close the cohort. Do not automatically create cohorts or close empty ones.
- Managers may reopen cohorts explicitly; this does not reopen their vacancies.
  Reopening a vacancy requires an open cohort or an explicit unbatched assignment.
  Retain durable role identity once applications exist; allow cohort reassignment.
- Duplicate protection is per vacancy and cohort (including the unbatched case),
  covering account identity and case-insensitive email. A later cohort permits
  reapplication. Intake and closure must serialise on vacancy rows.
- Migrate only explicitly known historical vacancy-cohort mappings to application
  cohorts. Unknown history stays null; never assume Cohort 1. No separate opening
  table or automatic cohort-routing engine is needed for this scope.

### Migration, verification and acceptance

- Add structures before retiring legacy fields. Preserve existing person/account,
  application and engagement links and evidence. Produce a read-only reconciliation
  report for duplicates, conflicting states and retained access. Ambiguous records
  require founder decisions; the reported approximately 12 team members is not
  verified backend data and must not drive invented records or Slack backfills.
- Verify row counts, links, permissions and history before switching workflows.
  Do not perform live data migration or bulk onboarding writes under local coding
  approval. Keep a tested rollback/recovery path for schema and data changes.
- Test escalation protection, privacy, multiple engagements, direct appointment,
  no-account membership, idempotency, invitation retries, suspension/offboarding,
  cohort closure/duplicates/history, self-review including editor contributions,
  author-only publication, stale/edited approval, metadata isolation and bypass audit.
- After every local code change and its relevant Django checks/tests, send the
  final diff to the existing visible reviewer task. The reviewer checks
  correctness, edge cases, code smells, over-engineering and irrelevant scope.
  Resolve findings and resend until the reviewer gives a final readback before
  declaring the local change complete. Present evidence and limitations, then
  await Oluwafemi's manual testing and explicit release approval. No UI
  automation without explicit authorisation.

### Future work and prerequisites

1. Reconcile current workforce and historical cohorts using founder-approved
   mappings; never infer identity or appointment from email/Slack membership alone.
2. Google Form/Sheet onboarding import: first verify the exact schema, consent,
   sensitivity and ownership. Use typed allowlisted fields, dry-run preview,
   stable engagement identifiers, verified source response identifiers for
   idempotency, per-row outcomes and import audit. Email is only a secondary
   identity check. Quarantine unmatched records; never create appointments from
   responses or overwrite locked submissions. Do not assume sheet row numbers
   are stable response IDs. No Google data operation is included in this phase.
3. Member self-service: one final initial submission per engagement, atomically
   locked. Corrections use authorised append-only versions with reason, actor
   and timestamp; preserve the original. Approve the fields, correction owners
   and restricted visibility before implementation. A full checklist engine waits.
4. Staff subdomain: defer DNS/hosting/deployment. Keep staff routes and links
   hostname-independent. A hidden URL is not security. Before deployment verify
   host routing, TLS, allowed hosts, CSRF, absolute links, host-only cookies,
   session/logout isolation and absence of staff data in public caches/analytics.
5. Defer generic configurable RBAC, departmental hierarchy, per-team/object
   scopes, payroll/benefits/performance, event shifts/attendance and automatic
   event-to-workforce conversion until concrete requirements justify them.
6. Consider reusable role templates and immutable advertised-term snapshots
   after the initial cohort/opening flow is complete. Do not build a generic HR
   platform as part of this change.
