<!-- docs:start -->
# Compliance

Inspection and compliance management system with structured records, evidence
attachments, archive/restore workflows, and AI-assisted site-history
analysis.

## Project Status

This project is an active portfolio MVP. It is designed for local demos,
technical review, and experimentation with compliance workflows, database-backed
APIs, and AI-assisted analysis. Before use with real compliance data, it would
need additional security, privacy, deployment, and operational review.

[![CI](https://github.com/elliottbache/compliance/actions/workflows/ci.yaml/badge.svg)](https://github.com/elliottbache/compliance/actions/workflows/ci.yaml)
[![codecov](https://codecov.io/github/elliottbache/compliance/graph/badge.svg?token=kNwbaexX4N)](https://codecov.io/github/elliottbache/compliance)
[![Release](https://img.shields.io/github/v/release/elliottbache/compliance)](https://github.com/elliottbache/compliance/releases)
[![License: PolyForm Noncommercial 1.0.0](https://img.shields.io/badge/license-PolyForm_NC_1.0.0-525252?style=flat-square)](https://polyformproject.org/licenses/noncommercial/1.0.0/)

![Python](https://img.shields.io/badge/Python-3.12-blue?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.129-blue?logo=fastapi&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-blue)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue?logo=postgresql&logoColor=white)
![Pydantic](https://img.shields.io/badge/Pydantic-v2-blue)
![Alembic](https://img.shields.io/badge/Alembic-migrations-blue)
![Anthropic](https://img.shields.io/badge/AI-Anthropic-blue)
![React](https://img.shields.io/badge/React-19-blue?logo=react&logoColor=white)
![TypeScript](https://img.shields.io/badge/TypeScript-5.7-blue?logo=typescript&logoColor=white)
![Vite](https://img.shields.io/badge/Vite-6-blue?logo=vite&logoColor=white)
![Docker](https://img.shields.io/badge/Docker-Compose-blue?logo=docker&logoColor=white)
![pytest](https://img.shields.io/badge/tests-pytest-blue?logo=pytest&logoColor=white)
![ruff](https://img.shields.io/badge/lint-ruff-blue)
![Sphinx](https://img.shields.io/badge/docs-Sphinx-blue?logo=sphinx&logoColor=white)

## Short demo: installation
![Installation demo](docs/demo.gif)

## Short demo: usage
![Usage demo](docs/browser_demo.gif)

## Overview

Compliance is a backend-first full-stack MVP for tracking inspection histories
across clients, sites, certifications, regulations, rules, findings, and
supporting evidence. The project emphasizes backend architecture, database
design, API boundaries, migrations, and service-layer correctness.  The goal is to keep 
compliance records queryable and traceable while making it
easy to review a site's prior inspection history before a new visit.

The current app supports:

- FastAPI backend with typed request/response schemas.
- PostgreSQL persistence through SQLAlchemy and Alembic migrations.
- React/Vite frontend for loading site history, attachments, AI analysis, and
  generated Markdown.
- Attachment metadata creation before file upload, plus upload/download support.
- Archive/restore workflows for main domain records.
- Optional AI site-history analysis:
  - `AI_MODE=mock` for deterministic offline demos.
  - `AI_MODE=anthropic` for live Anthropic-backed analysis.
- Demo data, fake attachment files, screenshots, and sample Markdown output.

AI output is intended as a human-review draft. It does not make official
compliance decisions and should not replace professional judgment.

The React frontend is intentionally lightweight: it exists to demonstrate and
exercise the backend workflows rather than to serve as a polished production UI.

## Samples

Demo screenshots live in `examples/demo/results/`:

![Load history](examples/demo/results/load_history.png)

![Load attachments](examples/demo/results/load_attachments1.png)

![Load attachments detail](examples/demo/results/load_attachments2.png)

Sample generated Markdown:

```text
examples/demo/results/site-71-analysis.md
```

## Architecture

```text
frontend/                    React + TypeScript + Vite UI
backend/src/compliance/
├── api/routers/             FastAPI route boundaries
├── db/                      SQLAlchemy models and database access
├── services/                Business logic and query composition
├── llm/                     Anthropic adapter and structured-output schemas
└── schemas.py               Cross-service domain output models
backend/migrations/          Alembic migration history
examples/demo/               Local demo seed data and fake evidence files
docker/                      Docker environment examples and Dockerfiles
```

The backend intentionally separates API schemas from service-layer schemas so
business logic can be tested without importing FastAPI models. Read paths apply
archive visibility rules in service queries; exact detail endpoints may still
return archived records for audit-trail access.

For a route-by-route overview of the backend request flow, see
[Backend Code Flow](docs/backend-flow.md).

## Quickstart

### Download repo

```bash
git clone https://github.com/elliottbache/compliance.git
cd compliance
```

### Run with Docker

Create a Docker environment file:

```bash
cp docker/.env.example docker/.env
```

For offline demos, keep:

```ini
AI_MODE=mock
ANTHROPIC_API_KEY=
```

For live Anthropic analysis, edit `docker/.env`:

```ini
AI_MODE=anthropic
ANTHROPIC_API_KEY=your_anthropic_api_key_here
```

If your network requires a proxy for outbound HTTPS, also set `HTTPS_PROXY` in
`docker/.env`.

Start the stack:

```bash
docker compose --env-file docker/.env up -d --build
```

Note: if the user is not part of the Docker security group, they can be added with:

```bash
sudo usermod -aG docker guest
newgrp docker
```

Open:

```text
http://localhost:5173
```

The backend is exposed at:

```text
http://localhost:8000
```

## Demo Data

The demo dataset centers on:

```text
Site ID: 71
```

Copy the fake attachment files into backend runtime storage:

```bash
mkdir -p backend/storage/attachments
cp examples/demo/attachments/* backend/storage/attachments/
```

With Docker Compose running, load the seed data:

```bash
docker compose --env-file docker/.env exec -T postgres psql -U postgres -d compliance_db < examples/demo/seed_demo_data.sql
```

Then open the frontend and run:

```text
Load History
Load Attachments
Run AI Analysis
Generate Markdown
Download Markdown
```

The seed file is for local demo use only. It truncates demo tables before
inserting records, so do not run it against a database containing real data.

See [Demo Documentation](examples/demo/README.md) for a more in-depth description of the demo example.

## Local Development

### Backend

Create a local backend environment file:

```bash
cp backend/.env.example backend/.env
```

Default local values:

```ini
POSTGRES_USER=postgres
POSTGRES_PASSWORD=postgres
POSTGRES_DB=compliance_db
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
AI_MODE=mock
ANTHROPIC_API_KEY=
```

Install the project and development dependencies:

```bash
python -m pip install -U pip
pip install -e .[dev]
```

Run migrations:

```bash
alembic upgrade head
```

Start the backend:

```bash
fastapi dev backend/src/compliance/api/main.py
```

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
npm run dev
```

`frontend/.env` should normally contain:

```ini
VITE_API_BASE_URL=http://localhost:8000
```

Open:

```text
http://localhost:5173
```

## Configuration

### AI mode

The site-analysis service reads `AI_MODE`:

- `mock`: returns deterministic offline analysis. This is the default and does
  not require an API key.
- `anthropic`: sends site history to Anthropic and validates the structured
  response against the Pydantic `SiteAnalysis` schema.

When `AI_MODE=anthropic`, `ANTHROPIC_API_KEY` must be set.

### Database

The backend builds its database URL from:

```ini
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
POSTGRES_HOST
POSTGRES_PORT
```

Environment variables already supplied by Docker or the shell are preserved;
`.env` files are loaded with `override=False`.

## Domain Model

The core records are:

- `Client`: organization that owns one or more sites.
- `Site`: physical location that receives inspections or certifications.
- `Certifier`: organization accrediting a certification.
- `Regulation`: compliance framework being checked.
- `Rule`: individual requirement within a regulation.
- `Certification`: inspection/certification event for one site.
- `Finding`: issue or observation tied to a certification and rule.
- `Attachment`: evidence file metadata and optional stored file.
- `FindingAttachment`: link between findings and supporting attachments.

Attachment records may exist before a file is uploaded. In that state,
`file_path` is `null` and the frontend displays the attachment path and upload date and time as ``--``.

## Archive Policy

Main domain records support archive and restore through `archived_at` and
`archive_reason`.

- List endpoints exclude archived records by default.
- List endpoints expose `include_archived=true`.
- Exact detail endpoints may return archived records by ID.
- Archive and restore operations are idempotent.
- Archive and restore do not cascade to child records.
- Child visibility is handled by read queries where implemented.
- `FindingAttachment` rows are not archived; they are link rows.

## Testing

Backend tests:

```bash
pytest --no-cov
```

Targeted examples:

```bash
pytest --no-cov backend/tests/services
pytest --no-cov backend/tests/db
pytest --no-cov backend/tests/llm
```

Frontend checks:

```bash
cd frontend
npm run build
npm run test
npm run test:e2e
```

Project linting uses Ruff for Python and ESLint for frontend code.

## Documentation

Sphinx documentation can be built with:

```bash
sphinx-build -b html docs docs/_build/html
```

GitHub Pages deployment is configured in `.github/workflows/pages.yaml`.

## Anthropic Retry and Error Policy

Live AI analysis uses `compliance.llm.anthropic_api.call_model` to send a
structured-output request to Anthropic and validate the response against a
Pydantic schema. The adapter separates transport/API retry behavior from model
stop-reason handling so operational failures, schema failures, and provider stop
states remain distinguishable.

### Retry policy

The retry decorator only retries Anthropic API/transport exceptions:

- `APIConnectionError`
- `APITimeoutError`
- `APIStatusError`

Retry limits are selected by status code:

- `408`, `429`, and `>=500`: retry up to 6 attempts.
- `400`, `401`, `402`, `403`, `404`, `413`, and `422`: stop after 1 attempt.
- Other API statuses, such as `409`: stop after 2 attempts.
- Connection and timeout errors: retry up to 6 attempts.

Model stop reasons are not treated as transport errors. They are converted into
typed application errors so callers and logs can distinguish why generation
stopped.

### Stop-reason errors

The adapter raises `LLMStopReasonError` subclasses for terminal stop reasons:

- `LLMMaxTokensError`: Anthropic returned `max_tokens`.
- `LLMToolUseError`: Anthropic requested tool use, which is not implemented by
  this adapter.
- `LLMPauseTurnError`: Anthropic returned `pause_turn`; continuation is not
  currently implemented.
- `LLMRefusalError`: Anthropic refused the request for safety reasons.
- `LLMContextWindowExceededError`: the model context window was exceeded.
- `LLMTokenBudgetExceededError`: local continuation handling exceeded the
  adapter token budget.

These errors are intentionally separate from Anthropic `APIStatusError`
failures. A refusal, a context-window problem, and a transient provider fault
need different operator responses.

### Typical flow patterns

Successful first response:

1. Build the system prompt, user message, and JSON schema.
2. Send the request to Anthropic.
3. Receive `stop_reason="end_turn"` with text content.
4. Parse the JSON and validate it against the requested Pydantic model.
5. Return the validated model.

Empty `end_turn` continuation:

1. Anthropic returns `stop_reason="end_turn"` with no content.
2. The adapter appends a user message asking the model to continue.
3. The next response is parsed and validated normally.
4. If the local token budget is exhausted, `LLMTokenBudgetExceededError` is
    raised.

Schema repair flow:

1. Anthropic returns text that is invalid JSON or fails Pydantic validation.
2. The adapter logs the failed response.
3. The adapter appends corrective context asking for valid structured output.
4. One repair attempt is allowed.
5. If validation fails again, the original JSON/Pydantic error is raised.

Transient API failure:

1. Anthropic raises a connection, timeout, rate-limit, or server-side status
    error.
2. Tenacity retries according to the status-code policy.
3. If all attempts fail, the original Anthropic exception is raised.

Terminal model stop:

1. Anthropic returns a stop reason such as `refusal`, `max_tokens`,
    `tool_use`, `pause_turn`, or `model_context_window_exceeded`.
2. The adapter raises the matching `LLMStopReasonError` subclass.
3. The caller can decide whether the issue needs prompt changes, smaller input,
    tool support, user review, or a durable failure record.

### Some Anthropic errors
```text
Exception (Python Base)
├── anthropic.APIConnectionError           # Network-layer errors (no HTTP response received)
│   └── anthropic.APITimeoutError          # Subclass for request or connection timeouts
│
└── anthropic.APIError                     # API-layer base exception
    └── anthropic.APIStatusError           # Server returned a non-2xx status code
        ├── anthropic.BadRequestError       # HTTP 400
        ├── anthropic.AuthenticationError   # HTTP 401
        ├── anthropic.PermissionDeniedError # HTTP 403
        ├── anthropic.NotFoundError         # HTTP 404
        ├── anthropic.ConflictError         # HTTP 409
        ├── anthropic.RateLimitError        # HTTP 429
        ├── anthropic.InternalServerError   # HTTP 500-504 - Backend Cluster Crash
        ├── anthropic.OverloadedError       # HTTP 529 - Heavy Traffic Spike
        └── Generic APIStatusError Fallbacks
            ├── HTTP 402                    # Payment Required / Billing Error
            ├── HTTP 408                    # Request Timeout (Gateway Proxy)
            ├── HTTP 413                    # Payload Too Large (> 32 MB)
            └── HTTP 422                    # Unprocessable Entity Data
```


## Roadmap

Near-term ideas:

### Bring code to production-level:
#### Security
-Authentication and authorization: users, roles, permissions, tenant/client isolation.
-File upload hardening: malware scanning, stricter MIME validation, size limits, quarantine, safe filenames, no direct path exposure.
-Secrets management: move API keys/db passwords to managed secrets, not .env files in deployed environments.
-API hardening: rate limits, CORS policy, request size limits, structured error handling, audit logging.
-Database security: least-privilege DB users, TLS connections, encrypted backups, migration safety checks.

#### Privacy
-Data classification: define what personal, client, regulatory, and confidential data may be stored.
-AI data policy: decide whether site history/attachments can be sent to Anthropic; document opt-in, redaction, retention, and audit trail.
-PII handling: redaction, minimization, retention periods, export/delete procedures where applicable.
-Attachment privacy: avoid exposing original filenames or storage paths if they contain sensitive info.

#### Deployment
-Production config: separate dev/staging/prod settings, no default passwords, no debug mode.
-Infrastructure: HTTPS, reverse proxy, container health checks, persistent storage, backups, restore testing.
-CI/CD: deployment gates, migration review, rollback plan, image scanning.
-Observability: logs, metrics, tracing, alerting, error reporting.

#### Operations
-Audit trail: who created/changed/archived/restored/uploaded/downloaded what and when.
-Data lifecycle: retention, archival, deletion, orphaned file cleanup.
-Incident response: what happens if data leaks, uploads fail, AI fails, or migrations fail.
-Human review policy: AI output should be labeled draft, reviewed by a person, and traceable to source records.

### New features
- Add a local model option for site analysis.
- Document Anthropic privacy boundaries and AI usage policy.
- Add regulation comparison/versioning workflows.
- Convert generated Markdown reports to PDF.
- Improve attachment upload/download selection UX.
- Add cleanup tooling for orphaned files.

## Author

Elliott Bache

## License

PolyForm Noncommercial License 1.0.0. See `LICENSE`.

## Version History

### v0.1.0 — Compliance MVP demo release

Initial public MVP release of the Compliance project.

Includes:

- FastAPI backend with PostgreSQL persistence.
- SQLAlchemy ORM/Core models and Alembic migrations.
- React/Vite/TypeScript frontend for the main demo workflow.
- Site-history loading for certifications, regulations, rules, and findings.
- Attachment metadata plus file upload/download support.
- Archive/restore workflows for main domain records.
- Optional AI site-analysis preview with mock and Anthropic-backed modes.
- Human-review-only Markdown report generation.
- Docker Compose local demo setup.
- Seeded demo dataset centered on Site ID `71`.
- Fake evidence attachment files for reproducible local walkthroughs.

This release is intended for local demos, portfolio review, and experimentation. It is not production-ready for real compliance data without additional security, privacy, deployment, and operational hardening.
<!-- docs:end -->
